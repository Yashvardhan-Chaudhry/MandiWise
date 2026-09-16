@echo off
setlocal
cd /d "%~dp0"
echo MandiWise - simple transport demonstration
echo.
if exist ".venv\Scripts\python.exe" (
    set "DEMO_PYTHON=.venv\Scripts\python.exe"
    goto launch
)
if exist "..\.venv\Scripts\python.exe" (
    set "DEMO_PYTHON=..\.venv\Scripts\python.exe"
    goto launch
)
echo Preparing Python. This only happens the first time.
py -3.12 -m venv .venv
if errorlevel 1 (
    echo Install Python 3.12, then run this file again.
    pause
    exit /b 1
)
set "DEMO_PYTHON=.venv\Scripts\python.exe"
:launch
"%DEMO_PYTHON%" -m pip --version >nul 2>&1
if errorlevel 1 "%DEMO_PYTHON%" -m ensurepip --upgrade
"%DEMO_PYTHON%" -m pip install -e .
if errorlevel 1 (
    echo Package installation failed. Check your internet connection.
    pause
    exit /b 1
)
echo.
echo Opening http://127.0.0.1:8001/demo
echo Keep this window open while you use the demo. Press Ctrl+C to stop.
"%DEMO_PYTHON%" -m mandiwise_transport.presentation
if errorlevel 1 (
    echo The server could not start. If port 8001 is in use, close the previous demo window.
    pause
)
