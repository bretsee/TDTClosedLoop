# set_rig_ip.ps1 -- put this PC on the RZ2's subnet, or put it back.
# Requires an ADMINISTRATOR PowerShell. Prints the plan and does nothing without -Apply.
#
#   .\rig\set_rig_ip.ps1                       # show what it WOULD do
#   .\rig\set_rig_ip.ps1 -Apply                # set Ethernet to 10.1.0.1/24
#   .\rig\set_rig_ip.ps1 -Apply -IP 10.1.0.2   # if the RZ2 itself is 10.1.0.1
#   .\rig\set_rig_ip.ps1 -Revert -Apply        # back to DHCP
#
# Deliberately sets NO default gateway on this NIC. The rig segment must not
# become the default route, or it will take over internet traffic from Wi-Fi.

param(
    [string]$Nic     = "",          # default: auto-detect (see Resolve-RigNic)
    [string]$IP      = "10.1.0.1",
    [int]   $Prefix  = 24,
    [switch]$Revert,
    [switch]$Apply
)
# Auto-detect the rig NIC when none is given (2026-10-12: onboard Realtek is dead,
# the RZ2 now hangs off a USB adapter named 'Ethernet 2'): prefer the adapter that
# already holds an address on the RZ2 /24, else the only physical wired adapter
# whose link is Up.
function Resolve-RigNic([string]$Given, [string]$Subnet) {
    if ($Given) { return $Given }
    $wired = Get-NetAdapter -Physical -ErrorAction SilentlyContinue |
        Where-Object { $_.PhysicalMediaType -match '802.3' -or $_.InterfaceDescription -match 'Ethernet' } |
        Where-Object { $_.InterfaceDescription -notmatch 'Wi-?Fi|Wireless|Bluetooth' }
    $onSubnet = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -like "$Subnet.*" -and ($wired.Name -contains $_.InterfaceAlias) }
    if ($onSubnet) { return @($onSubnet)[0].InterfaceAlias }
    $up = @($wired | Where-Object { $_.Status -eq 'Up' })
    if ($up.Count -ge 1) { return $up[0].Name }
    if ($wired) { return @($wired)[0].Name }
    return "Ethernet"
}
$Nic = Resolve-RigNic $Nic ($IP -replace '\.\d+$', '')


$ErrorActionPreference = 'Stop'

$admin = ([Security.Principal.WindowsPrincipal] `
          [Security.Principal.WindowsIdentity]::GetCurrent()
         ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

$ad = Get-NetAdapter -Name $Nic -ErrorAction SilentlyContinue
if (-not $ad) {
    Write-Host "FAIL: no adapter named '$Nic'." -ForegroundColor Red
    Get-NetAdapter | Format-Table Name, Status, InterfaceDescription -AutoSize
    exit 1
}

Write-Host "=== CURRENT ===" -ForegroundColor Cyan
Write-Host "  adapter : $($ad.Name)  [$($ad.Status)]  $($ad.InterfaceDescription)"
Get-NetIPAddress -InterfaceAlias $Nic -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    ForEach-Object { Write-Host "  address : $($_.IPAddress)/$($_.PrefixLength)  ($($_.PrefixOrigin))" }
$cfgNow = Get-NetIPInterface -InterfaceAlias $Nic -AddressFamily IPv4
Write-Host "  DHCP    : $($cfgNow.Dhcp)"
Write-Host ""

Write-Host "=== PLAN ===" -ForegroundColor Cyan
if ($Revert) {
    Write-Host "  Remove any static IPv4 address and route from '$Nic', re-enable DHCP."
} else {
    Write-Host "  Set '$Nic' to STATIC $IP/$Prefix with NO default gateway."
    Write-Host "  Leaves Wi-Fi and its default route untouched (internet keeps working)."
}
Write-Host ""

if (-not $Apply) {
    Write-Host "Dry run. Re-run with -Apply (as Administrator) to make the change." -ForegroundColor Yellow
    exit 0
}
if (-not $admin) {
    Write-Host "FAIL: -Apply needs an Administrator PowerShell." -ForegroundColor Red
    Write-Host "      Right-click PowerShell -> Run as administrator, then re-run." -ForegroundColor Yellow
    exit 1
}

# Clear whatever is there first; both cmdlets are noisy when nothing matches.
try { Remove-NetIPAddress -InterfaceAlias $Nic -AddressFamily IPv4 -Confirm:$false -ErrorAction Stop } catch {}
try { Remove-NetRoute -InterfaceAlias $Nic -AddressFamily IPv4 -Confirm:$false -ErrorAction Stop } catch {}

if ($Revert) {
    Set-NetIPInterface -InterfaceAlias $Nic -AddressFamily IPv4 -Dhcp Enabled
    Write-Host "Reverted '$Nic' to DHCP." -ForegroundColor Green
} else {
    Set-NetIPInterface -InterfaceAlias $Nic -AddressFamily IPv4 -Dhcp Disabled
    New-NetIPAddress -InterfaceAlias $Nic -AddressFamily IPv4 `
                     -IPAddress $IP -PrefixLength $Prefix | Out-Null
    Write-Host "Set '$Nic' to $IP/$Prefix (no gateway)." -ForegroundColor Green
}

Write-Host ""
Write-Host "=== NOW ===" -ForegroundColor Cyan
Get-NetIPAddress -InterfaceAlias $Nic -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Format-Table IPAddress, PrefixLength, PrefixOrigin, AddressState -AutoSize
Write-Host "Next: .\rig\net_diag.ps1" -ForegroundColor Cyan
