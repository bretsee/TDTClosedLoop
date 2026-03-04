@echo off
setlocal

cl /EHsc /std:c++17 RZ2UdpBarebones.cpp /link ws2_32.lib

endlocal

