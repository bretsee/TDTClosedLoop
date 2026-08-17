# pageheap.ps1 -- toggle full PageHeap for MpcPo8eUdpClosedLoop.exe. NEEDS ADMIN.
#
#   .\rig\pageheap.ps1 -On       # every alloc gets a guard page: heap overruns
#                                # fault AT the corrupting write (0xC0000005)
#   .\rig\pageheap.ps1 -Off      # ALWAYS run this before timing-sensitive runs
#   .\rig\pageheap.ps1           # show status
#
# DIAGNOSTIC ONLY: full PageHeap distorts loop timing and memory badly. Use for
# catch-the-corrupter runs, then turn OFF. WER LocalDumps still applies, so the
# resulting AV produces a dump whose faulting stack IS the corrupter.

param(
    [switch] $On,
    [switch] $Off
)

$k = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\MpcPo8eUdpClosedLoop.exe'

if ($On) {
    New-Item -Path $k -Force | Out-Null
    New-ItemProperty -Path $k -Name GlobalFlag    -PropertyType DWord -Value 0x02000000 -Force | Out-Null
    New-ItemProperty -Path $k -Name PageHeapFlags -PropertyType DWord -Value 0x3        -Force | Out-Null
    Write-Host "Full PageHeap ENABLED for MpcPo8eUdpClosedLoop.exe. Diagnostic runs only -- timing is now unrepresentative." -ForegroundColor Yellow
} elseif ($Off) {
    if (Test-Path $k) {
        Remove-ItemProperty -Path $k -Name GlobalFlag    -ErrorAction SilentlyContinue
        Remove-ItemProperty -Path $k -Name PageHeapFlags -ErrorAction SilentlyContinue
        # Remove the key entirely if nothing else is in it.
        $left = (Get-Item $k).Property
        if (-not $left) { Remove-Item $k }
    }
    Write-Host "PageHeap disabled."
} else {
    if (Test-Path $k) { Get-ItemProperty $k | Select-Object GlobalFlag, PageHeapFlags | Format-List }
    else { Write-Host "No IFEO key: PageHeap is off." }
}
