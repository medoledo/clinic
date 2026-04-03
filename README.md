# MediTrack — Doctor Visit Records System

A Django 5.x clinic management system with voice transcription, offline support, and a clean professional UI.

## Quick Setup

### 1. Activate Virtual Environment
```powershell
C:\Users\medol\OneDrive\Desktop\clinic\Scripts\activate.bat
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run Migrations
```bash
python manage.py makemigrations accounts patients
python manage.py migrate
```

### 4. Create Admin Account
```bash
python manage.py setup_meditrack
```
This creates:
- **Username**: `admin`  
- **Password**: `admin123`

### 5. Start the Server
```bash
python manage.py runserver
```

Open: **http://127.0.0.1:8000/**

---

## User Roles

| Role   | Login                | Dashboard       |
| ------ | -------------------- | --------------- |
| Admin  | `admin` / `admin123` | `/admin-panel/` |
| Doctor | (created by admin)   | `/dashboard/`   |

---

## Features

### Doctor
- **Dashboard** — stats (patients, today's visits, month's visits)
- **Live Search** — AJAX search by name/phone with 300ms debounce
- **Patient Management** — add, edit, view patients
- **Visit Records** — full medical form with all clinical fields
- **Voice Transcription** — Web Speech API (Chrome/Edge) for hands-free dictation
  - Master mic button + per-field mics
  - AR/EN language toggle
  - Real-time interim text display
- **File Uploads** — drag & drop, multiple files, image preview
- **Offline Mode** — saves visits to IndexedDB when disconnected, auto-syncs when back online

### Admin
- **Stats** — total doctors, active doctors, total patients, total visits
- **Doctor Management** — add/edit/deactivate, reset passwords
- Cannot access any patient data

---

## Voice Transcription
> Requires Chrome or Edge browser and microphone access.

1. Click **🎤 Start Recording**
2. Tap any field's mic button to direct speech to that field
3. Switch between **AR** (Arabic) and **EN** (English)
4. Text accumulates — you can keep speaking
5. Tap mic again to stop

---

## Keyboard Shortcuts

| Shortcut   | Action            |
| ---------- | ----------------- |
| `Ctrl + M` | Toggle microphone |
| `Ctrl + S` | Save visit        |
| `Ctrl + F` | Focus search bar  |
| `ESC`      | Stop recording    |

---

## Project Structure
```
clinic/
├── accounts/           # Auth, profiles, admin panel
│   ├── models.py       # DoctorProfile, AdminProfile
│   ├── views.py        # Login, admin CRUD
│   ├── decorators.py   # Role-based access
│   └── management/commands/setup_meditrack.py
├── patients/           # Patients & visits
│   ├── models.py       # Patient, Visit, VisitFile
│   └── views.py        # Dashboard, CRUD, AJAX search
├── templates/
│   ├── base.html       # Sidebar, offline banners, lightbox
│   ├── accounts/       # Login, admin templates
│   └── patients/       # Dashboard, patient/visit templates
├── static/
│   ├── js/voice.js     # Web Speech API transcription
│   ├── js/search.js    # AJAX debounced search
│   ├── js/upload.js    # Drag-and-drop file upload
│   ├── js/offline.js   # IndexedDB + network detection
│   ├── js/shortcuts.js # Keyboard shortcuts
│   └── sw.js           # Service Worker (offline caching)
└── requirements.txt
```

---

## Tech Stack
- **Backend**: Django 5.2, SQLite
- **Frontend**: Tailwind CSS (CDN), Vanilla JavaScript
- **Voice**: Web Speech API (free, no paid APIs)
- **Offline**: Service Worker + IndexedDB
- **Files**: Pillow for image processing
