# 0_preflight.ps1 -- run this FIRST, before touching the animal or the rig.
# No hardware needed. Proves the toolchain still works and sets up the shell.
#
#   .\rig\0_preflight.ps1
#
# PASS means: the MATLAB runtime is on PATH, the .exe runs, and the control loop
# holds its tick budget with zero dropped ticks.

$ErrorActionPreference = 'Continue'
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

Write-Host "=== 0. PRE-FLIGHT ===" -ForegroundColor Cyan

# --- MATLAB runtime on PATH -------------------------------------------------
# Not optional. Without it the .exe exits with code 53 and prints NOTHING AT ALL,
# which reads exactly like a hung program.
$mr = "C:\Program Files\MATLAB\R2025b"
if (-not (Test-Path "$mr\bin\matlab.exe")) {
    Write-Host "FAIL: MATLAB not found at $mr" -ForegroundColor Red
    Write-Host "      Find it with: Get-ChildItem 'C:\Program Files\MATLAB'" -ForegroundColor Yellow
    exit 1
}
$env:PATH = "$mr\runtime\win64;$mr\bin\win64;$mr\extern\bin\win64;$mr\sys\os\win64;$env:PATH"
$env:TDT_MATLAB_ROOT = $mr
Write-Host "  MATLAB runtime on PATH: $mr" -ForegroundColor Green

# --- Required files ---------------------------------------------------------
$needed = @(
    'MpcPo8eUdpClosedLoop.exe', 'mpc_test.m', 'matlab_controller_server.m',
    'make_excitation.m', 'fit_sysid_from_capture.m', 'AllModels.mat'
)
$missing = $needed | Where-Object { -not (Test-Path (Join-Path $repo $_)) }
if ($missing.Count -gt 0) {
    Write-Host "FAIL: missing files: $($missing -join ', ')" -ForegroundColor Red
    exit 1
}
Write-Host "  All $($needed.Count) required files present" -ForegroundColor Green

# --- Back up AllModels.mat before a day that will overwrite it --------------
# fit_sysid_from_capture makes its own backup on save, but a dated copy taken
# before the session means a bad fit is never one keystroke from unrecoverable.
$stamp  = Get-Date -Format 'yyyyMMdd'
$backup = Join-Path $repo "AllModels_backup_$stamp.mat"
if (-not (Test-Path $backup)) {
    Copy-Item (Join-Path $repo 'AllModels.mat') $backup
    Write-Host "  Backed up AllModels.mat -> $(Split-Path -Leaf $backup)" -ForegroundColor Green
} else {
    Write-Host "  Backup already exists: $(Split-Path -Leaf $backup)" -ForegroundColor DarkGray
}

# --- Smoke test: does the loop still hold its budget? ------------------------
Write-Host "  Running 300-tick smoke test (no hardware, ~5 s)..." -ForegroundColor Gray
$out = & .\MpcPo8eUdpClosedLoop.exe 127.0.0.1 . 16 --controller constant --constant-output 5 `
        --sim-input sine --sim-fs 610.3516 --sim-channels 16 --skip-udp-send `
        --max-control-ticks 300 --validate-log sim_smoke.csv 2>&1
$exit = $LASTEXITCODE

if ($exit -eq 53) {
    Write-Host "FAIL: exit code 53 -- MATLAB runtime not on PATH." -ForegroundColor Red
    Write-Host "      You are in a shell that never ran this script. Re-run it here." -ForegroundColor Yellow
    exit 1
}
$summary = $out | Select-String -Pattern '^Summary:'
if (-not $summary) {
    Write-Host "FAIL: no summary line. Exit code $exit. Raw tail:" -ForegroundColor Red
    $out | Select-Object -Last 15
    exit 1
}
Write-Host "  $summary" -ForegroundColor Gray

if ($summary -match 'droppedControlTicks=(\d+)') {
    $dropped = [int]$Matches[1]
    if ($dropped -eq 0) {
        Write-Host "PASS: droppedControlTicks=0. Toolchain healthy." -ForegroundColor Green
    } else {
        Write-Host "WARN: droppedControlTicks=$dropped (expected 0)." -ForegroundColor Yellow
        Write-Host "      Close other CPU load and re-run. If it persists, see" -ForegroundColor Yellow
        Write-Host "      RIG_DAY_2026-07-30.md branch A2." -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "This shell is now configured. Next: .\rig\1_server.ps1 (in a SECOND terminal)" -ForegroundColor Cyan
