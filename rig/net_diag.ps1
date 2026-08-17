# net_diag.ps1 -- read-only diagnosis of the PC -> RZ2 network path.
# Changes nothing. Run this before blaming the code.
#
#   .\rig\net_diag.ps1                     # assumes RZ2 at 10.1.0.100
#   .\rig\net_diag.ps1 -RZ2 10.1.0.1
#   .\rig\net_diag.ps1 -RZ2 10.1.0.100 -Nic Ethernet
#
# The failure this is built to catch: UDP sendto() SUCCEEDS even when the packet
# is handed to the wrong interface. If the PC has no address on the RZ2's subnet,
# Windows routes RZ2-bound traffic out the default gateway (the Wi-Fi/internet
# router), which silently discards it. Every layer above reports success and the
# RZ2 receives nothing.

param(
    [string]$RZ2 = "10.1.0.100",
    [string]$Nic = "Ethernet"
)

$ErrorActionPreference = 'Continue'
$fail = 0
$warn = 0

function Say($msg, $color = 'Gray') { Write-Host "  $msg" -ForegroundColor $color }

Write-Host "=== RZ2 NETWORK PATH DIAGNOSIS ===" -ForegroundColor Cyan
Write-Host "Target RZ2: $RZ2   Expected NIC: $Nic" -ForegroundColor Cyan
Write-Host ""

# --- 1. Does the NIC exist and is the cable live? ---------------------------
Write-Host "1. Physical link" -ForegroundColor White
$ad = Get-NetAdapter -Name $Nic -ErrorAction SilentlyContinue
if (-not $ad) {
    Say "FAIL: no adapter named '$Nic'. Adapters present:" 'Red'
    Get-NetAdapter | ForEach-Object { Say "       $($_.Name)  [$($_.Status)]  $($_.InterfaceDescription)" 'DarkGray' }
    $fail++
} else {
    Say "adapter : $($ad.InterfaceDescription)"
    Say "status  : $($ad.Status)   media: $($ad.MediaConnectionState)   speed: $($ad.LinkSpeed)"
    if ($ad.Status -ne 'Up') {
        Say "FAIL: link is DOWN. Nothing can leave this port." 'Red'
        Say "      Check: cable seated both ends, RZ2 powered on, correct RZ2 port" 'Yellow'
        Say "      (the UDP interface is on the RZ2 gigabit card, not the optical port)." 'Yellow'
        $fail++
    } else {
        Say "PASS: link is up." 'Green'
    }
}
Write-Host ""

# --- 2. Does this PC have an address on the RZ2's subnet? -------------------
Write-Host "2. Local IP address on the RZ2 subnet" -ForegroundColor White
$rzParts = $RZ2.Split('.')
$rzPrefix24 = "$($rzParts[0]).$($rzParts[1]).$($rzParts[2])."
$all = Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -ne '127.0.0.1' }
foreach ($a in ($all | Sort-Object InterfaceAlias)) {
    $flag = ''
    if ($a.IPAddress.StartsWith('169.254.')) { $flag = '   <-- APIPA: DHCP found no server' }
    if ($a.IPAddress.StartsWith($rzPrefix24)) { $flag = '   <-- on the RZ2 subnet' }
    Say ("{0,-28} {1,-16} /{2}  {3}{4}" -f $a.InterfaceAlias, $a.IPAddress, $a.PrefixLength, $a.PrefixOrigin, $flag)
}
$onSubnet = $all | Where-Object { $_.IPAddress.StartsWith($rzPrefix24) -and $_.PrefixLength -eq 24 }
if (-not $onSubnet) {
    Say "FAIL: no interface holds a /24 address on ${rzPrefix24}0/24." 'Red'
    Say "      Without one there is no on-link route to the RZ2." 'Yellow'
    $fail++
} else {
    Say "PASS: $($onSubnet[0].InterfaceAlias) has $($onSubnet[0].IPAddress)/24." 'Green'
    if ($onSubnet[0].IPAddress -eq $RZ2) {
        Say "FAIL: this PC's address IS the target address. One of them is wrong." 'Red'
        $fail++
    }
}
Write-Host ""

