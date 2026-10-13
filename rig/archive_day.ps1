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
#
# Files that are still open for writing (a run in progress) are SKIPPED and listed,
# not fatal: Compress-Archive aborted the whole zip on one locked file (10-13 test).
# Run it at WRAP, after the last 'Summary:'.

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
$files = @()
foreach ($pat in @("day_$Day", 'capture_rig_run*.csv', 'loop_run*.log', 'rig_run*.csv', 'server_*.log',
                   "BLOCK_LEDGER_$Day.md", 'galleries', 'design_run*.csv', 'design_run*_meta.json')) {
    $hits = Get-ChildItem -Path $pat -ErrorAction SilentlyContinue
    foreach ($h in $hits) {
        if ($h.PSIsContainer) { $files += (Get-ChildItem $h.FullName -Recurse -File).FullName }
        else { $files += $h.FullName }
    }
}
$files = $files | Sort-Object -Unique
if (-not $files.Count) { Write-Host "FAIL: nothing to archive for $Day" -ForegroundColor Red; exit 1 }
$bytes = ($files | ForEach-Object { (Get-Item $_).Length } | Measure-Object -Sum).Sum
Write-Host ("archiving {0} file(s), {1:n1} MB -> {2}" -f $files.Count, ($bytes / 1MB), $zip) -ForegroundColor Cyan

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$skipped = @()
$added = 0
$archive = [System.IO.Compression.ZipFile]::Open($zip, [System.IO.Compression.ZipArchiveMode]::Create)
try {
    foreach ($f in $files) {
        $rel = $f.Substring($repo.Length).TrimStart('\') -replace '\\', '/'
        try {
            [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, $f, $rel, [System.IO.Compression.CompressionLevel]::Optimal) | Out-Null
            $added++
        } catch {
            $skipped += $rel
        }
    }
} finally {
    $archive.Dispose()
}
if (-not (Test-Path $zip)) { Write-Host "FAIL: zip was not written: $zip" -ForegroundColor Red; exit 1 }
$sz = (Get-Item $zip).Length / 1MB
Write-Host ("DONE: {0} ({1:n1} MB, {2} file(s))" -f $zip, $sz, $added) -ForegroundColor Green
if ($skipped.Count) {
    Write-Host ("SKIPPED {0} file(s) still open for writing (rerun after the last Summary:):" -f $skipped.Count) -ForegroundColor Yellow
    $skipped | ForEach-Object { Write-Host "    $_" -ForegroundColor Yellow }
}
Write-Host "Next: copy the zip AND C:\Users\brets\Desktop\Data\<today's blocks> to the external drive; git add/commit/push both repos." -ForegroundColor Yellow
exit 0
