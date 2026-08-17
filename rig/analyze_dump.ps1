# analyze_dump.ps1 -- run WinDbgX commands against a dump, headless-ish.
#
#   .\rig\analyze_dump.ps1 -Dump crash_dumps\MpcPo8eUdpClosedLoop.exe.NNNN.dmp `
#                          -Log crash_dumps\analysis_cNN.log `
#                          -Commands "!analyze -v; k"
#
# WinDbgX has no true console mode: it opens a window, runs the commands, and
# STAYS OPEN after qq. This script launches it, waits for the log to be closed
# (the '.logclose' output line), then kills the window. Gotchas learned 2026-08-15:
#  - NEVER put .sympath in the -c chain: it treats the following ';'-separated
#    commands as symbol-path elements. Set _NT_SYMBOL_PATH instead (done here).
#  - .logopen must be FIRST so progress is observable.

param(
    [Parameter(Mandatory = $true)] [string] $Dump,
    [Parameter(Mandatory = $true)] [string] $Log,
    [string] $Commands = '!analyze -v; k',
    [int] $TimeoutSec = 240
)

$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
if (-not (Test-Path $Dump)) { Write-Host "FAIL: dump not found: $Dump" -ForegroundColor Red; exit 1 }
$logFull = Join-Path $repo $Log
Remove-Item $logFull -ErrorAction SilentlyContinue

$env:_NT_SYMBOL_PATH = "$repo;srv*C:\symbols*https://msdl.microsoft.com/download/symbols"
$dbg = "$env:LOCALAPPDATA\Microsoft\WindowsApps\WinDbgX.exe"
$cmd = ".logopen $logFull; .reload; $Commands; .logclose; qq"
# PS 5.1 Start-Process does NOT quote ArgumentList elements containing spaces --
# pass ONE pre-quoted string or WinDbgX sees the command chain as loose arguments.
$dumpFull = Join-Path $repo $Dump
$p = Start-Process $dbg -ArgumentList "-z `"$dumpFull`" -c `"$cmd`"" -PassThru

$deadline = (Get-Date).AddSeconds($TimeoutSec)
$closed = $false
while ((Get-Date) -lt $deadline) {
    if ((Test-Path $logFull) -and (Select-String -Path $logFull -Pattern 'Closing open log file' -Quiet -ErrorAction SilentlyContinue)) {
        $closed = $true; break
    }
    if ($p.HasExited) { break }
    Start-Sleep -Seconds 3
}
if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
if ($closed) { Write-Host "Analysis written to $Log" } else { Write-Host "WARN: log never closed (timeout ${TimeoutSec}s); partial output may exist in $Log" -ForegroundColor Yellow }
