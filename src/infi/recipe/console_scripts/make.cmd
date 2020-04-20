@echo off

PATH=C:\Program Files (x86)\Microsoft Visual Studio\2017\Enterprise\VC\Auxiliary\Build;%PATH%

call VCVARSALL x86_amd64
cl /c embed3.c /I parts\python\include
link /SUBSYSTEM:CONSOLE /out:embed3-x64.exe embed3.obj shell32.lib
link /SUBSYSTEM:WINDOWS /out:embed3-gui-x64.exe embed3.obj shell32.lib
