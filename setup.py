#!/usr/bin/env python3
"""
El-Basma Clinic — Automated Setup Script
Run this once on the Dr's laptop after git clone.
"""

import os
import sys
import subprocess
import secrets
import shutil
from pathlib import Path

# ─── Configuration ───────────────────────────────────────────────────────────
REQUIRED_PYTHON = (3, 11)
PROJECT_NAME = "El-Basma Clinic"
VENV_DIR = "venv"
ENV_FILE = ".env"


def print_banner(text):
    width = 60
    print("\n" + "=" * width)
    print(text.center(width))
    print("=" * width + "\n")


def print_step(step_num, total, message):
    print(f"\n[{step_num}/{total}] {message}")
    print("-" * 50)


def run_cmd(cmd, check=True, capture=False):
    """Run a shell command and return output."""
    kwargs = {"check": check, "shell": True}
    if capture:
        kwargs["capture_output"] = True
        kwargs["text"] = True
    return subprocess.run(cmd, **kwargs)


def check_python():
    """Verify Python version is sufficient."""
    version = sys.version_info
    if version < REQUIRED_PYTHON:
        print(f"ERROR: Python {REQUIRED_PYTHON[0]}.{REQUIRED_PYTHON[1]}+ required.")
        print(f"You have: {version.major}.{version.minor}.{version.micro}")
        print("Download from: https://python.org/downloads")
        sys.exit(1)
    print(f"Python {version.major}.{version.minor}.{version.micro} OK")


def create_venv():
    """Create virtual environment if it doesn't exist."""
    if os.path.exists(VENV_DIR):
        print("Virtual environment already exists. Skipping creation.")
        return
    print("Creating virtual environment...")
    run_cmd(f'"{sys.executable}" -m venv {VENV_DIR}')
    print("Virtual environment created.")


def get_python_path():
    """Get the Python executable inside the venv."""
    if os.name == "nt":  # Windows
        return os.path.join(VENV_DIR, "Scripts", "python.exe")
    return os.path.join(VENV_DIR, "bin", "python")


def get_pip_path():
    """Get the pip executable inside the venv."""
    if os.name == "nt":  # Windows
        return os.path.join(VENV_DIR, "Scripts", "pip.exe")
    return os.path.join(VENV_DIR, "bin", "pip")


def install_requirements():
    """Install Python packages."""
    pip = get_pip_path()
    print("Upgrading pip...")
    run_cmd(f'"{get_python_path()}" -m pip install --upgrade pip')
    print("Installing requirements (this may take a few minutes)...")
    run_cmd(f'"{pip}" install -r requirements.txt')
    print("All dependencies installed.")


def generate_secret_key():
    """Generate a secure Django SECRET_KEY."""
    return secrets.token_urlsafe(50)


def create_env_file():
    """Create the .env file with default settings."""
    if os.path.exists(ENV_FILE):
        print(".env file already exists. Skipping creation.")
        return

    secret_key = generate_secret_key()
    env_content = f"""# El-Basma Clinic Environment Configuration
# Generated automatically by setup.py

# Groq API Key (leave empty if voice transcription is not needed)
GROQ_API_KEY=

# Django Security Key (auto-generated)
SECRET_KEY={secret_key}

# Debug mode (True for local development)
DEBUG=True

# Allowed hosts (127.0.0.1 and localhost for local use)
ALLOWED_HOSTS=127.0.0.1,localhost
"""
    with open(ENV_FILE, "w") as f:
        f.write(env_content)
    print(".env file created with secure settings.")


def run_migrations():
    """Apply database migrations."""
    python = get_python_path()
    print("Running database migrations...")
    run_cmd(f'"{python}" manage.py migrate')
    print("Database migrations complete.")


def create_superuser():
    """Create the doctor's admin account."""
    python = get_python_path()
    print("\n" + "=" * 50)
    print("CREATE DOCTOR ACCOUNT")
    print("=" * 50)
    print("This will be the login for the clinic system.\n")

    # Use Django's createsuperuser command interactively
    result = subprocess.run(
        f'"{python}" manage.py createsuperuser',
        shell=True
    )

    if result.returncode != 0:
        print("\nUser creation was cancelled or failed.")
        print("You can create a user later with: python manage.py createsuperuser")
        return False
    return True


