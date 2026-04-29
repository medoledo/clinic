@echo off
cd /d "%~dp0"

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo Creating virtual environment...
    python -m venv venv
    echo Installing dependencies...
    call venv\Scripts\activate
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate
)

REM Run migrations and start server
echo Starting El-Basma Clinic...
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
pause
