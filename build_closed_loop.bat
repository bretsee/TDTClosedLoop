@echo off
setlocal

set MATLABROOT=C:\Program Files\MATLAB\R2025b

if not exist "%MATLABROOT%\extern\include\MatlabEngine.hpp" (
    echo MATLAB headers not found under "%MATLABROOT%".
    echo Update MATLABROOT in build_closed_loop.bat to your installed version.
    exit /b 1
)

cl /EHsc /std:c++17 MpcPo8eUdpClosedLoop.cpp TDTUDP.cpp ^
 /I"%MATLABROOT%\extern\include" ^
 /I"%MATLABROOT%\extern\include\MatlabEngine" ^
 /I"%MATLABROOT%\extern\include\MatlabDataArray" ^
 /link ^
 /LIBPATH:"%MATLABROOT%\extern\lib\win64\microsoft" ^
 PO8eStreaming.lib ws2_32.lib libMatlabEngine.lib libMatlabDataArray.lib

endlocal
