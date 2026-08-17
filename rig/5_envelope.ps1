# 5_envelope.ps1 -- send a KNOWN stim envelope to the RZ2 and log it. ONE TERMINAL.
#
# Standalone open-loop stim check: no PO8e, no MATLAB, no controller, no model.
# Answers "does a command I send come out of the stimulator, at the amplitude
# and on the channel I asked for?" -- which gates every other rig result.
#
#   .\rig\5_envelope.ps1 -Preview                            # draw it, send nothing
#   .\rig\5_envelope.ps1 -RZ2 10.1.0.100 -Channels 3         # REAL STIM, saw 0->10
#   .\rig\5_envelope.ps1 -RZ2 10.1.0.100 -Channels 1,5,9 -Stagger
#   .\rig\5_envelope.ps1 -DryRun                             # full timing loop, no socket
#
# WITHOUT -Preview or -DryRun this delivers real stim to real tissue.
# -UMax is the PULSE-AMPLITUDE ENVELOPE ceiling (physical limit 40); start low.

param(
    [string] $RZ2      = '',
    [string] $Shape    = 'saw',      # saw revsaw tri sine staircase pulse const
    [string] $Channels = '3',
    [double] $UMax     = 10,
    [double] $Period   = 2.0,
    [double] $Secs     = 20,
    [int]    $Count    = 8,
    [switch] $Stagger,
    [switch] $Preview,
    [switch] $DryRun,
    [string] $Log      = ''
)

$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

# No system Python on this machine; the analysis venv is the working interpreter.
# send_envelope.py itself is stdlib-only, so any python3 would do.
$py = Join-Path (Split-Path -Parent $repo) 'PythonIntanAnalysis\.venv\Scripts\python.exe'
if (-not (Test-Path $py)) {
    $cmd = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($null -eq $cmd) { Write-Host "FAIL: no Python found." -ForegroundColor Red; exit 1 }
    $py = $cmd.Source
}

if ([string]::IsNullOrWhiteSpace($Log)) { $Log = "envelope_sent_$Shape.csv" }

$a = @('rig\send_envelope.py', '--shape', $Shape, '--channels', $Channels,
       '--umax', "$UMax", '--period', "$Period", '--secs', "$Secs",
       '--count', "$Count", '--log', $Log)
if ($Stagger) { $a += '--stagger' }

if ($Preview) {
    & $py @a --preview
    exit $LASTEXITCODE
}

if ($DryRun) {
    Write-Host "=== DRY RUN: no socket opened, no stim delivered. ===" -ForegroundColor Green
    & $py @a --dry-run --yes
    exit $LASTEXITCODE
}

if ([string]::IsNullOrWhiteSpace($RZ2)) {
    Write-Host "FAIL: -RZ2 <ip> is required for a live run (or pass -Preview / -DryRun)." -ForegroundColor Red
    exit 1
}

Write-Host "=== LIVE RUN: stim WILL be delivered to $RZ2 ===" -ForegroundColor Red
Write-Host "    shape=$Shape channels=$Channels uMax=$UMax period=$Period s secs=$Secs" -ForegroundColor Yellow
Write-Host "    Start Synapse recording FIRST -- the check needs sSig from the block." -ForegroundColor Yellow
& $py @a --rz2 $RZ2

Write-Host ""
Write-Host "Next: stop the recording, then verify what was delivered:" -ForegroundColor Cyan
Write-Host "  $py rig\check_envelope.py --sent $Log --block <block_dir> --plot envelope_check.png" -ForegroundColor Gray
