# 7_campaign.ps1 -- one crash-campaign run, end to end. TERMINAL B.
#
# Wraps 2_loop.ps1 (does not modify it) and adds what the campaign needs:
# exit-code capture, crash detection, automatic stim zeroing after a crash,
# event-log + crash-dump scrape, and a ledger row per run.
#
#   .\rig\7_campaign.ps1 -Run c01 -RZ2 10.1.0.100      # live campaign run
#   .\rig\7_campaign.ps1 -Run c00 -Sim                 # rehearsal, no stim
#
# Choreography per run:
#   Terminal A:  .\rig\1_server.ps1 -Run cNN -UMax 30 -Ticks 6000   (restart every run)
#   Terminal B:  this script. It pauses to let you attest the server is ready,
#                then 2_loop's own 'go' prompt is where you START THE SYNAPSE
#                RECORDING before typing go (recording-last ordering).

param(
    [Parameter(Mandatory = $true)]
    [string] $Run,

    [string] $RZ2 = '10.1.0.100',

    [switch] $Sim,

    # Skip the interactive server-ready attestation (rehearsals/automation only).
    [switch] $Yes,

    [string] $Notes = ''
)

$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

# Re-assert PATH: fresh terminal -> without this the .exe exits 53 silently.
$mr = "C:\Program Files\MATLAB\R2025b"
$env:PATH = "$mr\runtime\win64;$mr\bin\win64;$mr\extern\bin\win64;$mr\sys\os\win64;$env:PATH"

# Resolve a real python for the emergency zero-send. A bare 'python' on a fresh
# shell hits the Microsoft Store stub (exit 9009) and the zero-send silently
# does nothing -- resolve it up front and fail loudly here, not after a crash.
$py = Join-Path (Split-Path -Parent $repo) 'PythonIntanAnalysis\.venv\Scripts\python.exe'
if (-not (Test-Path $py)) {
    $cmd = Get-Command python.exe, py.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cmd) { $py = $cmd.Source }
}
if (-not (Test-Path $py)) {
    Write-Host "FAIL: no python found for the post-crash stim zeroing. Refusing to run without it." -ForegroundColor Red
    exit 1
}

$log    = "loop_run$Run.log"
$csv    = "rig_run$Run.csv"
$ledger = "campaign_ledger.csv"
$dumpDir = Join-Path $repo 'crash_dumps'

# Never reuse a label: it would trip 1_server's overwrite prompt and mix artifacts.
if ((Test-Path $log) -or (Test-Path $csv)) {
    Write-Host "FAIL: artifacts for run '$Run' already exist ($log / $csv). Pick a fresh label." -ForegroundColor Red
    exit 1
}

