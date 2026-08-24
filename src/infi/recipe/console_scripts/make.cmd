@echo off
setlocal

set "VCVARSALL=C:\Program Files (x86)\Microsoft Visual Studio\2017\Enterprise\VC\Auxiliary\Build\VCVARSALL.bat"

call :build x86 x86
if errorlevel 1 exit /b 1

call :build x86_amd64 x64
if errorlevel 1 exit /b 1

exit /b 0

:build
setlocal
call "%VCVARSALL%" %1
if errorlevel 1 exit /b 1

cl /nologo /O2 /W3 /c embed3.c /Foembed3-%2.obj
if errorlevel 1 exit /b 1

link /nologo /SUBSYSTEM:CONSOLE /out:embed3-%2.exe embed3-%2.obj shell32.lib
if errorlevel 1 exit /b 1

link /nologo /SUBSYSTEM:WINDOWS /out:embed3-gui-%2.exe embed3-%2.obj shell32.lib
if errorlevel 1 exit /b 1

del /q embed3-%2.obj
if errorlevel 1 exit /b 1

endlocal & exit /b 0
