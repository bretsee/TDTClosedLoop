# 1c_server.ps1 -- C++ open-loop probe server. TERMINAL 2, FOREGROUND.
#
# The MATLAB-free replacement for 1_server.ps1 on probe runs. Why: the
# 2026-08-17 saline run showed MATLAB server stalls (~100 ms) stretching
# single-tick probes to 70-90 ms bursts via the loop's hold-last policy, and
# silently dropping 5.1% of designed pulses. cpp_controller.exe answers in
# ~0.02 ms and does neither.
#
# MATLAB is still used ONCE, OFFLINE, to generate the design CSV (that is
# where make_excitation and its bench tests live) -- then the validated CSV is
# replayed verbatim by C++ with no MATLAB in the real-time path. If the design
# CSV already exists it is reused as-is (same file = same experiment).
#
#   .\rig\1c_server.ps1 -Run sal2 -Seed 777
#   .\rig\1c_server.ps1 -Run sal3 -Seed 424242 -PulseAmps 5,10,18,25 -GapJitterMs 80
#
# Downstream is unchanged: same capture_rig_run<Run>.csv name, same wire
# protocol, so 2_loop.ps1, validate_impulse_design.py, check_impulse_delivery.py
# and 3_fit.ps1 all work as before.

param(
    [Parameter(Mandatory = $true)]
    [string]   $Run,

    [double[]] $PulseAmps   = @(5, 10, 18, 25),
    [int]      $GapTicks    = 50,
    [double]   $GapJitterMs = 80,
    [double]   $UMax        = 25,
    [double]   $UMin        = 0,
    [int]      $Ticks       = 7000,
    [int]      $Seed        = 20260818,
    [int]      $Outputs     = 8,

    # 'interleaved' (default): all pairs share the record, cross-guard enforced.
    # 'sequential': fully independent per-pair blocks -- the clean-baseline
    # protocol (no cross-pair proximity at all). Costs ~8x the ticks for the same
    # per-pair statistics; with the sequential default of 28000 ticks (~4.6 min)
    # each pair gets ~57 pulses = ~15 trials/amplitude.
    # 'random': ONE global train, every probe's (pair, amplitude) drawn from a
    # balanced shuffled deck -- the tissue probing protocol (2026-08-25). Use
    # -GapTicks >= 36 so epochs are contamination-free by construction.
    [ValidateSet('interleaved','sequential','random')]
    [string]   $Schedule    = 'interleaved',

    # Interleaved only: minimum spacing between pulses on ANY two pairs.
    [double]   $CrossGuardMs = 20,
    # Active stim channels; default all $Outputs pairs (the saline validation
    # design). For tissue probing pass ONE pair, e.g. -Channels 3.
    [int[]]    $Channels    = $null,
    # Reuse an existing design CSV without regenerating (path override).
    [string]   $Design      = ''
)

$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
$mr  = "C:\Program Files\MATLAB\R2025b"
$py  = Join-Path (Split-Path -Parent $repo) 'PythonIntanAnalysis\.venv\Scripts\python.exe'

if (-not (Test-Path .\cpp_controller.exe)) {
    Write-Host "FAIL: cpp_controller.exe not found. Build it: .\build_cpp_controller.bat" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $py)) {
    Write-Host "FAIL: venv python not found at $py" -ForegroundColor Red
    exit 1
}

# Sequential needs ~numel(pairs)x the ticks for the same per-pair statistics.
# Default to 28000 (~4.6 min, ~15 trials/amp/pair) unless -Ticks was given.
if ($Schedule -eq 'sequential' -and -not $PSBoundParameters.ContainsKey('Ticks')) {
    $Ticks = 28000
    Write-Host "Sequential schedule: -Ticks defaulted to $Ticks (~$([math]::Round($Ticks/6000.0,1)) min)" -ForegroundColor Cyan
}
$guardTicks = [math]::Max(0, [math]::Round($CrossGuardMs / 10))

