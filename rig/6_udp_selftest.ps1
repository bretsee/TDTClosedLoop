# 6_udp_selftest.ps1 -- prove the UDP send path works, with NO RZ2 attached.
#
#   .\rig\6_udp_selftest.ps1                 # all local tests
#   .\rig\6_udp_selftest.ps1 -RZ2 10.1.0.100 # also run the live-target test
#
# Runs the REAL MpcPo8eUdpClosedLoop.exe and the REAL rig/send_envelope.py against
# rig/fake_rz2.py, which speaks the exact TDTUDP.h protocol. If these pass, the
# code and the wire format are proven and any remaining failure is the network or
# the RZ2 itself.
#
# Test D is the important one: it demonstrates that sending to an unreachable
# target REPORTS SUCCESS. That is the failure mode that makes this bug invisible.

param(
    [string]$RZ2 = "",
    [string]$Python = "",
    [switch]$LiveStim,          # allow test E2 to send a real data packet to the RZ2
    [double]$LiveValue = 0.0    # value that packet carries; 0 = a zero command
)

$ErrorActionPreference = 'Continue'
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

if (-not $Python) {
    $cand = @(
        "$repo\..\PythonIntanAnalysis\.venv\Scripts\python.exe",
        "python"
    )
    foreach ($c in $cand) {
        $r = Get-Command $c -ErrorAction SilentlyContinue
        if ($r) { $Python = $r.Source; break }
        if (Test-Path $c) { $Python = (Resolve-Path $c).Path; break }
    }
}
if (-not $Python) { Write-Host "FAIL: no python found." -ForegroundColor Red; exit 1 }
Write-Host "python: $Python" -ForegroundColor DarkGray

# The .exe needs the MATLAB runtime on PATH or it exits 53 printing NOTHING AT ALL,
# which reads exactly like "the UDP send silently did nothing". Same as 0_preflight.
$mr = "C:\Program Files\MATLAB\R2025b"
if (Test-Path "$mr\bin\matlab.exe") {
    $env:PATH = "$mr\runtime\win64;$mr\bin\win64;$mr\extern\bin\win64;$mr\sys\os\win64;$env:PATH"
    Write-Host "MATLAB runtime on PATH" -ForegroundColor DarkGray
} else {
    Write-Host "WARN: MATLAB runtime not found at $mr; the .exe tests may exit 53." -ForegroundColor Yellow
}

$exe = Join-Path $repo 'MpcPo8eUdpClosedLoop.exe'
$results = [ordered]@{}

function Start-FakeRz2($bindAddr, $seconds, $logPath, $extra = @()) {
    $args = @("$repo\rig\fake_rz2.py", "--bind", $bindAddr, "--seconds", "$seconds") + $extra
    return Start-Process -FilePath $Python -ArgumentList $args -PassThru `
                         -RedirectStandardOutput $logPath -NoNewWindow
}

function Show-Log($path, $label) {
    Write-Host "  --- $label ---" -ForegroundColor DarkGray
    if (Test-Path $path) { Get-Content $path | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray } }
}

# Judge by the emulator's own verdict line, not by Process.ExitCode: with
# Start-Process -PassThru the ExitCode property is not reliably populated after
# WaitForExit(ms), which silently turns passes into failures.
function Test-Verdict($path) {
    if (-not (Test-Path $path)) { return $false }
    return ((Get-Content $path | Select-String -Pattern '^PASS: \d+ DATA packet') -ne $null)
}

# ===========================================================================
Write-Host ""
Write-Host "TEST A -- fake RZ2 binds the port and decodes a hand-built packet" -ForegroundColor White
# Proves the emulator itself is trustworthy before anything is judged against it.
$logA = "$env:TEMP\selftest_A.log"
$pA = Start-FakeRz2 "127.0.0.1" 6 $logA
Start-Sleep -Milliseconds 700
& $Python -c @"
import socket, struct
p = bytes([0x55,0xAA,0x00,3]) + struct.pack('>3f', 1.0, -2.5, 40.0)
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.sendto(p, ('127.0.0.1', 22022))
s.sendto(bytes([0x55,0xAA,0x01,0]), ('127.0.0.1', 22022))
print('sent 1 DATA + 1 GET_VERSION')
"@
$pA.WaitForExit(20000) | Out-Null
Show-Log $logA "fake RZ2"
$results['A hand-built packet decoded'] = (Test-Verdict $logA)

# ===========================================================================
# NOTE on the .exe test modes: only --test-udp-once returns. --test-udp and
# --test-udp-words are `while(true)` loops that say "Press Ctrl+C to stop", so
# they must be started detached and killed on a timer.
function Invoke-ExeForSeconds($exeArgs, $seconds, $outPath) {
    $p = Start-Process -FilePath $exe -ArgumentList $exeArgs -PassThru -NoNewWindow `
                       -RedirectStandardOutput $outPath
    Start-Sleep -Seconds $seconds
    if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Milliseconds 300
    return (Get-Content $outPath -ErrorAction SilentlyContinue)
}

