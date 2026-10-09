# 2_loop.ps1 -- run the C++ control loop. TERMINAL 1.
#
# Only start this AFTER 1_server.ps1 has printed 'ready' in terminal 2.
#
#   .\rig\2_loop.ps1 -Run 1 -RZ2 10.1.0.100          # REAL STIM
#   .\rig\2_loop.ps1 -Run 1 -Sim                     # dry rehearsal, no stim
#   .\rig\2_loop.ps1 -Run gate -RZ2 10.1.0.100 -Design design_rungate.csv `
#                    -Capture capture_rig_rungate.csv -Baseline 2.1e-4
#
# -Sim adds --sim-input (bypasses the PO8e card) and --skip-udp-send (nothing
# reaches the RZ2). Use it to rehearse the sequence without delivering current.
# WITHOUT -Sim, this delivers real stim to real tissue.
#
# -Design <csv>  sets -Ticks from the design's _meta.json nTicks (else its row
#                count) so the loop length can no longer disagree with what
#                terminal 2 is playing. An explicit -Ticks still wins.
# -Capture <csv> the capture terminal 2 is streaming (cpp_controller --capture).
#                When given, a THIRD window runs check_y_liveness.py --watch on
#                it from the moment you type 'go' (y-liveness rule, 09-10 PZ2-off
#                incident: 3 void runs, ~1.3M uA-ticks delivered unrecorded).
# -Baseline <V>  today's quiet-capture MAV baseline for that watch.

param(
    [string] $Run   = '1',

    # RZ2 IP. Required unless -Sim.
    [string] $RZ2   = '',

    [switch] $Sim,

    [int]    $Ticks = 6000,
    [int]    $TimeoutMs = 5,

    # Design CSV terminal 2 is playing; -Ticks is derived from it (see header).
    [string] $Design = '',
    # Capture CSV terminal 2 is streaming; spawns the y-liveness watch window.
    [string] $Capture = '',
    # Quiet-capture MAV baseline (V) passed to the watch.
    [double] $Baseline = 0,

    # Recording channels fed to the controller (argv[3] / mpcInputCount).
    # MUST match what the PO8e actually streams -- the .exe prints
    # "Streaming. numChannels=N" at startup. Since 2026-08-29 asking for MORE
    # than N is a FATAL startup error (the padded features are exact zeros and
    # poison fits; --allow-channel-pad overrides for deliberate debugging).
    # Asking for fewer warns and uses the first M channels (legitimate 16-ch
    # fallback on a 32-ch circuit). Raise to 32 only once the card reports 32.
    [int]    $InputChannels = 16,

    # UDP words per packet = BIPOLAR STIM PAIRS. The RZ2 receive gizmo reads 8;
    # anything past word 8 is discarded silently.
    [int]    $OutputCount = 8,

    # Frames per channel averaged into each feature. 6 = one 101.7253 Hz stim
    # period at the 610.3516 Hz acquisition rate -- keep it a multiple of 6 so
    # the stim artifact spans whole cycles.
    [int]    $FeatureWindow = 6,

    # Feature = signed mean(x) instead of rectified mean(|x|) (Choi-2016-style
    # signed LFP). Models/references fitted in one mode are NOT valid in the
    # other -- capture and deploy must agree, like -TickFrames.
    [switch] $FeatureSigned,

    # 0 = wall-clock 10 ms ticks (legacy). 6 = FRAME-LOCKED: tick every 6 ingested
    # frames = exactly one 101.7253 Hz stim-carrier period on the RZ2's own clock,
    # eliminating the carrier beat (1.9% missed / 4.2% doubled probe pulses under
    # wall-clock ticking, measured 2026-08-18). Use 6 for probe runs. Do NOT use
    # for closed-loop runs until Ts is aligned in mpc_test/fit_sysid (runbook).
    [int]    $TickFrames = 0,

    # Frame-locked only: phase trim in us for the counter-quantized tick grid.
    # check_impulse_delivery.py prints the recommended value (centers commands
    # mid-latch-period, maximum margin against tick-fire jitter).
    [double] $TickPhaseUs = 0,

    # Hardware PO8e stream rate. Default 610.3515625 (base/40). Pass
    # 1220.703125 (base/20) with -TickFrames 12 -FeatureWindow 12 when the
    # Synapse circuit streams Wav at 2x (the 2026-08-25 Choi-rate option).
    # Only forwarded to the exe when explicitly given.
    [double] $StreamFs = 610.3515625,

    # Sim acquisition rate for -Sim runs (default = the real base/40 rate;
    # 1220.703125 rehearses the 2x option with no hardware).
    [double] $SimFs = 610.3516,

    # Drop the K largest-|x| samples from each feature window (stim-artifact
    # rejection, --feature-trim). Models/references fitted untrimmed are NOT
    # valid trimmed -- capture and deploy must agree, like -FeatureSigned.
    [int]    $FeatureTrim = 0,

    # Which binary to run. MpcPo8eUdpClosedLoop.jul23.exe is the archived Jul-23
    # build that completed 3000 ticks on rig day 1 -- use it to A/B whether a
    # crash is caused by the newer changes or by the card/environment.
    [string] $Exe = '.\MpcPo8eUdpClosedLoop.exe'
)

