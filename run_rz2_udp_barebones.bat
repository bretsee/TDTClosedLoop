@echo off
setlocal

if not exist "RZ2UdpBarebones.exe" (
    echo RZ2UdpBarebones.exe not found. Run build_rz2_udp_barebones.bat first.
    exit /b 1
)

rem Usage:
rem   run_rz2_udp_barebones.bat [host] [baseValue] [count] [periodMs] [loops]
rem Example:
rem   run_rz2_udp_barebones.bat 10.1.0.1 12345 1 20 1000
RZ2UdpBarebones.exe %*

endlocal

