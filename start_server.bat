@echo off
rem Start the 3D ULPIN server on http://127.0.0.1:8000 (stops any old one first).
cd /d "%~dp0"
call stop_server.bat >nul 2>&1
echo Starting 3D ULPIN server...
start "3D ULPIN server" /min .venv\Scripts\uvicorn.exe src.api.main:app --port 8000
ping -n 7 127.0.0.1 >nul
echo.
echo   Viewer:      http://127.0.0.1:8000/
echo   Register:    http://127.0.0.1:8000/submit.html
echo   Try model:   http://127.0.0.1:8000/try_model.html
echo.
start "" http://127.0.0.1:8000/submit.html
