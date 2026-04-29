@echo off
cd /d "%~dp0"
echo ============================================
echo     El-Basma Clinic - First Time Setup
echo ============================================
echo.
echo This will set up everything automatically.
echo It may take 5-10 minutes.
echo.
pause

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Please install Python 3.11+ from https://python.org/downloads
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

python setup.py
