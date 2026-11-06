@echo off
setlocal
set "MODE="

if "%~1"=="" set "MODE=-Foreground"
if /I "%~1"=="--foreground" set "MODE=-Foreground"
if /I "%~1"=="--background" set "MODE=-Background"
if /I "%~1"=="--desktop" set "MODE=-Background"
if /I "%~1"=="--stop" set "MODE=-Stop"
if /I "%~1"=="--status" set "MODE=-Status"
if /I "%~1"=="--help" set "MODE=-Help"
if /I "%~1"=="-h" set "MODE=-Help"

if not defined MODE goto usage

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0pruefung.ps1" %MODE%
exit /b %ERRORLEVEL%

:usage
echo Verwendung: pruefung.cmd [--background^|--stop^|--status^|--help]
exit /b 2
