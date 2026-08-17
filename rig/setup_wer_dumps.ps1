# setup_wer_dumps.ps1 -- register WER LocalDumps for MpcPo8eUdpClosedLoop.exe. NEEDS ADMIN.
#
#   .\rig\setup_wer_dumps.ps1            # install: full dumps -> repo crash_dumps\
#   .\rig\setup_wer_dumps.ps1 -Remove    # post-campaign cleanup
#
# WER keys on the IMAGE NAME only, so archived copies (jul23/aug14/aug15 names)
# will not produce dumps -- only the canonical MpcPo8eUdpClosedLoop.exe.

param(
    [switch] $Remove,
    # Also registered/removed alongside the main exe; used once to verify the
    # dump pipeline end-to-end before any rig run.
    [switch] $CrashTest
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$dumpDir = Join-Path $repo 'crash_dumps'
$wer = 'HKLM:\SOFTWARE\Microsoft\Windows\Windows Error Reporting'
$keys = @("$wer\LocalDumps\MpcPo8eUdpClosedLoop.exe")
if ($CrashTest) { $keys += "$wer\LocalDumps\crashtest.exe" }

if ($Remove) {
    foreach ($k in $keys) {
        if (Test-Path $k) { Remove-Item -Recurse -Force $k; Write-Host "Removed $k" }
        else { Write-Host "Already absent: $k" }
    }
    Remove-ItemProperty -Path $wer -Name DontShowUI -ErrorAction SilentlyContinue
    Write-Host "Removed DontShowUI. Dumps in $dumpDir are untouched."
    exit 0
}

New-Item -ItemType Directory -Force $dumpDir | Out-Null
foreach ($k in $keys) {
    New-Item -Path $k -Force | Out-Null
    New-ItemProperty -Path $k -Name DumpFolder -PropertyType ExpandString -Value $dumpDir -Force | Out-Null
    New-ItemProperty -Path $k -Name DumpType   -PropertyType DWord -Value 2  -Force | Out-Null  # 2 = full dump (heap walk needs it)
    New-ItemProperty -Path $k -Name DumpCount  -PropertyType DWord -Value 16 -Force | Out-Null
    Write-Host "Registered $k -> $dumpDir (full dumps, keep 16)"
}
# No modal WerFault dialog between crash and dump during the campaign.
New-ItemProperty -Path $wer -Name DontShowUI -PropertyType DWord -Value 1 -Force | Out-Null
Write-Host "Set DontShowUI=1 (remove with -Remove after the campaign)."

$disabled = (Get-ItemProperty $wer -Name Disabled -ErrorAction SilentlyContinue).Disabled
if ($disabled -eq 1) { Write-Host "WARNING: WER is globally Disabled=1 -- dumps will NOT be written!" -ForegroundColor Red }
else { Write-Host "WER enabled check: OK (Disabled absent or 0)." }
$svc = Get-Service WerSvc
Write-Host "WerSvc: Status=$($svc.Status) StartType=$($svc.StartType) (Manual is fine; Disabled is not)."
if ($svc.StartType -eq 'Disabled') { Write-Host "WARNING: WerSvc is Disabled -- dumps will NOT be written!" -ForegroundColor Red }
