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
    Write-Host "Design: generating $Design (MATLAB, ~30 s, offline -- not in the loop)..." -ForegroundColor Cyan
    $code = @"
cd('$($repo -replace '\\','/')'); addpath('rig');
write_excitation_csv('$Design','impulse',$Ticks,$Outputs, ...
    struct('pulseAmps',{[$ampList]},'gapTicks',$GapTicks, ...
           'gapJitterMeanTicks',$jitterTicks,'uMin',$UMin,'uMax',$UMax, ...
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
& $py rig\validate_impulse_design.py --capture $Design --amps @($PulseAmps) `
      --gap-ticks $GapTicks --jitter-mean-ticks ([math]::Max(1, [math]::Round($GapJitterMs / 10))) `
      --umax $UMax
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
