# 4_mpc_server.ps1 -- closed-loop MPC server. TERMINAL 2, FOREGROUND.
#
#   .\rig\4_mpc_server.ps1 -Target 250
#   .\rig\4_mpc_server.ps1 -Target 250 -Ticks 3000     # bounded run, auto-stops
#   .\rig\4_mpc_server.ps1 -Reference ref_touch.csv -RWeight 1e-3
#                                                      # track a touch trajectory
#
# -Reference plays a per-tick reference CSV (from rig\build_touch_reference.py)
# through the MPC with horizon preview, instead of a constant -Target. Ticks
# defaults to the trajectory length. -RWeight sets the input-cost weight:
# the MPC penalises ABSOLUTE u with no integral action, so the default 1
# deliberately settles short of the target; ~1e-3 is where tracking starts to
# be honest. A (u,y) capture CSV is always written for post-run evaluation.
#
# Blocks like 1_server.ps1. Runs until -Ticks packets (or forever if -Ticks 0,
# ending on Ctrl+C).
#
# READ BEFORE THE FIRST CLOSED-LOOP RUN:
# The observer gain fix (a toolbox-free steady-state Kalman gain replacing a
# silent L = zeros(...) fallback) has ONLY ever been tested on the toy
# first-order model. Before 2026-07-23 the MPC ran fully open-loop and ignored
# its measurement entirely. This is the first time it closes the loop on a real
# plant. Watch the first run closely and keep a hand on Ctrl+C.
#
# WHAT TO WATCH in the server output:
#   out0 must CHANGE WITH feature0. If out0 converges to a constant while
#   feature0 moves, the loop is open somewhere -- stop and see branch E1.
#   Saturation at 0 or UMax means the target is unreachable -- see branch E2.

param(
    [double] $Target  = [double]::NaN,
    [int]    $Ticks   = 3000,
    # Per-tick reference trajectory CSV (rig\build_touch_reference.py output).
    # When set, -Target is not required and -Ticks defaults to trajectory length.
    [string] $Reference = '',
    # Input-cost weight passed as MPC_OPTS.rWeight (NaN = leave at default 1).
    [double] $RWeight = [double]::NaN,
    # Which physical stim pair slot(s) the controller's output(s) drive.
    # REQUIRED knowledge for a single-pair model: word k drives bipolar pair k,
    # so a model identified on pair 3 must map to slot 3 (-Pairs 3). Without
    # this, a 1-output model's command lands on pair 1 only.
    [int[]]  $Pairs = @(),
    # Stim outputs = BIPOLAR PAIRS (8 pairs = 16 electrodes; gizmo width is 8).
    [int]    $Outputs = 8,
    # MPC tuning pass-throughs (NaN = leave at mpc_test defaults 20/2/1/40).
    # All land in MPC_OPTS; mpc_test prints the values that took effect.
    [double] $Horizon        = [double]::NaN,   # MPC_OPTS.N (prediction, ticks)
    [double] $ControlHorizon = [double]::NaN,   # MPC_OPTS.Nu (moves)
    [double] $QWeight        = [double]::NaN,   # MPC_OPTS.qWeight
    [double] $UMax           = [double]::NaN,   # MPC_OPTS.umax (charge ceiling)
    # Feature channel the model's output was identified on (replaces the old
    # "hand-edit feature_map in mpc_test.m" step). 0 = legacy first-p mapping.
    [int]    $FeatureChannel = 0,
    # Width of the LIVE feature vector = the loop's -InputChannels. Sizes the
    # server's warm-up so any live channel is addressable; before 2026-08-29 the
    # warm-up latched mpc_test at 8-wide and -FeatureChannel 9+ threw
    # BadFeatureChannel mid-run. Pass 32 with a 32-ch circuit.
    [int]    $FeatureCount   = 16,
    # Which AllModels slot to control from (default 10).
    [int]    $ModelIndex     = 0
)

$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
$mr = "C:\Program Files\MATLAB\R2025b"

if ($FeatureChannel -gt $FeatureCount) {
    Write-Host "FAIL: -FeatureChannel $FeatureChannel > -FeatureCount $FeatureCount." -ForegroundColor Red
    Write-Host "      FeatureCount must be the loop's -InputChannels (the live feature" -ForegroundColor Yellow
    Write-Host "      width). Pass -FeatureCount 32 when running the 32-ch circuit." -ForegroundColor Yellow
    exit 1
}
if ([string]::IsNullOrWhiteSpace($Reference) -and [double]::IsNaN($Target)) {
    Write-Host "FAIL: either -Target <value> or -Reference <csv> is required." -ForegroundColor Red
    Write-Host "      Pick -Target from the feature range you actually observed in the" -ForegroundColor Yellow
    Write-Host "      open-loop capture (the 'output N: range [.. ..]' line from 3_fit)." -ForegroundColor Yellow
    Write-Host "      A target outside that range is unreachable and the command will" -ForegroundColor Yellow
    Write-Host "      simply pin at a bound, which tells you nothing." -ForegroundColor Yellow
    exit 1
}
if (-not [string]::IsNullOrWhiteSpace($Reference)) {
    if (-not (Test-Path $Reference)) {
        Write-Host "FAIL: reference file $Reference not found." -ForegroundColor Red
        exit 1
    }
    $refRows = (Get-Content $Reference | Measure-Object -Line).Lines - 1
    if ($Ticks -eq 3000 -and $refRows -gt 0) { $Ticks = $refRows }
}

$stamp  = Get-Date -Format 'yyyyMMdd_HHmmss'
$srvlog = "matlab_mpc_$stamp.log"
$capfile = "capture_mpc_$stamp.csv"

