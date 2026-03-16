@echo off
REM Start the Poker WebSocket Server

echo Starting Poker WebSocket Server...
echo.

REM Activate virtual environment
call .\venv\Scripts\activate.bat

REM Start the server
python -m api.main

pause