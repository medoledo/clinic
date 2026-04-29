@echo off
cd /d "%~dp0"
if not exist "backups" mkdir backups

REM Create timestamp
call venv\Scripts\activate >nul 2>&1
for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set mydate=%%c%%a%%b)
for /f "tokens=1-2 delims=/:" %%a in ('time /t') do (set mytime=%%a%%b)
set datetime=%mydate%_%mytime%
set datetime=%datetime: =0%

echo ============================================
echo     El-Basma Clinic - Backup
echo ============================================
echo.

REM Backup database
echo Backing up database...
copy db.sqlite3 "backups\db_%datetime%.sqlite3" >nul
echo   Database: backups\db_%datetime%.sqlite3

REM Backup media files
if exist "media" (
    echo Backing up media files...
    xcopy media "backups\media_%datetime%\" /E /I /Y >nul 2>&1
    echo   Media:    backups\media_%datetime%\
)

echo.
echo Backup complete!
pause
