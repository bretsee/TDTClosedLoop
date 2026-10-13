# archive_day.ps1 -- zip everything a rig day produced that git does not keep.
#
#   .\rig\archive_day.ps1 -Day 2026-10-14                       # -> Desktop\Data\Archive\TDTClosedLoop_2026-10-14.zip
#   .\rig\archive_day.ps1 -Day 2026-10-14 -Dest E:\Backups      # external drive
#
# Captures, loop logs, latency logs and rig_run CSVs are git-ignored (.gitignore),
# so "commit + push" saves only code, JSON, PNG and the ledger. This bundles:
#   day_<Day>\*            capture_rig_run*.csv    loop_run*.log    rig_run*.csv
#   server_*.log           BLOCK_LEDGER_<Day>.md   galleries\*      design_run*.csv + _meta.json
# TDT blocks are NOT included (they live under Desktop\Data; copy that folder too).

param(
    [string] $Day,
    [string] $Dest = 'C:\Users\brets\Desktop\Data\Archive'
)

if ([string]::IsNullOrWhiteSpace($Day)) { Write-Host "FAIL: -Day YYYY-MM-DD required" -ForegroundColor Red; exit 1 }
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
New-Item -ItemType Directory -Force $Dest | Out-Null
$zip = Join-Path $Dest ("TDTClosedLoop_{0}.zip" -f $Day)
if (Test-Path $zip) {
    $zip = Join-Path $Dest ("TDTClosedLoop_{0}_{1}.zip" -f $Day, (Get-Date -Format HHmmss))
}
$items = @()
foreach ($pat in @("day_$Day", 'capture_rig_run*.csv', 'loop_run*.log', 'rig_run*.csv', 'server_*.log',
                   "BLOCK_LEDGER_$Day.md", 'galleries', 'design_run*.csv', 'design_run*_meta.json')) {
    $hits = Get-ChildItem -Path $pat -ErrorAction SilentlyContinue
    if ($hits) { $items += $hits.FullName }
}
if (-not $items.Count) { Write-Host "FAIL: nothing to archive for $Day" -ForegroundColor Red; exit 1 }
$bytes = 0
foreach ($i in $items) {
    if (Test-Path $i -PathType Container) { $bytes += (Get-ChildItem $i -Recurse -File | Measure-Object Length -Sum).Sum }
    else { $bytes += (Get-Item $i).Length }
}
Write-Host ("archiving {0} item(s), {1:n1} MB -> {2}" -f $items.Count, ($bytes / 1MB), $zip) -ForegroundColor Cyan
Compress-Archive -Path $items -DestinationPath $zip -CompressionLevel Optimal
$sz = (Get-Item $zip).Length / 1MB
Write-Host ("DONE: {0} ({1:n1} MB)" -f $zip, $sz) -ForegroundColor Green
Write-Host "Next: copy the zip AND C:\Users\brets\Desktop\Data\<today's blocks> to the external drive; git add/commit/push both repos." -ForegroundColor Yellow
