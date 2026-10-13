# stim_zero.ps1 -- send zero to every stim word, NOW. Run after ANY crash or
# abort of a stim run (08-31 rule: hold-last on the RZ2 keeps delivering the
# last command until something overwrites it), and at the end of the day.
#
#   .\rig\stim_zero.ps1 [-RZ2 10.1.0.100]

param([string] $RZ2 = '10.1.0.100')

$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
$py = Join-Path (Split-Path -Parent $repo) 'PythonIntanAnalysis\.venv\Scripts\python.exe'
Write-Host ("STIM ZERO -> {0}" -f $RZ2) -ForegroundColor Red
& $py rig\send_envelope.py --rz2 $RZ2 --shape const --umax 0 --secs 2 --count 8 --yes
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: stim zero did not complete -- turn the stim-enable OFF in Synapse." -ForegroundColor Red; exit 1 }
Write-Host "stim zero sent (8 words, 2 s of zeros)." -ForegroundColor Green
