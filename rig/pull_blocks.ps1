# pull_blocks.ps1 -- mirror new TDT blocks from the Synapse PC's tank to this PC.
#
#   .\rig\pull_blocks.ps1 -Source \\SYNAPSEPC\Tanks\BSCL20261014 -Check          # reachability + free space
#   .\rig\pull_blocks.ps1 -Source \\SYNAPSEPC\Tanks\BSCL20261014 -Watch          # copy loop, prints NEW BLOCK lines
#   .\rig\pull_blocks.ps1 -Source D:\Tanks\BSCL20261014 -Once                   # single pass
#   .\rig\pull_blocks.ps1 -Source E:\Acute_102226 -Once                               # 10-22: USB flash drive, one pass per round-trip
#   .\rig\pull_blocks.ps1 -Source \\DESKTOP-G2170R2\SynapseTanks -Tank Acute_102226 -Watch
#        -Tank <prefix>: -Source is the SHARE ROOT and the tank folder is resolved on every
#        pass as the newest directory whose name starts with <prefix> (Synapse creates
#        <Subject>-<yymmdd>-<hhmmss> at the first Record, so the name is unknown beforehand).
#        Until it exists the watcher waits and prints a dot every pass.
#
# Why (2026-10-13): placement_gate / ingest_block read the NEWEST block under
# Desktop\Data; on 09-10 blocks were hand-copied and the later ones sat on the
# rig PC for a day. The gate cycle is ~3 min, so blocks must land here within
# a minute of Synapse closing them. robocopy /XO copies only new/changed files;
# a block that is still being recorded is copied again on the next pass.

param(
    [string] $Source = '',
    [string] $Tank   = '',
    [string] $Dest   = 'C:\Users\brets\Desktop\Data\Acute_102226',
    [switch] $Check,
    [switch] $Watch,
    [switch] $Once,
    [int]    $EveryS = 20
)

if ([string]::IsNullOrWhiteSpace($Source)) {
    Write-Host "FAIL: -Source <tank folder on the Synapse PC (UNC share or mapped drive)> is required." -ForegroundColor Red
    Write-Host "      On the Synapse PC: share the tank folder (read-only is enough); here: Test-Path \\PC\share" -ForegroundColor Gray
    exit 1
}

