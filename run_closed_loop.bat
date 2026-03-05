@echo off
setlocal

set MATLABROOT=C:\Program Files\MATLAB\R2025b

if not exist "%MATLABROOT%\extern\bin\win64\libMatlabEngine.dll" (
    echo MATLAB Engine runtime DLL not found under "%MATLABROOT%".
    echo Update MATLABROOT in run_closed_loop.bat to your installed MATLAB version.
    exit /b 1
)

if not exist "MpcPo8eUdpClosedLoop.exe" (
    echo MpcPo8eUdpClosedLoop.exe not found. Run build_closed_loop.bat first.
    exit /b 1
)

rem MATLAB Engine runtime DLLs and their dependencies are not in PATH by default.
rem Include the common MATLAB runtime locations used by Engine/DataArray.
set "PATH=%MATLABROOT%\runtime\win64;%MATLABROOT%\bin\win64;%MATLABROOT%\extern\bin\win64;%MATLABROOT%\sys\os\win64;%PATH%"

rem Usage:
rem   run_closed_loop.bat [tdt_host_or_ip] [matlab_workdir] [mpc_input_count]
MpcPo8eUdpClosedLoop.exe %*
set EXITCODE=%ERRORLEVEL%
echo MpcPo8eUdpClosedLoop exit code: %EXITCODE%
exit /b %EXITCODE%

endlocal
