@echo off
set MATLABROOT=C:\Program Files\MATLAB\R2025b

cl /EHsc engine_hello.cpp ^
 /I"%MATLABROOT%\extern\include" ^
 /I"%MATLABROOT%\extern\include\MatlabEngine" ^
 /I"%MATLABROOT%\extern\include\MatlabDataArray" ^
 /link ^
 /LIBPATH:"%MATLABROOT%\extern\lib\win64\microsoft" ^
 libMatlabEngine.lib libMatlabDataArray.lib
