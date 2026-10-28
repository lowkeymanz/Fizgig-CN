@echo off
rem Fizgig CN launcher (Windows)
cd /d "%~dp0"
if not exist "..\venv\Scripts\python.exe" (
    echo [ERROR] Fizgig venv not found: ..\venv
    echo Please run install_fizgig.bat first, then try again.
    pause
    exit /b 1
)
"..\venv\Scripts\python.exe" start.py %*
set "code=%errorlevel%"
if not "%code%"=="0" pause
exit /b %code%
