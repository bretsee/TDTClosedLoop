@echo off
rem Build the native controller server (backup for matlab_controller_server.m).
rem
rem Deliberately has NO dependencies: no MATLAB, no CMake, no Eigen, no LibTorch.
rem Only the Visual Studio C++ toolchain and the Windows SDK, both of which are
rem already required to build MpcPo8eUdpClosedLoop.exe.
rem
rem   build_cpp_controller.bat
rem   cpp_controller.exe --selftest

setlocal

set "VSDEVCMD=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat"

where cl >nul 2>nul
if errorlevel 1 (
    if not exist "%VSDEVCMD%" (
        echo cl.exe was not found on PATH and "%VSDEVCMD%" does not exist.
        echo Launch from a Visual Studio developer shell, or fix VSDEVCMD above.
        exit /b 1
    )
    call "%VSDEVCMD%" -host_arch=x64 -arch=x64 >nul
    if errorlevel 1 (
        echo Failed to initialize the Visual Studio build environment.
        exit /b 1
    )
)

rem cl does not create the /Fo directory itself; it fails with C1083 if absent.
if not exist cpp_controller_build mkdir cpp_controller_build

rem /O2   optimise -- this runs inside a 10 ms budget
rem /EHsc standard C++ exceptions (model loading throws; the control tick does not)
rem /W3   warnings; the code is expected to build clean
cl /nologo /O2 /EHsc /std:c++17 /W3 ^
   /Fe:cpp_controller.exe ^
   /Fo:cpp_controller_build\ ^
   cpp_controller\main.cpp ^
   /link ws2_32.lib

if errorlevel 1 (
    echo.
    echo BUILD FAILED
    exit /b 1
)

echo.
echo Built cpp_controller.exe
echo Run the offline checks now:  cpp_controller.exe --selftest
endlocal
