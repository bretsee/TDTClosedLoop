@echo off
setlocal

set MATLABROOT=C:\Program Files\MATLAB\R2025b
set "VSDEVCMD=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat"

if not exist "%MATLABROOT%\extern\include\MatlabEngine.hpp" (
    echo MATLAB headers not found under "%MATLABROOT%".
    echo Update MATLABROOT in build_closed_loop.bat to your installed version.
    exit /b 1
)

where cl >nul 2>nul
if errorlevel 1 (
    if not exist "%VSDEVCMD%" (
        echo cl.exe was not found on PATH.
        echo Also could not find "%VSDEVCMD%".
        echo Launch this from a Visual Studio developer shell or update VSDEVCMD in build_closed_loop.bat.
        exit /b 1
    )

    call "%VSDEVCMD%" -host_arch=x64 -arch=x64 >nul
    if errorlevel 1 (
        echo Failed to initialize the Visual Studio build environment.
        exit /b 1
    )
)

cl /EHsc /std:c++17 /Zi /Fd:MpcPo8eUdpClosedLoop_compile.pdb MpcPo8eUdpClosedLoop.cpp TDTUDP.cpp ^
 /I"%MATLABROOT%\extern\include" ^
 /I"%MATLABROOT%\extern\include\MatlabEngine" ^
 /I"%MATLABROOT%\extern\include\MatlabDataArray" ^
 /link /DEBUG /PDB:MpcPo8eUdpClosedLoop.pdb ^
 /LIBPATH:"%MATLABROOT%\extern\lib\win64\microsoft" ^
 PO8eStreaming.lib ws2_32.lib libMatlabEngine.lib libMatlabDataArray.lib

endlocal
