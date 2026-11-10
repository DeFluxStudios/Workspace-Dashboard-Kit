@echo off
rem Builds DashboardSaver.scr from DashboardSaver.cs with the C# compiler that ships with Windows (.NET Framework 4).
cd /d "%~dp0"
set CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe
if not exist "%CSC%" set CSC=%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe
if not exist "%CSC%" (echo C# compiler not found. .NET Framework 4 is needed. & exit /b 1)
"%CSC%" /nologo /target:winexe /r:System.Windows.Forms.dll /r:System.Management.dll /out:DashboardSaver.scr DashboardSaver.cs
