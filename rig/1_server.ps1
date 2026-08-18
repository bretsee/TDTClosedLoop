# 1_server.ps1 -- start the open-loop capture server. TERMINAL 2, FOREGROUND.
#
# This BLOCKS. That is intentional: MATLAB must run in the foreground of its own
# terminal. Start-Process and Start-Job both silently produce nothing here
# (bin\matlab.exe is a launcher that detaches), and at the rig you want to see
# the server's output anyway.
#
#   .\rig\1_server.ps1 -Run 1 -UMax 10 -Channels 3
#   .\rig\1_server.ps1 -Run 2 -UMax 10 -Channels 3 -Seed 777      # independent record
#   .\rig\1_server.ps1 -Run 3 -UMax 10 -Channels (1..8) -Ticks 12000
#
# It prints the excitation summary BEFORE the first packet. Read the active
# channel list and the u range and confirm both are what you intended -- that
# print is the last checkpoint before current goes into tissue.

param(
    # Label for this run. Everything downstream is named from it.
    [string]   $Run       = '1',

    # UPPER STIM AMPLITUDE. Set from known-safe limits for THIS preparation.
    # This is the pulse-amplitude envelope, one amplitude per 100 Hz control
    # point -- the same quantity as the acute stimblock CSVs. It is a real
    # charge/compliance ceiling, not a placeholder. Nothing in this code knows
    # anything about tissue safety.
    [double]   $UMax      = 10,
    [double]   $UMin      = 0,

    # Which stim channels are allowed to move. Everything else is held at UMin.
    # Start with ONE. Default $null = all channels (the old behaviour).
    [int[]]    $Channels  = $null,

    [int]      $Ticks     = 6000,        # 6000 = 60 s at 100 Hz
    [ValidateSet('prbs','multilevel','steps','chirp','impulse')]
    [string]   $Kind      = 'prbs',
    [int]      $ClockTicks = 5,          # do NOT use 1 -- that identifies noise
    [int]      $Seed      = 12345,

    # Impulse-kind options (ignored for other kinds). -PulseAmps sets the cycled
    # amplitude ladder; -GapTicks the deterministic quiet gap between pulses;
    # -GapJitterMs > 0 adds a per-pulse geometric random gap with that MEAN (in
    # ms, rounded to 10 ms ticks) so the train carries no fixed rhythm. The
    # jitter is strictly positive: it only ever lengthens gaps, never shortens.
    [double[]] $PulseAmps  = $null,
    [int]      $GapTicks   = 50,
    [double]   $GapJitterMs = 0,

    # Stim outputs = BIPOLAR PAIRS. 8 pairs drive 16 electrodes; the RZ2 receive
    # gizmo reads exactly 8 words and discards anything beyond that.
    [int]      $Outputs   = 8
)

$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
$mr = "C:\Program Files\MATLAB\R2025b"

$capture = "capture_rig_run$Run.csv"
$latlog  = "server_lat_run$Run.csv"
$srvlog  = "matlab_server_run$Run.log"

if (Test-Path $capture) {
    Write-Host "WARNING: $capture already exists and WILL BE OVERWRITTEN." -ForegroundColor Yellow
    Write-Host "         Use a different -Run label to keep it." -ForegroundColor Yellow
    $answer = Read-Host "         Type 'yes' to overwrite"
    if ($answer -ne 'yes') { Write-Host "Aborted."; exit 1 }
}

# Build the activeChannels clause only when channels were specified, so the
# default path stays byte-identical to what was rehearsed.
if ($null -ne $Channels -and $Channels.Count -gt 0) {
    $chanList   = ($Channels -join ' ')
    # {[...]}: cell-wrap so struct() stores the vector in ONE struct instead of
    # expanding into a struct array (which silently breaks the server config).
    $activeExpr = ",'activeChannels',{[$chanList]}"
    Write-Host "Active stim channels: $chanList" -ForegroundColor Cyan
} else {
    $activeExpr = ""
    Write-Host "Active stim channels: ALL $Outputs (no -Channels given)" -ForegroundColor Yellow
}

# Impulse-only options, emitted only when they differ from the make_excitation
# defaults so every previously rehearsed command line stays byte-identical.
$impExpr = ""
if ($Kind -eq 'impulse') {
    if ($null -ne $PulseAmps -and $PulseAmps.Count -gt 0) {
        $ampList = ($PulseAmps -join ' ')
        $impExpr += ",'pulseAmps',{[$ampList]}"
        Write-Host "Impulse amplitudes: [$ampList]" -ForegroundColor Cyan
    }
    if ($GapTicks -ne 50) {
        $impExpr += ",'gapTicks',$GapTicks"
    }
    if ($GapJitterMs -gt 0) {
        $jitterTicks = [math]::Round($GapJitterMs / 10)
        if ($jitterTicks -lt 1) { $jitterTicks = 1 }
        $impExpr += ",'gapJitterMeanTicks',$jitterTicks"
        Write-Host "Gap jitter: geometric, mean $($jitterTicks*10) ms on top of the $($GapTicks*10) ms base gap" -ForegroundColor Cyan
    }
}

Write-Host "Excitation: $Kind, u in [$UMin $UMax], $Ticks ticks ($($Ticks/100) s), clockTicks=$ClockTicks, seed=$Seed" -ForegroundColor Cyan
Write-Host "Capture -> $capture" -ForegroundColor Cyan
Write-Host "MATLAB takes ~30 s to start. Wait for 'ready' before running 2_loop.ps1." -ForegroundColor Gray
Write-Host ""

$code = @"
cd('$($repo -replace '\\','/')');
cfg = struct('mode','openloop','requestPort',31000,'replyPort',31001, ...
             'outputCount',$Outputs,'maxPackets',$Ticks, ...
             'captureFile','$capture','logFile','$latlog');
cfg.excitation = struct('kind','$Kind','clockTicks',$ClockTicks, ...
                        'uMin',$UMin,'uMax',$UMax,'seed',$Seed$activeExpr$impExpr);
matlab_controller_server(cfg)
"@

# Tee so the console stays live AND a log survives for the notebook. -batch
# writes errors to stderr, so 2>&1 is mandatory: without it a failing server is
# indistinguishable from a silent one.
& "$mr\bin\matlab.exe" -batch $code 2>&1 | Tee-Object -FilePath $srvlog