Write-Host ""
Write-Host "TEST B1 -- .exe --test-udp-once  (openSocket + setRemoteIp + sendUDPPacket)" -ForegroundColor White
if (-not (Test-Path $exe)) {
    Write-Host "  SKIP: $exe not present." -ForegroundColor Yellow
    $results['B1 .exe one-shot'] = $null
    $results['B2 .exe checkRZ handshake'] = $null
    $results['B3 .exe sendUDPPacketWords'] = $null
} else {
    $logB1 = "$env:TEMP\selftest_B1.log"
    $pB1 = Start-FakeRz2 "127.0.0.1" 8 $logB1 @("--expect-packets", "1")
    Start-Sleep -Milliseconds 700
    $outB1 = & $exe --test-udp-once 127.0.0.1 1234.5 2>&1
    $outB1 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
    $pB1.WaitForExit(20000) | Out-Null
    Show-Log $logB1 "fake RZ2"
    $results['B1 .exe one-shot'] = (Test-Verdict $logB1)

    # -----------------------------------------------------------------------
    Write-Host ""
    Write-Host "TEST B2 -- .exe --test-udp  (adds the checkRZ GET_VERSION handshake)" -ForegroundColor White
    $logB2 = "$env:TEMP\selftest_B2.log"
    $exeB2 = "$env:TEMP\selftest_B2_exe.log"
    $pB2 = Start-FakeRz2 "127.0.0.1" 9 $logB2 @("--expect-packets", "5")
    Start-Sleep -Milliseconds 700
    $outB2 = Invoke-ExeForSeconds @('--test-udp','127.0.0.1','1234.5','1','20') 4 $exeB2
    $outB2 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
    $pB2.WaitForExit(20000) | Out-Null
    Show-Log $logB2 "fake RZ2"
    $ack = (($outB2 | Select-String -Pattern 'checkRZ: ACK received') -ne $null)
    if ($ack) { Write-Host "  checkRZ handshake succeeded (RZ2 identity confirmed)." -ForegroundColor Green }
    else      { Write-Host "  checkRZ did NOT get an ACK." -ForegroundColor Red }
    $results['B2 .exe checkRZ handshake'] = ($ack -and (Test-Verdict $logB2))

    # -----------------------------------------------------------------------
    Write-Host ""
    Write-Host "TEST B3 -- .exe --test-udp-words  (the production sendUDPPacketWords path)" -ForegroundColor White
    $logB3 = "$env:TEMP\selftest_B3.log"
    $exeB3 = "$env:TEMP\selftest_B3_exe.log"
    $pB3 = Start-FakeRz2 "127.0.0.1" 9 $logB3 @("--expect-packets", "10")
    Start-Sleep -Milliseconds 700
    $outB3 = Invoke-ExeForSeconds @('--test-udp-words','127.0.0.1','16','5','5','50') 4 $exeB3
    $outB3 | Select-Object -First 6 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
    $pB3.WaitForExit(20000) | Out-Null
    Show-Log $logB3 "fake RZ2"
    $results['B3 .exe sendUDPPacketWords'] = (Test-Verdict $logB3)
}