# --- 3. Where would a packet to the RZ2 actually go? ------------------------
Write-Host "3. Route a packet to $RZ2 would take" -ForegroundColor White
$route = $null
try { $route = Find-NetRoute -RemoteIPAddress $RZ2 -ErrorAction Stop } catch {}
if (-not $route) {
    Say "FAIL: no route at all to $RZ2." 'Red'
    $fail++
} else {
    $src = ($route | Where-Object { $_.IPAddress }        | Select-Object -First 1)
    $rt  = ($route | Where-Object { $_.DestinationPrefix } | Select-Object -First 1)
    Say "source address : $($src.IPAddress)"
    Say "egress adapter : $($src.InterfaceAlias)"
    Say "matched route  : $($rt.DestinationPrefix)  next hop: $($rt.NextHop)"
    if ($rt.DestinationPrefix -eq '0.0.0.0/0') {
        Say "FAIL: falling through to the DEFAULT GATEWAY ($($rt.NextHop))." 'Red'
        Say "      Packets are going to your internet router, which drops them." 'Yellow'
        Say "      sendto() will still report success. This is the silent failure." 'Yellow'
        $fail++
    } elseif ($src.InterfaceAlias -ne $Nic) {
        Say "WARN: leaving via '$($src.InterfaceAlias)', not '$Nic'." 'Yellow'
        $warn++
    } else {
        Say "PASS: on-link via $Nic, no gateway involved." 'Green'
    }
}
Write-Host ""

# --- 4. Is the RZ2 answering at layer 2/3? ---------------------------------
Write-Host "4. Reachability" -ForegroundColor White
$ping = Test-Connection -ComputerName $RZ2 -Count 2 -Quiet -ErrorAction SilentlyContinue
if ($ping) {
    Say "PASS: $RZ2 answers ICMP." 'Green'
} else {
    Say "no ICMP reply from $RZ2." 'Yellow'
    Say "      Not conclusive -- many TDT UDP interfaces never answer ping." 'DarkGray'
    Say "      The ARP entry below is the better evidence." 'DarkGray'
    $warn++
}
$arp = Get-NetNeighbor -IPAddress $RZ2 -ErrorAction SilentlyContinue
if ($arp) {
    foreach ($n in $arp) { Say "ARP: $($n.IPAddress) -> $($n.LinkLayerAddress)  [$($n.State)]" }
    if ($arp | Where-Object { $_.State -in 'Reachable','Stale','Permanent' }) {
        Say "PASS: the RZ2 answered ARP -- it is physically on this segment." 'Green'
    } else {
        Say "WARN: ARP entry is $($arp[0].State) -- no hardware reply yet." 'Yellow'
        $warn++
    }
} else {
    Say "no ARP entry for $RZ2 (nothing has replied at layer 2)." 'Yellow'
    $warn++
}
Write-Host ""

# --- 5. Firewall on outbound UDP 22022 -------------------------------------
Write-Host "5. Firewall" -ForegroundColor White
$profiles = Get-NetFirewallProfile
foreach ($p in $profiles) {
    Say ("{0,-9} enabled={1,-5} outbound default={2}" -f $p.Name, $p.Enabled, $p.DefaultOutboundAction)
}
Say "Windows allows outbound UDP by default; inbound is what gets blocked." 'DarkGray'
Say "That matters for the RZ2's REPLIES (checkRZ ACK), not for stim commands." 'DarkGray'
Write-Host ""

# --- verdict ---------------------------------------------------------------
Write-Host "=== VERDICT ===" -ForegroundColor Cyan
if ($fail -gt 0) {
    Write-Host "  $fail blocking problem(s), $warn warning(s)." -ForegroundColor Red
    Write-Host ""
    Write-Host "  Most likely fix -- give this PC a static address on the RZ2 subnet:" -ForegroundColor Yellow
    Write-Host "      .\rig\set_rig_ip.ps1 -Apply            (run as Administrator)" -ForegroundColor Yellow
    Write-Host "  Wi-Fi internet keeps working: it is on a different subnet and keeps" -ForegroundColor DarkGray
    Write-Host "  the default route. The Ethernet route is on-link only." -ForegroundColor DarkGray
    exit 1
} elseif ($warn -gt 0) {
    Write-Host "  No blocking problems, $warn warning(s). Path looks usable." -ForegroundColor Yellow
    exit 0
} else {
    Write-Host "  PASS: the path to $RZ2 is correctly configured." -ForegroundColor Green
    exit 0
}