Add-Type -TypeDefinition @"
using System; using System.Runtime.InteropServices;
public static class PullDiskFree {
    [DllImport("kernel32.dll", CharSet=CharSet.Auto, SetLastError=true)] [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool GetDiskFreeSpaceEx(string path, out ulong freeAvail, out ulong total, out ulong totalFree);
}
"@
function Free-GB($path) {
    # GetDiskFreeSpaceEx accepts UNC paths; System.IO.DriveInfo does not.
    try {
        $a = [uint64]0; $t = [uint64]0; $f = [uint64]0
        if ([PullDiskFree]::GetDiskFreeSpaceEx($path, [ref]$a, [ref]$t, [ref]$f)) { return [math]::Round($a / 1GB, 1) }
        return $null
    } catch { return $null }
}

function Block-Dirs($root) {
    # DirectoryInfo objects (not strings): the caller sorts on LastWriteTime without a second round-trip.
    if (-not (Test-Path $root)) { return @() }
    @(Get-ChildItem $root -Directory -Recurse -Depth 1 -ErrorAction SilentlyContinue |
        Where-Object { Get-ChildItem $_.FullName -Filter *.tsq -ErrorAction SilentlyContinue })
}

# With -Tank, $Source is the share root; the tank folder is the newest dir named <Tank>*.
function Resolve-Tank($root, $prefix) {
    $d = Get-ChildItem $root -Directory -Filter "$prefix*" -ErrorAction SilentlyContinue |
         Sort-Object LastWriteTime | Select-Object -Last 1
    if ($null -eq $d) { return $null }
    return $d.FullName
}

Write-Host "=== BLOCK TRANSFER ===" -ForegroundColor Cyan
Write-Host "source : $Source"
if ($Tank) { Write-Host "tank   : $Tank*  (newest match, resolved every pass)" }
Write-Host "dest   : $Dest"
if (-not (Test-Path $Source)) {
    Write-Host "FAIL: source not reachable. Share the tank folder on the Synapse PC and check the PC name / firewall / cmdkey." -ForegroundColor Red
    exit 1
}
New-Item -ItemType Directory -Force $Dest | Out-Null
$root = $Source
$src = $Source
if ($Tank) {
    $src = Resolve-Tank $root $Tank
    if ($null -eq $src) {
        Write-Host ("tank {0}* not found yet under {1} (fine before the first Record)" -f $Tank, $root) -ForegroundColor Yellow
        $others = Get-ChildItem $root -Directory -ErrorAction SilentlyContinue | Sort-Object LastWriteTime | Select-Object -Last 3
        if ($others) { Write-Host ("  newest folders on the share: " + (($others | ForEach-Object { $_.Name }) -join ', ')) -ForegroundColor Gray }
    } else {
        Write-Host "tank   : $src" -ForegroundColor Cyan
    }
}
$srcBlocks = @()
if ($src) { $srcBlocks = @(Block-Dirs $src) }
Write-Host ("source blocks: {0}   newest: {1}" -f $srcBlocks.Count, ($(if ($srcBlocks.Count) { ($srcBlocks | Sort-Object LastWriteTime | Select-Object -Last 1).Name } else { '-' })))
$fs = Free-GB $Source; $fd = Free-GB $Dest
Write-Host ("free space: source {0} GB   dest {1} GB" -f $(if ($null -ne $fs) { $fs } else { '?' }), $(if ($null -ne $fd) { $fd } else { '?' }))
if ($null -ne $fd -and $fd -lt 50) { Write-Host "WARN: under 50 GB free on the destination drive." -ForegroundColor Yellow }
if ($Check) {
    Write-Host "PASS: source reachable." -ForegroundColor Green
    exit 0
}

$known = @{}
foreach ($b in (Block-Dirs $Dest)) { $known[$b.Name] = $true }
$pass = 0
$synced = $false
$lastSrc = $null
do {
    $pass++
    $t0 = Get-Date
    if ($Tank) {
        $src = Resolve-Tank $root $Tank
        if ($null -eq $src) {
            if (-not $Watch -or $Once) { Write-Host "FAIL: tank $Tank* does not exist yet on the share." -ForegroundColor Red; exit 1 }
            Write-Host "." -NoNewline -ForegroundColor Gray
            Start-Sleep -Seconds $EveryS
            continue
        }
        if ($src -ne $lastSrc) { Write-Host ("{0} tank: {1}" -f (Get-Date -Format HH:mm:ss), $src) -ForegroundColor Cyan; $lastSrc = $src }
    }
    & robocopy $src $Dest /E /XO /R:1 /W:1 /NFL /NDL /NJH /NJS /NP /XF *.tmp | Out-Null
    $rc = $LASTEXITCODE
    if ($rc -ge 8) { Write-Host ("{0} robocopy ERROR rc={1}: source unreachable or files failed (Synapse PC asleep? share dropped?)" -f (Get-Date -Format HH:mm:ss), $rc) -ForegroundColor Red }
    foreach ($b in (Block-Dirs $Dest)) {
        $name = $b.Name
        if (-not $known.ContainsKey($name)) {
            $known[$name] = $true
            if ($synced -or $Once) {
                Write-Host ("{0} NEW BLOCK: {1}" -f (Get-Date -Format HH:mm:ss), $b.FullName) -ForegroundColor Green
            }
        }
    }
    if (-not $synced) {
        $synced = $true
        $tail = if ($Watch -and -not $Once) { ("Watching every {0} s..." -f $EveryS) } else { "" }
        Write-Host ("{0} initial sync done ({1:n0} s); {2} block(s) local. {3}" -f (Get-Date -Format HH:mm:ss), ((Get-Date) - $t0).TotalSeconds, $known.Count, $tail) -ForegroundColor Cyan
    }
    if ($Watch -and -not $Once) { Start-Sleep -Seconds $EveryS }
} while ($Watch -and -not $Once)
# robocopy exit codes below 8 mean "copied / nothing to do"; do not let them leak as a failure.
exit 0
