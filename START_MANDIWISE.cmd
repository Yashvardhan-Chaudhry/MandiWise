@echo off
setlocal
echo MandiWise is two separate programs. This file starts one of them.
echo.
echo   STARTING NOW - transport pooling backend
echo   A local web demo at http://127.0.0.1:8001/demo
echo   Same as running backend\START_DEMO.cmd
echo.
echo   NOT STARTED - mandi recommendation engine
echo   Prints a ranked comparison, no server. Run it yourself with:
echo       python demo.py
echo.
call "%~dp0backend\START_DEMO.cmd"
