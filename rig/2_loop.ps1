# 2_loop.ps1 -- run the C++ control loop. TERMINAL 1.
#
# Only start this AFTER 1_server.ps1 has printed 'ready' in terminal 2.
#
#   .\rig\2_loop.ps1 -Run 1 -RZ2 10.1.0.100          # REAL STIM
#   .\rig\2_loop.ps1 -Run 1 -Sim                     # dry rehearsal, no stim
#
# -Sim adds --sim-input (bypasses the PO8e card) and --skip-udp-send (nothing
# reaches the RZ2). Use it to rehearse the sequence without delivering current.
# WITHOUT -Sim, this delivers real stim to real tissue.

param(
    [string] $Run   = '1',

    # RZ2 IP. Required unless -Sim.
    [string] $RZ2   = '',

    [switch] $Sim,

    [int]    $Ticks = 6000,
    [int]    $TimeoutMs = 5,

    # Recording channels fed to the controller (argv[3] / mpcInputCount).
    # MUST match what the PO8e actually streams -- the .exe prints
    # "Streaming. numChannels=N" at startup. Asking for more than N is not an
    # error, it just zero-pads the extra features, which then pollute the fit.
    # Measured 2026-08-14: the card delivers 16. Raise this to 32 only once the
    # card reports 32.
    [int]    $InputChannels = 16,

    # UDP words per packet = BIPOLAR STIM PAIRS. The RZ2 receive gizmo reads 8;
    # anything past word 8 is discarded silently.
    [int]    $OutputCount = 8,

    # Frames per channel averaged into each feature. 6 = one 101.7253 Hz stim
    # period at the 610.3516 Hz acquisition rate -- keep it a multiple of 6 so
    # the stim artifact spans whole cycles.
    [int]    $FeatureWindow = 6,

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

    # Which binary to run. MpcPo8eUdpClosedLoop.jul23.exe is the archived Jul-23
    # build that completed 3000 ticks on rig day 1 -- use it to A/B whether a
    # crash is caused by the newer changes or by the card/environment.
    [string] $Exe = '.\MpcPo8eUdpClosedLoop.exe'
)

$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

# Re-assert PATH: this may be a fresh terminal that never ran 0_preflight.
# Without it the .exe exits 53 and prints nothing.
$mr = "C:\Program Files\MATLAB\R2025b"
$env:PATH = "$mr\runtime\win64;$mr\bin\win64;$mr\extern\bin\win64;$mr\sys\os\win64;$env:PATH"

$args = @(
    '--controller','localhost','--localhost-timeout-ms',"$TimeoutMs",
    '--max-control-ticks',"$Ticks",'--validate-log',"rig_run$Run.csv",
    '--udp-output-count',"$OutputCount",
    '--feature-window-samples',"$FeatureWindow"
)
if ($TickFrames -gt 0) {
    $args += @('--tick-frames',"$TickFrames")
    if ($TickPhaseUs -ne 0) { $args += @('--tick-phase-us',"$TickPhaseUs") }
    Write-Host "Tick scheduling: FRAME-LOCKED PLL, $TickFrames frames/tick (~101.7253 Hz), phase trim $TickPhaseUs us" -ForegroundColor Cyan
}

if ($Sim) {
    $target = '127.0.0.1'
    # 610.3516 Hz is the REAL NPro1 rate. The old 24414 made sim run 40x faster
    # than hardware, hiding the arrival-time window defect entirely.
    $args += @('--sim-input','sine','--sim-fs','610.3516','--sim-channels',"$InputChannels",'--skip-udp-send')
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
if ($Exe -match 'jul23|aug1[45]') {
    $exeArgs = @()
    for ($i = 0; $i -lt $args.Count; $i++) {
        if ($args[$i] -eq '--feature-window-samples' -and $Exe -match 'jul23') { $i++; continue }
        if ($args[$i] -eq '--tick-frames') { $i++; continue }
        $exeArgs += $args[$i]
    }
    Write-Host "  (dropped flags not present in this archived build)" -ForegroundColor Gray
}
& $Exe $target "$($repo -replace '\\','/')" $InputChannels @exeArgs 2>&1 | Tee-Object -FilePath $log

Write-Host ""
Write-Host "=== HEADLINE NUMBERS ===" -ForegroundColor Cyan
Get-Content $log | Select-String -Pattern '^Summary:|^Localhost summary:|^Exit reason:'
Write-Host ""
Write-Host "Want: droppedControlTicks=0, timeouts in the low tens, zeroTicks ~15-25 (startup only)." -ForegroundColor Gray
Write-Host "Next: check terminal 2 for 'Wrote N capture rows', then .\rig\3_fit.ps1 -Run $Run" -ForegroundColor Cyan
