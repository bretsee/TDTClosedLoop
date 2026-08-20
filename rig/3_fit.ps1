# 3_fit.ps1 -- fit a plant model from a capture, or triage every output channel.
#
#   .\rig\3_fit.ps1 -Run 1 -Sweep                       # WHICH channel responded? DO THIS FIRST
#   .\rig\3_fit.ps1 -Run 1 -Channel 7                   # full report for one channel
#   .\rig\3_fit.ps1 -Run 1 -Channel 7 -Validate 2       # fit on run 1, score on run 2
#   .\rig\3_fit.ps1 -Run 1 -Channel 7 -Save             # commit into AllModels(10).sys
#
# Read |corr| FIRST. Below ~0.1 the stim did not measurably move that feature,
# and every other number on the line is meaningless however confident it looks.
# ARX always returns a model.
#
# Order of operations that keeps you out of trouble:
#   -Sweep  ->  -Channel N  ->  -Validate  ->  -Save
# Do not -Save a model that has not survived a second, independent record.

param(
    [string] $Run      = '1',
    [int]    $Channel  = 1,
    [switch] $Sweep,
    [switch] $Save,
    [string] $Validate = '',        # a run label ('2') or a full capture filename
    [string] $CaptureFile = ''
)

$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
$mr = "C:\Program Files\MATLAB\R2025b"
$repoFwd = $repo -replace '\\','/'

if ([string]::IsNullOrWhiteSpace($CaptureFile)) { $CaptureFile = "capture_rig_run$Run.csv" }
if (-not (Test-Path $CaptureFile)) {
    Write-Host "FAIL: $CaptureFile not found." -ForegroundColor Red
    Write-Host "      Captures present:" -ForegroundColor Yellow
    Get-ChildItem -Filter 'capture_*.csv' -ErrorAction SilentlyContinue |
        Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize
    exit 1
}

# Everything is invoked as a SINGLE-LINE -batch command. Multi-line here-strings
# fail here with "This statement is incomplete" because of CRLF handling, which
# is why the real logic lives in sweep_channels.m / crossval_model.m rather than
# being embedded in this script.

# --- triage ------------------------------------------------------------------
if ($Sweep) {
    Write-Host "=== CHANNEL SWEEP over $CaptureFile ===" -ForegroundColor Cyan
    $cmd = "cd('$repoFwd'); sweep_channels('$CaptureFile');"
    & "$mr\bin\matlab.exe" -batch $cmd 2>&1
    exit $LASTEXITCODE
}

# --- cross-record validation -------------------------------------------------
if (-not [string]::IsNullOrWhiteSpace($Validate)) {
    if ($Validate -notmatch '\.csv$') { $valFile = "capture_rig_run$Validate.csv" }
    else                              { $valFile = $Validate }
    if (-not (Test-Path $valFile)) {
        Write-Host "FAIL: validation capture $valFile not found." -ForegroundColor Red
        Write-Host "      Take a second capture first: .\rig\1_server.ps1 -Run 2 -Seed 777 ..." -ForegroundColor Yellow
        exit 1
    }
    $cmd = "cd('$repoFwd'); crossval_model('$CaptureFile','$valFile',$Channel);"
    & "$mr\bin\matlab.exe" -batch $cmd 2>&1
    exit $LASTEXITCODE
}

# --- single-channel report (optionally committing the model) -----------------
$optFields = "'useOutputs',$Channel"
if ($Save) {
    Write-Host "=== SAVING into AllModels(10).sys ===" -ForegroundColor Yellow
    Write-Host "    (fit_sysid_from_capture backs up AllModels.mat first; 0_preflight" -ForegroundColor Gray
    Write-Host "     also took a dated copy before the session.)" -ForegroundColor Gray
    $optFields += ",'save',true"
}

$cmd = "cd('$repoFwd'); r = fit_sysid_from_capture('$CaptureFile', struct($optFields)); disp(r);"
& "$mr\bin\matlab.exe" -batch $cmd 2>&1

Write-Host ""
Write-Host "Read in this order:" -ForegroundColor Gray
Write-Host "  1. |corr| u->y     > 0.1 or nothing below matters" -ForegroundColor Gray
Write-Host "  2. valFit%         on held-out data; near 0 = no identifiable linear dynamic" -ForegroundColor Gray
Write-Host "  3. chosen order    NOT the physical state count -- ARX buys fit with states" -ForegroundColor Gray
Write-Host "  4. time constant   sanity-check against the evoked response you know" -ForegroundColor Gray

if ($Save) {
    Write-Host ""
    Write-Host "SAVED. Start the server with: 4_mpc_server.ps1 -FeatureChannel $Channel ..." -ForegroundColor Yellow
    Write-Host "(passes MPC_OPTS.featureChannel; no more hand-editing feature_map in" -ForegroundColor Yellow
    Write-Host "mpc_test.m. Without it the MPC controls feature 1, a channel it may" -ForegroundColor Yellow
    Write-Host "have no model of.)" -ForegroundColor Yellow
}
