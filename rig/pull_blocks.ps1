# pull_blocks.ps1 -- mirror new TDT blocks from the Synapse PC's tank to this PC.
#
#   .\rig\pull_blocks.ps1 -Source \\SYNAPSEPC\Tanks\BSCL20261014 -Check          # reachability + free space
#   .\rig\pull_blocks.ps1 -Source \\SYNAPSEPC\Tanks\BSCL20261014 -Watch          # copy loop, prints NEW BLOCK lines
#   .\rig\pull_blocks.ps1 -Source D:\Tanks\BSCL20261014 -Once                   # single pass
#
# Why (2026-10-13): placement_gate / ingest_block read the NEWEST block under
# Desktop\Data; on 09-10 blocks were hand-copied and the later ones sat on the
# rig PC for a day. The gate cycle is ~3 min, so blocks must land here within
# a minute of Synapse closing them. robocopy /XO copies only new/changed files;
# a block that is still being recorded is copied again on the next pass.

param(
    [string] $Source = '',
    [string] $Dest   = 'C:\Users\brets\Desktop\Data\Acute3',
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

function Free-GB($path) {
    try {
        if ($path -like '\\*') {
            $root = ($path -split '\\')[0..3] -join '\'
            $d = New-Object System.IO.DriveInfo($root)
        } else {
            $d = New-Object System.IO.DriveInfo((Split-Path -Qualifier $path))
        }
        return [math]::Round($d.AvailableFreeSpace / 1GB, 1)
    } catch { return $null }
}

function Block-Dirs($root) {
    if (-not (Test-Path $root)) { return @() }
    Get-ChildItem $root -Directory -Recurse -Depth 1 -ErrorAction SilentlyContinue |
        Where-Object { Get-ChildItem $_.FullName -Filter *.tsq -ErrorAction SilentlyContinue } |
        Select-Object -ExpandProperty FullName
}

Write-Host "=== BLOCK TRANSFER ===" -ForegroundColor Cyan
Write-Host "source : $Source"
Write-Host "dest   : $Dest"
if (-not (Test-Path $Source)) {
    Write-Host "FAIL: source not reachable. Share the tank folder on the Synapse PC and check the PC name / firewall." -ForegroundColor Red
    exit 1
}
New-Item -ItemType Directory -Force $Dest | Out-Null
$srcBlocks = @(Block-Dirs $Source)
Write-Host ("source blocks: {0}   newest: {1}" -f $srcBlocks.Count, ($(if ($srcBlocks.Count) { Split-Path -Leaf ($srcBlocks | Sort-Object { (Get-Item $_).LastWriteTime } | Select-Object -Last 1) } else { '-' })))
$fs = Free-GB $Source; $fd = Free-GB $Dest
Write-Host ("free space: source {0} GB   dest {1} GB" -f $(if ($null -ne $fs) { $fs } else { '?' }), $(if ($null -ne $fd) { $fd } else { '?' }))
if ($null -ne $fd -and $fd -lt 50) { Write-Host "WARN: under 50 GB free on the destination drive." -ForegroundColor Yellow }
if ($Check) {
    Write-Host "PASS: source reachable." -ForegroundColor Green
    exit 0
}

$known = @{}
foreach ($b in (Block-Dirs $Dest)) { $known[(Split-Path -Leaf $b)] = $true }
$pass = 0
do {
    $pass++
    $t0 = Get-Date
    & robocopy $Source $Dest /E /XO /R:1 /W:1 /NFL /NDL /NJH /NJS /NP /XF *.tmp | Out-Null
    $rc = $LASTEXITCODE
    if ($rc -ge 8) { Write-Host ("{0} robocopy ERROR rc={1}" -f (Get-Date -Format HH:mm:ss), $rc) -ForegroundColor Red }
    foreach ($b in (Block-Dirs $Dest)) {
        $name = Split-Path -Leaf $b
        if (-not $known.ContainsKey($name)) {
            $known[$name] = $true
            if ($pass -gt 1 -or $Once) {
                Write-Host ("{0} NEW BLOCK: {1}" -f (Get-Date -Format HH:mm:ss), $b) -ForegroundColor Green
            }
        }
    }
    if ($pass -eq 1) { Write-Host ("{0} initial sync done ({1:n0} s); {2} block(s) local. Watching every {3} s..." -f (Get-Date -Format HH:mm:ss), ((Get-Date) - $t0).TotalSeconds, $known.Count, $EveryS) -ForegroundColor Cyan }
    if ($Watch -and -not $Once) { Start-Sleep -Seconds $EveryS }
} while ($Watch -and -not $Once)
