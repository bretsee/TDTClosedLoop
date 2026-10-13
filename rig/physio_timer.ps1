# physio_timer.ps1 -- periodic beep + log for animal monitoring (solo surgeon).
#
#   .\rig\physio_timer.ps1 -Day 2026-10-14 -EveryMin 15
#
# Every -EveryMin minutes: three beeps, then a prompt. Type the reading (free
# text: HR / RR / SpO2 / temp / reflex / dose) or '-' to skip, 'q' to quit.
# Appends "time,entry" to day_<Day>\physio_log.csv. The interval and WHAT to
# record come from the lab's approved animal protocol -- this script only keeps
# the clock honest. Run it in its own window from Phase 0.

param(
    [string] $Day,
    [int]    $EveryMin = 15
)

if ([string]::IsNullOrWhiteSpace($Day)) { Write-Host "FAIL: -Day YYYY-MM-DD required" -ForegroundColor Red; exit 1 }
$repo = Split-Path -Parent $PSScriptRoot
$dir = Join-Path $repo ("day_{0}" -f $Day)
New-Item -ItemType Directory -Force $dir | Out-Null
$log = Join-Path $dir 'physio_log.csv'
if (-not (Test-Path $log)) { 'time,entry' | Out-File -Encoding ascii $log }
Write-Host ("physio timer: every {0} min -> {1}  (type '-' to skip an entry, 'q' to quit)" -f $EveryMin, $log) -ForegroundColor Cyan
$next = Get-Date
while ($true) {
    $now = Get-Date
    if ($now -lt $next) { Start-Sleep -Seconds ([math]::Max(1, [int]($next - $now).TotalSeconds)); continue }
    1..3 | ForEach-Object { [console]::Beep(880, 250); Start-Sleep -Milliseconds 120 }
    $entry = Read-Host ("{0} physiology reading" -f (Get-Date -Format HH:mm))
    if ($entry -eq 'q') { break }
    if ($entry -ne '-' -and -not [string]::IsNullOrWhiteSpace($entry)) {
        ('{0},"{1}"' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), ($entry -replace '"', "'")) | Out-File -Append -Encoding ascii $log
        Write-Host "  logged." -ForegroundColor Green
    }
    $next = (Get-Date).AddMinutes($EveryMin)
    Write-Host ("  next reminder {0}" -f $next.ToString('HH:mm')) -ForegroundColor Gray
}