def set_doctor_role():
    """Set the user's role to 'doctor'."""
    python = get_python_path()
    print("\nSetting user role to 'doctor'...")

    script = """
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'clinic.settings')
import django
django.setup()

from django.contrib.auth.models import User
from accounts.models import UserProfile

users = User.objects.filter(is_superuser=True)
if users.count() == 0:
    print("ERROR: No users found. Run createsuperuser first.")
    exit(1)

for user in users:
    profile, created = UserProfile.objects.get_or_create(
        user=user,
        defaults={'role': 'doctor'}
    )
    if not created and profile.role != 'doctor':
        profile.role = 'doctor'
        profile.save()
    print(f'User "{user.username}" is now set as DOCTOR.')

print("Role assignment complete.")
"""
    run_cmd(f'"{python}" -c "{script}"')


def collect_static():
    """Collect static files (optional for development)."""
    python = get_python_path()
    print("Collecting static files...")
    run_cmd(f'"{python}" manage.py collectstatic --noinput')
    print("Static files collected.")


def create_run_script():
    """Create a convenient run script if it doesn't exist."""
    if os.path.exists("run.bat"):
        return

    run_bat = """@echo off
cd /d "%~dp0"
if not exist "venv\\Scripts\\activate.bat" (
    echo ERROR: Virtual environment not found.
    echo Please run setup.py first.
    pause
    exit /b 1
)
call venv\\Scripts\\activate
echo Starting El-Basma Clinic...
echo Open your browser to: http://127.0.0.1:8000
python manage.py runserver 127.0.0.1:8000
pause
"""
    with open("run.bat", "w") as f:
        f.write(run_bat)
    print("run.bat created for easy startup.")


def create_backup_script():
    """Create a backup script."""
    if os.path.exists("backup.bat"):
        return

    backup_bat = """@echo off
cd /d "%~dp0"
if not exist "backups" mkdir backups
set datetime=%date:~-4,4%%date:~-10,2%%date:~-7,2%_%time:~0,2%%time:~3,2%
set datetime=%datetime: =0%
copy db.sqlite3 "backups\\db_%datetime%.sqlite3" >nul
xcopy media backups\\media\\ /E /I /Y >nul 2>&1
echo Backup saved to backups\\db_%datetime%.sqlite3
pause
"""
    with open("backup.bat", "w") as f:
        f.write(backup_bat)
    print("backup.bat created for easy backups.")


def main():
    print_banner(f"Welcome to {PROJECT_NAME} Setup")

    total_steps = 8
    current_step = 0

    # Step 1: Check Python
    current_step += 1
    print_step(current_step, total_steps, "Checking Python version")
    check_python()

    # Step 2: Create virtual environment
    current_step += 1
    print_step(current_step, total_steps, "Creating virtual environment")
    create_venv()

    # Step 3: Install dependencies
    current_step += 1
    print_step(current_step, total_steps, "Installing dependencies")
    install_requirements()

    # Step 4: Create .env file
    current_step += 1
    print_step(current_step, total_steps, "Creating configuration file")
    create_env_file()

    # Step 5: Run migrations
    current_step += 1
    print_step(current_step, total_steps, "Setting up database")
    run_migrations()

    # Step 6: Create superuser
    current_step += 1
    print_step(current_step, total_steps, "Creating doctor account")
    user_created = create_superuser()

    # Step 7: Set doctor role
    if user_created:
        current_step += 1
        print_step(current_step, total_steps, "Assigning doctor role")
        set_doctor_role()

    # Step 8: Collect static and create scripts
    current_step += 1
    print_step(current_step, total_steps, "Finalizing setup")
    collect_static()
    create_run_script()
    create_backup_script()

    # Done
    print_banner("Setup Complete!")
    print("""
Your clinic system is ready!

To start the application:
  Double-click: run.bat
  Or run:       python manage.py runserver

To create a backup:
  Double-click: backup.bat

Access the system:
  Open browser: http://127.0.0.1:8000
  Login with the username/password you just created.

If you ever see stale data or CSRF errors:
  Press Ctrl+F5 in the browser to hard refresh.
""")

    # Ask to start now
    response = input("\nWould you like to start the server now? (y/n): ").strip().lower()
    if response in ('y', 'yes'):
        python = get_python_path()
        print("\nStarting server...")
        run_cmd(f'"{python}" manage.py runserver 127.0.0.1:8000', check=False)


if __name__ == "__main__":
    main()