$preDumps = @()
if (Test-Path $dumpDir) {
    $preDumps = @(Get-ChildItem (Join-Path $dumpDir '*.dmp') -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
} else {
    Write-Host "WARN: $dumpDir does not exist -- WER LocalDumps not set up? Crashes will not produce dumps." -ForegroundColor Yellow
}

if (-not ($Yes -or $Sim)) {
    Read-Host "Terminal A: 1_server.ps1 -Run $Run started and printed 'ready'? [Enter to continue]"
}

if (-not $Sim) {
    Write-Host ""
    Write-Host ">>> At the 'go' prompt below: START THE SYNAPSE RECORDING, then type go immediately. <<<" -ForegroundColor Cyan
    Write-Host ""
}

$start = Get-Date

if ($Sim) {
    & .\rig\2_loop.ps1 -Run $Run -Sim
} else {
    & .\rig\2_loop.ps1 -Run $Run -RZ2 $RZ2
}
$exit = $LASTEXITCODE
$end = Get-Date

if (-not (Test-Path $log)) {
    Write-Host "Run '$Run' aborted before the exe launched (no $log). Nothing sent, no ledger row." -ForegroundColor Yellow
    exit 1
}

$exitHex = '0x{0:X8}' -f $exit
# Authoritative clean/crash discriminator is the Summary line, not the exit code.
$hasSummary = [bool](Select-String -Path $log -Pattern '^Summary:' -Quiet)
$crashed = -not $hasSummary

# ---- SAFETY FIRST: on any crash the exe's cleanup never ran, so the RZ2 is ----
# ---- still holding the last commanded amplitude. Zero it before anything else. ----
$zeroed = ''
if ($crashed -and -not $Sim) {
    Write-Host ""
    Write-Host "*** CRASH: STIM MAY BE RUNNING AT LAST COMMANDED AMPLITUDE. Zeroing now. ***" -ForegroundColor Red
    & $py rig/send_envelope.py --rz2 $RZ2 --count 8 --shape const --umin 0 --umax 0 `
        --secs 0.2 --lead-secs 0 --tail-secs 0 --yes --log "envelope_zero_$Run.csv"
    if ($LASTEXITCODE -eq 0) { $zeroed = 'zeroed' } else { $zeroed = 'ZERO-SEND FAILED' }
    Write-Host "*** Zero-send result: $zeroed. Now STOP the Synapse recording. ***" -ForegroundColor Red
    Write-Host ""
}

# ---- Scrape ----
$lastPacket = ''
if (Test-Path $csv) {
    $lastRow = Get-Content $csv -Tail 1
    if ($lastRow -and $lastRow -notmatch '^[A-Za-z]') { $lastPacket = ($lastRow -split ',')[0] }
}
$skipping = [bool](Select-String -Path $log -Pattern 'Skipping \d+ to position' -Quiet)

$event1000 = $null
try {
    $event1000 = Get-WinEvent -FilterHashtable @{LogName = 'Application'; Id = 1000; StartTime = $start} -ErrorAction Stop |
        Where-Object { $_.Message -match 'MpcPo8eUdpClosedLoop' } | Select-Object -First 1
} catch {}

$dumpPath = ''
if ($crashed) {
    Write-Host "Waiting up to 30 s for a crash dump..." -ForegroundColor Gray
    $deadline = (Get-Date).AddSeconds(30)
    while ((Get-Date) -lt $deadline) {
        $newDumps = @(Get-ChildItem (Join-Path $dumpDir '*.dmp') -ErrorAction SilentlyContinue |
            Where-Object { $preDumps -notcontains $_.FullName })
        if ($newDumps.Count -gt 0) { $dumpPath = $newDumps[0].FullName; break }
        Start-Sleep -Seconds 2
    }
}

# ---- Ledger ----
$yn = @{ $true = 'y'; $false = 'n' }
$noteParts = @()
if ($Notes) { $noteParts += $Notes }
if ($zeroed) { $noteParts += $zeroed }
if ($Sim) { $noteParts += 'sim' }
$noteText = ($noteParts -join '; ') -replace ',', ';'
if (-not (Test-Path $ledger)) {
    Add-Content -Path $ledger -Encoding utf8 -Value 'run,start,end,exit_hex,summary_yn,last_packet,skipping_yn,event1000_yn,dump_path,notes'
}
$row = '{0},{1:yyyy-MM-dd HH:mm:ss},{2:yyyy-MM-dd HH:mm:ss},{3},{4},{5},{6},{7},{8},{9}' -f `
    $Run, $start, $end, $exitHex, $yn[$hasSummary], $lastPacket, $yn[$skipping], $yn[[bool]$event1000], $dumpPath, $noteText
Add-Content -Path $ledger -Encoding utf8 -Value $row

# ---- Verdict ----
Write-Host ""
Write-Host "=== CAMPAIGN RUN $Run VERDICT ===" -ForegroundColor Cyan
if ($hasSummary) {
    Write-Host "  CLEAN. Exit $exitHex, last packet $lastPacket." -ForegroundColor Green
    Write-Host "  Stop the Synapse recording normally; confirm Terminal A printed 'Wrote N capture rows'." -ForegroundColor Gray
} else {
    $hint = ''
    if ($exitHex -eq '0xC0000374') { $hint = ' = heap corruption, the known fault' }
    Write-Host "  CRASH. Exit $exitHex$hint." -ForegroundColor Red
    Write-Host "  Last packet flushed to ${csv}: '$lastPacket'  Skipping line: $($yn[$skipping])" -ForegroundColor Red
    if ($event1000) { Write-Host "  Event 1000 captured at $($event1000.TimeCreated)." -ForegroundColor Red }
    else { Write-Host "  No Application event 1000 found (a kill, not a fault?)." -ForegroundColor Yellow }
    if ($dumpPath) { Write-Host "  Dump: $dumpPath" -ForegroundColor Red }
    elseif ($event1000) { Write-Host "  WARNING: fault event but NO DUMP -- debug WER before the next run." -ForegroundColor Yellow }
}
Write-Host "  Ledger row appended to $ledger." -ForegroundColor Gray
Write-Host "  Next: restart Terminal A with the next label before the next campaign run." -ForegroundColor Cyan
exit 0  # the wrapper did its job either way; the ledger records the run's outcome
