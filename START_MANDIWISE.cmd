@echo off
setlocal
echo Starting the MandiWise backend: transport, pooling and net-realisation API.
echo.
echo   STARTING NOW - transport pooling backend
echo   A local web demo at http://127.0.0.1:8001/demo
echo   Same as running backend\START_DEMO.cmd
echo.
echo   For the farmer interface, also run START_FRONTEND.cmd
echo   Then open http://127.0.0.1:5173/#rankings
echo.
call "%~dp0backend\START_DEMO.cmd"