Write-Host "=== CLOSED-LOOP MPC ===" -ForegroundColor Red
if ([string]::IsNullOrWhiteSpace($Reference)) {
    Write-Host "  MPC_TARGET = $Target (constant)" -ForegroundColor Cyan
} else {
    Write-Host "  reference  = $Reference ($refRows ticks)" -ForegroundColor Cyan
}
if (-not [double]::IsNaN($RWeight)) {
    Write-Host "  rWeight    = $RWeight" -ForegroundColor Cyan
}
Write-Host "  ticks      = $Ticks" -ForegroundColor Cyan
Write-Host "  log        -> $srvlog" -ForegroundColor Cyan
Write-Host "  capture    -> $capfile" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Confirm you have already saved the fitted model (3_fit -Save), and pass" -ForegroundColor Yellow
Write-Host "  -FeatureChannel <k> for the channel it was identified on (no more" -ForegroundColor Yellow
Write-Host "  hand-editing feature_map in mpc_test.m)." -ForegroundColor Yellow
Write-Host ""

# mpc_test([]) resets persistent state so the run starts clean and picks up the
# newly saved AllModels (and any MPC_OPTS). Without it, a model saved during
# this MATLAB session is not necessarily the one the controller uses.
$targetLine = ''
if (-not [double]::IsNaN($Target)) {
    $targetLine = "assignin('base','MPC_TARGET',$Target);"
}
$modelLine = ''
if ($ModelIndex -gt 0) {
    $modelLine = "assignin('base','MPC_MODEL_INDEX',$ModelIndex);"
    Write-Host "  model slot = AllModels($ModelIndex)" -ForegroundColor Cyan
}
# Accumulate every non-NaN tuning override into ONE cfg.mpcOpts struct.
# Names must match the mpc_test whitelist (N/Nu/qWeight/rWeight/umax/
# featureChannel) or they are silently dropped there.
$optPairs = @()
if (-not [double]::IsNaN($RWeight))        { $optPairs += "'rWeight',$RWeight" }
if (-not [double]::IsNaN($Horizon))        { $optPairs += "'N',$Horizon";  Write-Host "  horizon    = $Horizon ticks" -ForegroundColor Cyan }
if (-not [double]::IsNaN($ControlHorizon)) { $optPairs += "'Nu',$ControlHorizon"; Write-Host "  ctrl horiz = $ControlHorizon moves" -ForegroundColor Cyan }
if (-not [double]::IsNaN($QWeight))        { $optPairs += "'qWeight',$QWeight"; Write-Host "  qWeight    = $QWeight" -ForegroundColor Cyan }
if (-not [double]::IsNaN($UMax))           { $optPairs += "'umax',$UMax";   Write-Host "  uMax       = $UMax" -ForegroundColor Cyan }
if ($FeatureChannel -gt 0)                 { $optPairs += "'featureChannel',$FeatureChannel"; Write-Host "  feat chan  = $FeatureChannel" -ForegroundColor Cyan }
$optsLine = ''
if ($optPairs.Count -gt 0) {
    $optsLine = "cfg.mpcOpts = struct($($optPairs -join ','));"
}
$refLine = ''
if (-not [string]::IsNullOrWhiteSpace($Reference)) {
    $refLine = "cfg.referenceFile = '$($Reference -replace '\\','/')';"
}
$pairsLine = ''
if ($Pairs.Count -gt 0) {
    $pairsLine = "cfg.stimPairs = [$($Pairs -join ' ')];"
    Write-Host "  stim pairs = [$($Pairs -join ' ')]" -ForegroundColor Cyan
} else {
    Write-Host "  NOTE: no -Pairs given; a 1-output model drives PAIR 1 only." -ForegroundColor Yellow
}
$code = @"
cd('$($repo -replace '\\','/')');
mpc_test([]);
$targetLine
$modelLine
cfg = struct('mode','mpc','requestPort',31000,'replyPort',31001, ...
             'outputCount',$Outputs,'maxPackets',$Ticks,'logFile','mpc_lat_$stamp.csv', ...
             'captureFile','$capfile','featureCount',$FeatureCount);
$optsLine
$refLine
$pairsLine
matlab_controller_server(cfg)
"@

& "$mr\bin\matlab.exe" -batch $code 2>&1 | Tee-Object -FilePath $srvlog

Write-Host ""
Write-Host "=== DID THE LOOP CLOSE? ===" -ForegroundColor Cyan
# The single most important check: out0 must vary. A constant out0 across
# replies is the exact signature of the pre-2026-07-23 open-loop defect.
$replies = Get-Content $srvlog | Select-String -Pattern 'out0='
if ($replies.Count -ge 2) {
    $vals = $replies | ForEach-Object {
        if ($_ -match 'out0=([-\d.]+)') { [double]$Matches[1] }
    }
    $spread = ($vals | Measure-Object -Maximum -Minimum)
    $range  = $spread.Maximum - $spread.Minimum
    Write-Host ("  out0 range over {0} logged replies: {1:N4}  (min {2:N4}, max {3:N4})" -f $vals.Count, $range, $spread.Minimum, $spread.Maximum)
    if ($range -lt 1e-6) {
        Write-Host "  *** out0 IS CONSTANT. The loop is NOT closed. See branch E1. ***" -ForegroundColor Red
    } else {
        Write-Host "  out0 varies -- the controller is responding to its measurement." -ForegroundColor Green
    }
} else {
    Write-Host "  Not enough logged replies to judge." -ForegroundColor Yellow
}