$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
$py = Join-Path (Split-Path -Parent $repo) 'PythonIntanAnalysis\.venv\Scripts\python.exe'

# Re-assert PATH: this may be a fresh terminal that never ran 0_preflight.
# Without it the .exe exits 53 and prints nothing.
$mr = "C:\Program Files\MATLAB\R2025b"
$env:PATH = "$mr\runtime\win64;$mr\bin\win64;$mr\extern\bin\win64;$mr\sys\os\win64;$env:PATH"

# -Design: derive the tick count from the design so it cannot be mistyped.
if (-not [string]::IsNullOrWhiteSpace($Design)) {
    if (-not (Test-Path $Design)) {
        Write-Host "FAIL: -Design $Design not found." -ForegroundColor Red
        exit 1
    }
    $meta = [System.IO.Path]::ChangeExtension($Design, $null).TrimEnd('.') + '_meta.json'
    $designTicks = 0
    $source = ''
    if (Test-Path $meta) {
        try {
            $m = Get-Content $meta -Raw | ConvertFrom-Json
            if ($null -ne $m.nTicks) { $designTicks = [int]$m.nTicks; $source = "meta $meta (kind=$($m.kind))" }
        } catch { Write-Host "WARN: could not parse $meta ($($_.Exception.Message)); using the row count." -ForegroundColor Yellow }
    }
    if ($designTicks -le 0) {
        $designTicks = ((Get-Content $Design | Measure-Object -Line).Lines - 1)
        $source = "row count of $Design"
    }
    if ($PSBoundParameters.ContainsKey('Ticks')) {
        if ($Ticks -ne $designTicks) {
            Write-Host "WARNING: -Ticks $Ticks disagrees with the design ($designTicks from $source). Using -Ticks as given." -ForegroundColor Yellow
        }
    } else {
        $Ticks = $designTicks
        Write-Host "Ticks from design: $Ticks ($source)" -ForegroundColor Cyan
    }
}

$args = @(
    '--controller','localhost','--localhost-timeout-ms',"$TimeoutMs",
    '--max-control-ticks',"$Ticks",'--validate-log',"rig_run$Run.csv",
    '--udp-output-count',"$OutputCount",
    '--feature-window-samples',"$FeatureWindow"
)
if ($FeatureSigned) {
    $args += '--feature-signed'
    Write-Host "Feature mode: SIGNED mean(x) (Choi-style LFP). Models fitted on rectified captures do NOT apply." -ForegroundColor Yellow
}
if ($FeatureTrim -gt 0) {
    $args += @('--feature-trim',"$FeatureTrim")
    Write-Host "Feature TRIM: dropping $FeatureTrim largest-|x| sample(s)/window (artifact rejection). Models fitted untrimmed do NOT apply." -ForegroundColor Yellow
}
if ($PSBoundParameters.ContainsKey('StreamFs')) {
    $args += @('--stream-fs',"$StreamFs")
    Write-Host "Stream rate override: $StreamFs Hz (must match the Synapse Wav divisor; the exe cross-checks against the offset stride)" -ForegroundColor Cyan
}
if ($TickFrames -gt 0) {
    $args += @('--tick-frames',"$TickFrames")
    if ($TickPhaseUs -ne 0) { $args += @('--tick-phase-us',"$TickPhaseUs") }
    Write-Host "Tick scheduling: FRAME-LOCKED PLL, $TickFrames frames/tick (~101.7253 Hz), phase trim $TickPhaseUs us" -ForegroundColor Cyan
}