if ($Schedule -eq 'random') {
    # Trial math: one global train shares its probes across ALL conditions.
    $nChan = $Outputs
    if ($null -ne $Channels -and $Channels.Count -gt 0) { $nChan = $Channels.Count }
    $nCond  = $nChan * $PulseAmps.Count
    $jitT   = [math]::Max(1, [math]::Round($GapJitterMs / 10))
    $probes = [math]::Floor(($Ticks - $GapTicks) / ($GapTicks + 1 + $jitT))
    $tpc    = [math]::Round($probes / $nCond, 1)
    Write-Host ("Random schedule: {0} conditions ({1} ch x {2} amps), ~{3} probes " -f `
                $nCond, $nChan, $PulseAmps.Count, $probes) -NoNewline -ForegroundColor Cyan
    Write-Host ("=> ~{0} trials/condition over ~{1} min" -f `
                $tpc, [math]::Round($Ticks/6103.0,1)) -ForegroundColor Cyan
    if ($tpc -lt 3) {
        Write-Host ("WARNING: <3 trials/condition -- fit_impulse_model SKIPS such " +
                    "amplitude levels. Need -Ticks >= " +
                    [math]::Ceiling(3 * $nCond * ($GapTicks + 1 + $jitT) + $GapTicks)) -ForegroundColor Yellow
    }
    if ($GapTicks -lt 36) {
        Write-Host ("WARNING: -GapTicks $GapTicks < 36 (pre 5 + post 30 + 1): epochs " +
                    "will overlap neighbouring probes; contamination-free property lost.") -ForegroundColor Yellow
    }
}

if ([string]::IsNullOrWhiteSpace($Design)) { $Design = "design_run$Run.csv" }
$capture = "capture_rig_run$Run.csv"
$latlog  = "server_lat_run$Run.csv"

if (Test-Path $capture) {
    Write-Host "WARNING: $capture already exists and WILL BE OVERWRITTEN." -ForegroundColor Yellow
    $answer = Read-Host "         Type 'yes' to overwrite"
    if ($answer -ne 'yes') { Write-Host "Aborted."; exit 1 }
}

# --- 1. design (MATLAB, offline, once) --------------------------------------
if (Test-Path $Design) {
    Write-Host "Design: reusing existing $Design (delete it to regenerate)" -ForegroundColor Cyan
} else {
    $ampList = ($PulseAmps -join ' ')
    $jitterTicks = [math]::Max(1, [math]::Round($GapJitterMs / 10))
    $activeExpr = ''
    if ($null -ne $Channels -and $Channels.Count -gt 0) {
        $activeExpr = ",'activeChannels',{[$($Channels -join ' ')]}"
        Write-Host "Active stim channels: $($Channels -join ' ')" -ForegroundColor Cyan
    } else {
        Write-Host "Active stim channels: ALL $Outputs" -ForegroundColor Yellow
    }
    Write-Host "Design: generating $Design ($Schedule; MATLAB, ~30 s, offline -- not in the loop)..." -ForegroundColor Cyan
    $code = @"
cd('$($repo -replace '\\','/')'); addpath('rig');
write_excitation_csv('$Design','impulse',$Ticks,$Outputs, ...
    struct('pulseAmps',{[$ampList]},'gapTicks',$GapTicks, ...
           'gapJitterMeanTicks',$jitterTicks,'uMin',$UMin,'uMax',$UMax, ...
           'schedule','$Schedule','crossGuardTicks',$guardTicks, ...
           'seed',$Seed$activeExpr));
"@
    & "$mr\bin\matlab.exe" -batch $code 2>&1
    if (-not (Test-Path $Design)) {
        Write-Host "FAIL: design generation did not produce $Design" -ForegroundColor Red
        exit 1
    }
}

# --- 2. validate the design BEFORE anything is delivered --------------------
Write-Host "Validating design..." -ForegroundColor Cyan
$valArgs = @('--capture', $Design, '--gap-ticks', $GapTicks,
             '--jitter-mean-ticks', ([math]::Max(1, [math]::Round($GapJitterMs / 10))),
             '--umax', $UMax, '--guard-ticks', $guardTicks)
$valArgs += @('--amps'); $valArgs += $PulseAmps
if ($Schedule -eq 'random') {
    $valArgs += @('--schedule', 'random')
    $metaFile = $Design -replace '\.csv$', '_meta.json'
    if (Test-Path $metaFile) { $valArgs += @('--meta', $metaFile) }
}
& $py rig\validate_impulse_design.py @valArgs
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAIL: design validation failed -- not starting the server." -ForegroundColor Red
    exit 1
}

# --- 3. serve (C++, no MATLAB anywhere near the tick) -----------------------
$rows = (Get-Content $Design | Measure-Object -Line).Lines - 1
Write-Host ""
Write-Host "Starting C++ replay server: $rows ticks -> $capture" -ForegroundColor Cyan
Write-Host "Wait for 'ready', then run 2_loop.ps1 in the OTHER terminal." -ForegroundColor Gray
& .\cpp_controller.exe --mode openloop --play $Design --output-count $Outputs `
      --capture $capture --log $latlog --max-packets $rows