# ===========================================================================
Write-Host ""
Write-Host "TEST C -- rig/send_envelope.py against the fake RZ2" -ForegroundColor White
# The stim-envelope path used for the 'was stim actually delivered' check.
$logC = "$env:TEMP\selftest_C.log"
$csvC = "$env:TEMP\selftest_C_rx.csv"
$pC = Start-FakeRz2 "127.0.0.1" 12 $logC @("--expect-packets", "50", "--csv", $csvC, "--quiet")
Start-Sleep -Milliseconds 700
& $Python "$repo\rig\send_envelope.py" --rz2 127.0.0.1 --channels 3 --umax 10 `
          --shape saw --secs 3 --yes 2>&1 | Select-Object -Last 12 |
          ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
$pC.WaitForExit(30000) | Out-Null
Show-Log $logC "fake RZ2"
$results['C envelope -> fake RZ2'] = (Test-Verdict $logC)

# ===========================================================================
Write-Host ""
Write-Host "TEST D -- send to an UNREACHABLE target and watch it 'succeed'" -ForegroundColor White
Write-Host "  This is the silent failure. Nothing receives these packets." -ForegroundColor Yellow
& $Python -c @"
import socket, struct, sys
target = ('10.255.255.254', 22022)   # routable via default gw, nothing there
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    s.connect(target)
except OSError as e:
    print('connect() failed:', e); sys.exit(0)
p = bytes([0x55,0xAA,0x00,1]) + struct.pack('>f', 40.0)
n = s.send(p)
print(f'send() returned {n} bytes to {target[0]}:{target[1]} -- REPORTED SUCCESS')
print('local socket bound to:', s.getsockname())
print('No RZ2 exists there. UDP cannot tell you that. This is exactly what the')
print('closed loop was doing when the PC had no address on the RZ2 subnet.')
"@
$results['D silent-failure demonstrated'] = $true

# ===========================================================================
if ($RZ2) {
    Write-Host ""
    Write-Host "TEST E -- live target $RZ2 (needs the RZ2 powered and cabled)" -ForegroundColor White
    & "$repo\rig\net_diag.ps1" -RZ2 $RZ2
    $diagOk = ($LASTEXITCODE -eq 0)
    if (-not $diagOk) {
        Write-Host "  SKIP send: fix the network first." -ForegroundColor Yellow
        $results['E1 live RZ2 answers GET_VERSION'] = $false
    } else {
        # E1: GET_VERSION only. No data packet is sent, so this cannot drive stim
        # under any circuit -- safe with an animal connected.
        $outE1 = & $Python "$repo\rig\find_rz2.py" --hosts $RZ2 --wait 3 2>&1
        $outE1 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
        $results['E1 live RZ2 answers GET_VERSION'] = (($outE1 | Select-String 'VALID ACK') -ne $null)

        # E2: one DATA packet carrying 0.0 -- a zero command. Still a real data
        # packet, so it is gated behind -LiveStim rather than run by default.
        if (Test-Path $exe) {
            if ($LiveStim) {
                Write-Host ""
                Write-Host "  -LiveStim: sending ONE data packet, value $LiveValue" -ForegroundColor Yellow
                $outE2 = & $exe --test-udp-once $RZ2 $LiveValue 2>&1
                $outE2 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
                $results['E2 live one-shot data packet'] =
                    (($outE2 | Select-String 'sendUDPPacket returned: 8') -ne $null)
            } else {
                Write-Host ""
                Write-Host "  E2 skipped: sends a real data packet to the RZ2." -ForegroundColor Yellow
                Write-Host "     Add -LiveStim once you are satisfied nothing is connected" -ForegroundColor Yellow
                Write-Host "     that a stray command could drive (default value 0)." -ForegroundColor Yellow
                $results['E2 live one-shot data packet'] = $null
            }
        }
    }
}

# ===========================================================================
Write-Host ""
Write-Host "=== SELF-TEST SUMMARY ===" -ForegroundColor Cyan
$bad = 0
foreach ($k in $results.Keys) {
    $v = $results[$k]
    if ($v -eq $null)      { Write-Host ("  SKIP  {0}" -f $k) -ForegroundColor Yellow }
    elseif ($v)            { Write-Host ("  PASS  {0}" -f $k) -ForegroundColor Green }
    else                   { Write-Host ("  FAIL  {0}" -f $k) -ForegroundColor Red; $bad++ }
}
Write-Host ""
if ($bad -eq 0) {
    Write-Host "Send path and wire format are proven locally." -ForegroundColor Green
    Write-Host "Any remaining failure is the network or the RZ2, not this code." -ForegroundColor Green
} else {
    Write-Host "$bad test(s) failed -- the fault is in the code path, not the network." -ForegroundColor Red
}
exit $bad
