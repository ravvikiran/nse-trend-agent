@echo off
REM NSE Trend Scanner - Web UI Launcher (Windows)
REM This script starts the web UI

setlocal enabledelayedexpansion

echo.
echo ====================================================
echo   NSE Trend Scanner - Web UI Launcher (Windows)
echo ====================================================
echo.

REM Check if virtual environment exists
if not exist ".venv" (
    echo ERROR: Virtual environment not found!
    echo Please create it first:
    echo   python -m venv .venv
    echo   .venv\Scripts\activate
    echo   pip install -r requirements.txt
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat

REM Check if Flask is installed
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo Flask not installed. Installing...
    pip install flask flask-cors
)

REM Set default port
set PORT=5000
if not "%2"=="" set PORT=%2

REM Check mode
if "%1"=="" goto ui_mode
if "%1"=="ui" goto ui_mode
if "%1"=="help" goto help_mode

echo Unknown mode: %1
echo Use 'help' for usage information: run_ui.bat help
exit /b 1

:ui_mode
echo.
echo Starting Web UI Server...
echo Dashboard will be available at: http://localhost:%PORT%
echo.
python src/api.py --port %PORT%
exit /b 0

:help_mode
echo Usage: run_ui.bat [MODE] [PORT]
echo.
echo Modes:
echo   ui       - Run Web UI only (default)
echo   help     - Show this help message
echo.
echo Examples:
echo   run_ui.bat                 - Run UI on port 5000
echo   run_ui.bat ui 8000         - Run UI on port 8000
echo.
exit /b 0