if ($Sim) {
    $target = '127.0.0.1'
    # 610.3516 Hz is the REAL NPro1 rate. The old 24414 made sim run 40x faster
    # than hardware, hiding the arrival-time window defect entirely.
    $args += @('--sim-input','sine','--sim-fs',"$SimFs",'--sim-channels',"$InputChannels",'--skip-udp-send')
    Write-Host "=== DRY RUN: sim input, UDP send suppressed. No stim will be delivered. ===" -ForegroundColor Green
} else {
    if ([string]::IsNullOrWhiteSpace($RZ2)) {
        Write-Host "FAIL: -RZ2 <ip> is required for a live run (or pass -Sim to rehearse)." -ForegroundColor Red
        exit 1
    }
    $target = $RZ2
    Write-Host "=== LIVE RUN: stim WILL be delivered to $RZ2 ===" -ForegroundColor Red
    Write-Host "    Confirm terminal 2 printed the excitation summary you intended," -ForegroundColor Yellow
    Write-Host "    and that the active channels and u range are correct." -ForegroundColor Yellow
    $answer = Read-Host "    Type 'go' to deliver stim"
    if ($answer -ne 'go') { Write-Host "Aborted. Nothing was sent." -ForegroundColor Green; exit 1 }
}

Write-Host "Running $Ticks ticks ($($Ticks/100) s)..." -ForegroundColor Cyan
$log = "loop_run$Run.log"
Write-Host "Binary: $Exe" -ForegroundColor Gray
# Archived builds predate --feature-window-samples / --tick-frames; drop flags
# they cannot parse so the A/B actually runs instead of failing on an unknown arg.
$exeArgs = $args
if ($Exe -match 'jul23|aug1[458]|aug20|aug25-pre') {
    $exeArgs = @()
    for ($i = 0; $i -lt $args.Count; $i++) {
        if ($args[$i] -eq '--feature-window-samples' -and $Exe -match 'jul23') { $i++; continue }
        if ($args[$i] -eq '--tick-frames' -and $Exe -match 'jul23|aug1[45]') { $i++; continue }
        if ($args[$i] -eq '--feature-signed' -and $Exe -match 'jul23|aug1[458]') { continue }
        # --stream-fs / --feature-trim exist only in builds from 2026-08-25 on.
        if ($args[$i] -eq '--stream-fs' -and $Exe -match 'jul23|aug1[458]|aug20|aug25-pre') { $i++; continue }
        if ($args[$i] -eq '--feature-trim' -and $Exe -match 'jul23|aug1[458]|aug20|aug25-pre') { $i++; continue }
        $exeArgs += $args[$i]
    }
    Write-Host "  (dropped flags not present in this archived build)" -ForegroundColor Gray
}

# y-liveness watch in its own window, started as the loop starts (not after
# the run): the capture is streamed by cpp_controller, so a dead amplifier
# shows as DEAD within the first minute instead of in the post-hoc scan.
if (-not [string]::IsNullOrWhiteSpace($Capture)) {
    if (-not (Test-Path $py)) {
        Write-Host "WARN: venv python not found at $py -- no liveness watch window." -ForegroundColor Yellow
    } else {
        $watchArgs = "& '$py' '$repo\rig\check_y_liveness.py' --capture '$Capture' --watch"
        if ($Baseline -gt 0) { $watchArgs += " --baseline $Baseline" }
        Start-Process powershell -ArgumentList '-NoExit', '-Command', $watchArgs
        Write-Host "y-liveness watch window started on $Capture (close it after 'Summary:')." -ForegroundColor Cyan
    }
} else {
    Write-Host "No -Capture given: no y-liveness watch. Run rig\check_y_liveness.py on the capture within the first minute." -ForegroundColor Yellow
}

& $Exe $target "$($repo -replace '\\','/')" $InputChannels @exeArgs 2>&1 | Tee-Object -FilePath $log

Write-Host ""
Write-Host "=== HEADLINE NUMBERS ===" -ForegroundColor Cyan
Get-Content $log | Select-String -Pattern '^Summary:|^Localhost summary:|^Exit reason:'
Write-Host ""
Write-Host "Want: droppedControlTicks=0, timeouts in the low tens, zeroTicks ~15-25 (startup only)." -ForegroundColor Gray
$auditLine = "$py rig\run_audit.py --run $Run --loop-log $log"
if (-not [string]::IsNullOrWhiteSpace($Capture)) { $auditLine += " --capture $Capture" }
if ($Sim) { $auditLine += " --sim" }
Write-Host "Next: $auditLine" -ForegroundColor Cyan
Write-Host "      (one PASS/WARN/FAIL line; then rig\3_fit.ps1 -Run $Run or ingest_block.py)" -ForegroundColor Gray
