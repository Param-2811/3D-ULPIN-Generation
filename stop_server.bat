@echo off
rem Stop whatever is listening on port 8000 (the 3D ULPIN server).
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    echo Stopping server, process %%p
    taskkill /PID %%p /F >nul 2>&1
)
echo Server stopped.
