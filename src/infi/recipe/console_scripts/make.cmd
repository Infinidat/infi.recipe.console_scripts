@echo off

PATH=C:\Program Files\Microsoft Visual Studio 9.0\VC;%PATH%
PATH=C:\Program Files (x86)\Microsoft Visual Studio 9.0\VC;%PATH%

call VCVARSALL x86
cl /c embed.c /I parts\python\include 
link /out:embed-x86.exe embed.obj
link /SUBSYSTEM:WINDOWS /out:embed-gui-x86.exe embed.obj

call VCVARSALL x86_amd64
cl /c embed.c /I parts\python\include 
link /out:embed-x64.exe embed.obj
link /SUBSYSTEM:WINDOWS /out:embed-gui-x64.exe embed.obj

