@echo off
cd /d "%~dp0"
if not exist "venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found.
    echo Please run setup.py first.
    echo.
    echo Instructions:
    echo 1. Open Command Prompt in this folder
    echo 2. Run: python setup.py
    pause
    exit /b 1
)
call venv\Scripts\activate
cls
echo ============================================
echo     El-Basma Clinic - Starting Server
echo ============================================
echo.
echo Opening browser... Please wait.
echo If browser doesn't open, go to: http://127.0.0.1:8000
echo.
start http://127.0.0.1:8000
python manage.py runserver 127.0.0.1:8000
pause
