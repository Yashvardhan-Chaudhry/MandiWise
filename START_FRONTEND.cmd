@echo off
setlocal
cd /d "%~dp0frontend"
echo MandiWise React frontend
echo First start START_MANDIWISE.cmd in another terminal and leave it open.
echo This frontend connects to that backend on port 8001.
where node >nul 2>nul
if errorlevel 1 (
  echo Install a supported Node.js version first. See frontend\README.md.
  pause
  exit /b 1
)
if not exist node_modules\vite\bin\vite.js (
  call npm.cmd ci --no-audit --no-fund
  if errorlevel 1 (
    echo Dependency installation failed. Keep this error message for troubleshooting.
    pause
    exit /b 1
  )
)
call npm.cmd run dev -- --open
if errorlevel 1 pause
