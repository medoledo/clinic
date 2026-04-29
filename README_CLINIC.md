# El-Basma Clinic - Quick Start Guide

## First Time Setup (Run Once)

1. **Install Python**
   - Download from: https://python.org/downloads
   - During installation, check **"Add Python to PATH"**

2. **Run Setup**
   - Double-click: `setup.bat`
   - Follow the prompts to create your login
   - Wait for installation to complete (5-10 minutes)

## Daily Use

- **Start the clinic system:** Double-click `run.bat`
- **Open in browser:** http://127.0.0.1:8000 (opens automatically)
- **Login** with the username and password you created during setup

## Backup (Do This Weekly)

- **Create backup:** Double-click `backup.bat`
- Backups are saved to the `backups/` folder
- To restore: Copy a backup file back to `db.sqlite3`

## If Something Looks Wrong

- **Page looks old or data seems wrong:** Press `Ctrl + F5` in your browser
- **Can't add patient (CSRF error):** Press `Ctrl + F5` and try again
- **Server won't start:** Make sure no other `run.bat` window is already open

## Need Help?

Contact the person who set up this system for you.

---

**System:** El-Basma Clinic - Patient Records Management  
**Doctor:** Dr. Mohammed Mahmoud Basyony
