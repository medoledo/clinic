# MediTrack — Complete Technical Documentation

> **Project:** MediTrack Clinic Management System  
> **Generated:** April 12, 2026  
> **Scope:** Full codebase — every model, view, URL, JS file, and configuration option

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Project Structure](#2-project-structure)
3. [Database Models](#3-database-models)
4. [URL Routes](#4-url-routes)
5. [Views & Business Logic](#5-views--business-logic)
6. [Voice Transcription System](#6-voice-transcription-system)
7. [Authentication System](#7-authentication-system)
8. [File Upload System](#8-file-upload-system)
9. [Drug Dictionary System](#9-drug-dictionary-system)
10. [API Endpoints](#10-api-endpoints)
11. [Management Commands](#11-management-commands)
12. [Static Files & Frontend](#12-static-files--frontend)
13. [Environment Variables & Configuration](#13-environment-variables--configuration)
14. [Deployment Checklist](#14-deployment-checklist)
15. [Known Issues & Limitations](#15-known-issues--limitations)

---

## 1. Project Overview

### What This Application Does

MediTrack is a **private clinic management system** designed for Egyptian doctors. It allows a doctor (or a team of doctors administered by a clinic owner) to:

- Manage a patient registry with demographics
- Record detailed visit notes including chief complaint, symptoms, diagnosis, treatment, vitals, and private doctor notes
- **Dictate visit notes by voice** — audio is transcribed using Groq Whisper and then parsed into structured form fields using an LLM (Llama 3.1 8B)
- Attach medical files (X-rays, lab results, PDFs, images) and external links to each visit
- Auto-correct Arabic drug names using a fuzzy-matching system backed by a 14,000+ entry Egyptian drug dictionary
- Work **offline** — visits recorded without internet are saved in IndexedDB and synced when connection is restored
- Print visit summaries as clean prescription-style PDFs
- Admin panel for clinic owners to manage doctor accounts and view analytics

### Who It Is Built For

- **Primary user:** An Egyptian doctor dictating in Arabic/mixed Arabic-English during or after a patient consultation
- **Secondary user:** A clinic administrator (admin role) who manages doctor accounts and monitors clinic-wide statistics

### Tech Stack

| Layer                   | Technology                                                           |
| ----------------------- | -------------------------------------------------------------------- |
| Language                | Python 3.x                                                           |
| Framework               | Django 5.2                                                           |
| Database                | SQLite 3 (WAL mode, 20-second timeout)                               |
| AI — Speech to Text     | Groq Whisper Large V3                                                |
| AI — Transcript Parsing | Groq Llama 3.1 8B Instant (primary), OpenAI GPT (secondary fallback) |
| AI — Local Fallback     | Regex-based field extractor (tertiary fallback)                      |
| Fuzzy Matching          | RapidFuzz (`fuzz.WRatio`, threshold 70)                              |
| In-Process Cache        | Django LocMemCache (1-hour TTL for medical dictionary)               |
| Frontend                | Vanilla HTML/CSS/JS (no framework)                                   |
| Offline Support         | IndexedDB + Service Worker                                           |
| File Storage            | Local filesystem (`media/visit_files/`)                              |
| Key Python packages     | `groq`, `rapidfuzz`, `python-decouple`, `Pillow`                     |

---

## 2. Project Structure

```
clinic/                              ← Django project root
├── .env                             ← Environment variables (GROQ_API_KEY)
├── .gitignore                       ← Git ignore rules
├── db.sqlite3                       ← SQLite database file
├── egyptian_drugs.txt               ← 14,000+ Arabic drug names (source for import_drugs)
├── manage.py                        ← Django management entry point
├── requirements.txt                 ← Python dependencies
├── DOCUMENTATION.md                 ← This file
│
├── clinic/                          ← Django project config package
│   ├── settings.py                  ← All Django settings (DB, cache, security, auth)
│   ├── urls.py                      ← Root URL router (includes accounts + patients)
│   ├── wsgi.py                      ← WSGI entry point for production servers
│   └── asgi.py                      ← ASGI entry point (not used, placeholder)
│
├── accounts/                        ← Authentication & user management app
│   ├── models.py                    ← UserProfile, DoctorProfile, AdminProfile models
│   ├── views.py                     ← Login, logout, register, admin CRUD views
│   ├── urls.py                      ← Auth + admin panel URL patterns
│   ├── decorators.py                ← @doctor_required, @admin_required, @post_required
│   ├── admin.py                     ← Django admin config for user models
│   └── apps.py                      ← App config
│
├── patients/                        ← Core clinical data app
│   ├── models.py                    ← Patient, Visit, VisitFile, MedicalDictionary, TranscriptionCorrection
│   ├── views.py                     ← All patient/visit CRUD + voice transcription views
│   ├── urls.py                      ← All patient/visit URL patterns
│   ├── utils.py                     ← Fuzzy matching, drug dictionary, regex parser
│   ├── admin.py                     ← Django admin config for clinical models
│   ├── apps.py                      ← App config
│   └── management/
│       └── commands/
│           └── import_drugs.py      ← Management command to seed MedicalDictionary
│
├── templates/                       ← All HTML templates
│   ├── base.html                    ← Master layout: nav, offline banners, scripts
│   ├── sw.js                        ← Service Worker (served at /sw.js via TemplateView)
│   ├── accounts/
│   │   ├── login.html               ← Login page
│   │   ├── register.html            ← Doctor self-registration page
│   │   ├── admin_dashboard.html     ← Admin analytics dashboard
│   │   ├── manage_doctors.html      ← Doctor list with CRUD controls
│   │   ├── doctor_form.html         ← Add/Edit doctor modal form
│   │   ├── confirm_delete.html      ← Doctor deletion confirmation
│   │   └── reset_password.html      ← Password reset form
│   └── patients/
│       ├── dashboard.html           ← Doctor's home: stats + search
│       ├── patient_list.html        ← Paginated patient list with filters
│       ├── patient_detail.html      ← Patient profile + visit history
│       ├── patient_form.html        ← Add/Edit patient form
│       ├── patient_files.html       ← All files grouped by visit
│       ├── add_visit.html           ← Add/Edit visit form with voice recorder
│       ├── visit_detail.html        ← Single visit view with redesigned UI
│       ├── visit_print.html         ← Print-optimised visit summary
│       ├── pending_visits.html      ← Offline pending visits list
│       └── confirm_delete_file.html ← File deletion confirmation
│
├── static/
│   ├── js/
│   │   ├── voice.js                 ← Voice recording, Groq transcription, suggestion popups
│   │   ├── offline.js               ← IndexedDB, network detection, background sync
│   │   ├── search.js                ← Debounced AJAX patient search with highlighting
│   │   ├── upload.js                ← Drag-and-drop file upload with preview
│   │   └── shortcuts.js             ← Keyboard shortcuts (Ctrl+M, Ctrl+S, Ctrl+F)
│   └── css/                         ← (empty — styles are embedded in base.html)
│
└── media/
    └── visit_files/                 ← Uploaded patient files stored here
```

---

## 3. Database Models

### 3.1 `accounts` App

#### `UserProfile`
**File:** `accounts/models.py`  
Extends Django's built-in `User` via a OneToOne relationship to add a role.

| Field        | Type                 | Constraints                              | Purpose                  |
| ------------ | -------------------- | ---------------------------------------- | ------------------------ |
| `user`       | OneToOneField → User | CASCADE, related_name=`profile`          | Link to Django auth user |
| `role`       | CharField(10)        | choices: `admin`/`doctor`, db_index=True | Determines access level  |
| `created_at` | DateTimeField        | auto_now_add                             | Creation timestamp       |

**Meta:** `ordering = ['-created_at']`, index on `role`  
**Usage:** `request.user.profile.role` is checked by every auth decorator

---

#### `DoctorProfile`
**File:** `accounts/models.py`  
Extra professional details for doctor-role users.

| Field            | Type                 | Constraints                            | Purpose                  |
| ---------------- | -------------------- | -------------------------------------- | ------------------------ |
| `user`           | OneToOneField → User | CASCADE, related_name=`doctor_profile` | Link to Django auth user |
| `full_name`      | CharField(200)       | required                               | Doctor's display name    |
| `specialization` | CharField(200)       | blank                                  | Medical specialty        |
| `phone`          | CharField(20)        | blank                                  | Contact number           |
| `created_at`     | DateTimeField        | auto_now_add                           | Creation timestamp       |

**Meta:** `ordering = ['-created_at']`  
**Usage:** `visit.doctor.doctor_profile.full_name` is shown on visit print and admin panel

---

#### `AdminProfile`
**File:** `accounts/models.py`  
Placeholder model for admin-role users. Contains no extra fields beyond the user link.

| Field        | Type                 | Constraints                           | Purpose                  |
| ------------ | -------------------- | ------------------------------------- | ------------------------ |
| `user`       | OneToOneField → User | CASCADE, related_name=`admin_profile` | Link to Django auth user |
| `created_at` | DateTimeField        | auto_now_add                          | Creation timestamp       |

---

### 3.2 `patients` App

#### `Patient`
**File:** `patients/models.py`  
Core patient registry. Each patient belongs to exactly one doctor.

| Field           | Type              | Constraints                              | Purpose                     |
| --------------- | ----------------- | ---------------------------------------- | --------------------------- |
| `doctor`        | ForeignKey → User | CASCADE, related_name=`patients`         | Owning doctor               |
| `name`          | CharField(200)    | required                                 | Full patient name           |
| `phone`         | CharField(20)     | blank                                    | Contact phone               |
| `date_of_birth` | DateField         | null, blank                              | Used to calculate age       |
| `gender`        | CharField(10)     | choices: `male`/`female`, default=`male` | Patient gender              |
| `notes`         | TextField         | blank                                    | General notes about patient |
| `created_at`    | DateTimeField     | auto_now_add                             | Registration date           |

**Meta:**  
- `ordering = ['-created_at']`
- `indexes`: composite `(doctor, -created_at)`, single `(name)`

**Custom Properties:**

```python
# patients/models.py — Patient.age
@property
def age(self):
    """Returns patient's age in years from date_of_birth. Returns None if DOB not set."""
    if self.date_of_birth:
        today = timezone.now().date()
        born = self.date_of_birth
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    return None

# Patient.last_visit — hits DB on every call, avoid in loops
@property
def last_visit(self):
    return self.visits.order_by('-visit_date').first()

# Patient.total_visits — hits DB on every call, avoid in loops
@property
def total_visits(self):
    return self.visits.count()
```

---

#### `Visit`
**File:** `patients/models.py`  
A single patient consultation. Contains all clinical data dictated by the doctor.

| Field               | Type                 | Constraints                    | Purpose                     |
| ------------------- | -------------------- | ------------------------------ | --------------------------- |
| `patient`           | ForeignKey → Patient | CASCADE, related_name=`visits` | The patient seen            |
| `doctor`            | ForeignKey → User    | CASCADE, related_name=`visits` | Doctor who recorded it      |
| `visit_date`        | DateTimeField        | default=timezone.now           | Date and time of visit      |
| `chief_complaint`   | TextField            | required                       | Main reason for visit       |
| `symptoms`          | TextField            | null, blank                    | Symptom description         |
| `diagnosis`         | TextField            | null, blank                    | Doctor's diagnosis          |
| `treatment`         | TextField            | null, blank                    | Treatment / prescription    |
| `temperature`       | DecimalField(4,1)    | null, blank                    | Body temperature in °C      |
| `blood_pressure`    | CharField(20)        | blank                          | e.g. "120/80"               |
| `pulse`             | PositiveIntegerField | null, blank                    | Heart rate in bpm           |
| `weight`            | DecimalField(5,2)    | null, blank                    | Body weight in kg           |
| `next_checkup_date` | DateField            | null, blank                    | Scheduled follow-up date    |
| `doctor_notes`      | TextField            | null, blank                    | Private notes (not printed) |
| `created_at`        | DateTimeField        | auto_now_add                   | Record creation timestamp   |

**Meta:**  
- `ordering = ['-visit_date']`
- `indexes`: `(doctor, -visit_date)`, `(patient, -visit_date)`, `(visit_date)` for analytics

**Custom Properties:**

```python
@property
def has_files(self):
    return self.files.exists()

@property
def diagnosis_summary(self):
    """First 80 characters of diagnosis — used in admin list display."""
    if self.diagnosis:
        return self.diagnosis[:80] + ('...' if len(self.diagnosis) > 80 else '')
    return ''
```

---

#### `VisitFile`
**File:** `patients/models.py`  
A file or external link attached to a visit. Either `file` or `link_url` is populated — not both.

| Field         | Type               | Constraints                                      | Purpose                            |
| ------------- | ------------------ | ------------------------------------------------ | ---------------------------------- |
| `visit`       | ForeignKey → Visit | CASCADE, related_name=`files`                    | Parent visit                       |
| `doctor`      | ForeignKey → User  | CASCADE, related_name=`visit_files`              | Uploading doctor                   |
| `title`       | CharField(200)     | required                                         | Display name                       |
| `file_type`   | CharField(20)      | choices: lab_result/xray/prescription/scan/other | Category                           |
| `file`        | FileField          | upload_to=`visit_files/`, null, blank            | Actual uploaded file               |
| `link_url`    | URLField(1000)     | null, blank                                      | External URL (alternative to file) |
| `uploaded_at` | DateTimeField      | auto_now_add                                     | Upload timestamp                   |
| `notes`       | TextField          | null, blank                                      | Optional annotation                |

**Meta:** `indexes`: `(visit)`, `(doctor)`

**Custom Properties:**

```python
@property
def is_link(self):    return bool(self.link_url)
@property
def is_image(self):   return file.name ends with .jpg/.jpeg/.png
@property
def is_pdf(self):     return file.name ends with .pdf
@property
def file_size_display(self):  # Returns "1.4 MB", "230 KB", etc.
```

---

#### `MedicalDictionary`
**File:** `patients/models.py`  
Master word list of known correct medical terms and drug names used for fuzzy matching.

| Field        | Type           | Constraints                                     | Purpose                  |
| ------------ | -------------- | ----------------------------------------------- | ------------------------ |
| `word`       | CharField(200) | unique, db_index                                | The correct medical term |
| `category`   | CharField(50)  | choices: drug/diagnosis/symptom/procedure/other | Term type                |
| `created_at` | DateTimeField  | auto_now_add                                    | When added               |

**Meta:** `verbose_name = 'Medical Dictionary'`  
**Typical size:** 14,000+ Egyptian drug trade names after running `import_drugs`

---

#### `TranscriptionCorrection`
**File:** `patients/models.py`  
Per-doctor personal learning table. When a doctor confirms a suggestion, the wrong→correct mapping is stored here and applied automatically in future transcriptions.

| Field          | Type              | Constraints                                       | Purpose                                  |
| -------------- | ----------------- | ------------------------------------------------- | ---------------------------------------- |
| `doctor`       | ForeignKey → User | CASCADE, related_name=`transcription_corrections` | Which doctor's correction                |
| `wrong_word`   | CharField(200)    | db_index                                          | The incorrectly transcribed word         |
| `correct_word` | CharField(200)    | —                                                 | The confirmed correct spelling           |
| `usage_count`  | IntegerField      | default=1                                         | Times this correction has been confirmed |
| `created_at`   | DateTimeField     | auto_now_add                                      | First correction date                    |
| `updated_at`   | DateTimeField     | auto_now                                          | Last update date                         |

**Meta:** `unique_together = ('doctor', 'wrong_word')`, `ordering = ['-usage_count']`

---

## 4. URL Routes

### Root (`clinic/urls.py`)

| URL Pattern                | View                           | Auth  | Description               |
| -------------------------- | ------------------------------ | ----- | ------------------------- |
| `/admin/`                  | Django admin site              | staff | Built-in Django admin     |
| `/sw.js`                   | TemplateView (templates/sw.js) | none  | Serves the Service Worker |
| `/`                        | redirect → `login`             | none  | Root redirects to login   |
| + includes `accounts.urls` | —                              | —     | Auth + admin panel routes |
| + includes `patients.urls` | —                              | —     | Clinical data routes      |

### Accounts (`accounts/urls.py`)

| URL Pattern                                 | View                    | Auth        | Description                |
| ------------------------------------------- | ----------------------- | ----------- | -------------------------- |
| `/login/`                                   | `login_view`            | none        | Login page                 |
| `/register/`                                | `register`              | none        | Doctor self-registration   |
| `/logout/`                                  | `logout_view`           | none        | Logs user out              |
| `/admin-panel/`                             | `admin_dashboard`       | admin       | Clinic analytics dashboard |
| `/admin-panel/manage-doctors/`              | `manage_doctors`        | admin       | Doctor management list     |
| `/admin-panel/doctors/add/`                 | `add_doctor`            | admin       | Add new doctor             |
| `/admin-panel/doctors/<pk>/edit/`           | `edit_doctor`           | admin       | Edit doctor profile        |
| `/admin-panel/doctors/<pk>/reset-password/` | `reset_doctor_password` | admin       | Reset doctor password      |
| `/admin-panel/doctors/<pk>/toggle/`         | `toggle_doctor_status`  | admin, POST | Activate/deactivate doctor |
| `/admin-panel/doctors/<pk>/delete/`         | `delete_doctor`         | admin       | Delete doctor account      |

### Patients (`patients/urls.py`)

| URL Pattern                  | View                   | Auth         | Description                         |
| ---------------------------- | ---------------------- | ------------ | ----------------------------------- |
| `/dashboard/`                | `dashboard`            | doctor       | Doctor's home page                  |
| `/patients/`                 | `patient_list`         | doctor       | Paginated patient list              |
| `/patients/add/`             | `add_patient`          | doctor       | Add new patient                     |
| `/patients/<pk>/`            | `patient_detail`       | doctor       | Patient profile + visit history     |
| `/patients/<pk>/files/`      | `patient_files`        | doctor       | All files for this patient          |
| `/patients/<pk>/edit/`       | `edit_patient`         | doctor       | Edit patient demographics           |
| `/patients/<pk>/delete/`     | `delete_patient`       | doctor, POST | Delete patient record               |
| `/patients/<pk>/add-visit/`  | `add_visit`            | doctor       | Add new visit                       |
| `/visits/<pk>/`              | `visit_detail`         | doctor       | View full visit record              |
| `/visits/<pk>/edit/`         | `edit_visit`           | doctor       | Edit existing visit                 |
| `/visits/<pk>/delete/`       | `delete_visit`         | doctor, POST | Delete visit                        |
| `/visits/<pk>/print/`        | `visit_print`          | doctor       | Printable visit summary             |
| `/visits/files/<pk>/delete/` | `delete_visit_file`    | doctor, POST | Remove an attachment                |
| `/search-patients/`          | `search_patients`      | doctor, GET  | AJAX patient search (JSON)          |
| `/pending-visits/`           | `pending_visits`       | doctor       | Offline pending visits page         |
| `/sync-offline-visit/`       | `sync_offline_visit`   | doctor, POST | Sync IndexedDB visit to DB          |
| `/transcribe-visit/`         | `transcribe_and_parse` | doctor, POST | Voice → structured fields (JSON)    |
| `/check-suggestions/`        | `check_suggestions`    | doctor, POST | Fuzzy match suggestions (JSON)      |
| `/save-correction/`          | `save_correction`      | doctor, POST | Persist confirmed correction (JSON) |

---

## 5. Views & Business Logic

### `patients/views.py`

#### `dashboard`
- **URL:** `/dashboard/`
- **Auth:** `@doctor_required`
- **Methods:** GET
- **Logic:** Counts total patients, today's visits, and this month's visits for the logged-in doctor using three separate but simple `.count()` queries.
- **Returns:** `patients/dashboard.html` with `total_patients`, `today_visits`, `month_visits`

---

#### `search_patients`
- **URL:** `/search-patients/?q=`
- **Auth:** `@doctor_required`, `@require_GET`
- **Methods:** GET
- **Logic:** If query is ≥ 2 characters, runs a single query with `Q(name__icontains=query) | Q(phone__icontains=query)`, bounded to 10 results. For each result, the `patient.last_visit` property is called (1 DB query per patient — acceptable at max 10 rows).
- **Returns:** JSON `{results: [{id, name, phone, age, last_visit_date}, ...], query}`

---

#### `patient_list`
- **URL:** `/patients/`
- **Auth:** `@doctor_required`
- **Methods:** GET
- **Logic:**
  1. Filters patients by doctor, optional name/phone query, optional gender filter
  2. Paginates at 10 per page
  3. For each page, re-fetches only the page's PKs with annotations (`visit_count`, `last_visit_date`) to avoid N+1 on the full queryset
- **Returns:** `patients/patient_list.html` with `page_obj`, `query`, `gender_filter`, `total_patients_count`, `total_visits_count`

---

#### `patient_detail`
- **URL:** `/patients/<pk>/`
- **Auth:** `@doctor_required`
- **Methods:** GET
- **Logic:** Fetches patient (404 if not owned by doctor), fetches visits with `.only()` + `file_count` annotation, paginates at 10 per page.
- **Returns:** `patients/patient_detail.html`

---

#### `patient_files`
- **URL:** `/patients/<pk>/files/`
- **Auth:** `@doctor_required`
- **Methods:** GET
- **Logic:** Returns all VisitFile objects for a patient, ordered by visit date descending, with `select_related('visit')` to avoid N+1.
- **Returns:** `patients/patient_files.html`

---

#### `add_patient` / `edit_patient`
- **URL:** `/patients/add/` and `/patients/<pk>/edit/`
- **Auth:** `@doctor_required`
- **Methods:** GET (form), POST (save)
- **Logic:** Both support AJAX (`X-Requested-With: XMLHttpRequest`) — return JSON on success/failure. Non-AJAX falls back to full-page redirect. Validation is done via `_fill_patient_from_post()` helper.
- **Returns:** JSON on AJAX or redirect to `patient_detail`

---

#### `delete_patient`
- **URL:** `/patients/<pk>/delete/`
- **Auth:** `@doctor_required`
- **Methods:** POST only
- **Logic:** Verifies ownership, deletes. Returns 405 JSON on non-POST.
- **Returns:** JSON `{success, message}`

---

#### `add_visit`
- **URL:** `/patients/<pk>/add-visit/`
- **Auth:** `@doctor_required`
- **Methods:** GET (form), POST (save)
- **Logic (POST):**
  1. Validates at least one clinical field is filled
  2. Parses `visit_date` with `parse_datetime`; falls back to `timezone.now()`
  3. Creates `Visit` record
  4. Iterates uploaded files: checks extension, size (max 10 MB), creates `VisitFile` for each
  5. Iterates submitted link URLs, creates `VisitFile` with `link_url` set
  6. Collects file errors as warnings, redirects to `visit_detail`
- **Returns:** Redirect to `visit_detail` or re-render form with errors

---

#### `edit_visit`
- **URL:** `/visits/<pk>/edit/`
- **Auth:** `@doctor_required`
- **Methods:** GET, POST
- **Logic:** Same as `add_visit` but updates an existing visit. New files/links are appended (existing attachments are not removed unless explicitly deleted).
- **Returns:** Redirect to `visit_detail`

---

#### `visit_detail`
- **URL:** `/visits/<pk>/`
- **Auth:** `@doctor_required`
- **Methods:** GET
- **Logic:** Fetches visit with `select_related('patient', 'doctor', 'doctor__doctor_profile')`. Loads all files **once** into Python, then splits into images/pdfs/links/other in a single pass — avoids 4 separate DB queries.
- **Returns:** `patients/visit_detail.html` with `visit`, `files`, `images`, `pdfs`, `links`, `other_files`

---

#### `visit_print`
- **URL:** `/visits/<pk>/print/`
- **Auth:** `@doctor_required`
- **Methods:** GET
- **Logic:** Same fetch as `visit_detail` but renders a print-optimised template.
- **Returns:** `patients/visit_print.html`

---

#### `delete_visit`
- **URL:** `/visits/<pk>/delete/`
- **Auth:** `@doctor_required`
- **Methods:** POST only
- **Returns:** JSON `{success, message}`

---

#### `delete_visit_file`
- **URL:** `/visits/files/<pk>/delete/`
- **Auth:** `@doctor_required`
- **Methods:** POST (delete form), GET (confirmation page)
- **Logic:** On POST, calls `vf.file.delete(save=False)` to remove the physical file from disk before deleting the DB record.
- **Returns:** Redirect to `visit_detail`

---

#### `pending_visits`
- **URL:** `/pending-visits/`
- **Auth:** `@doctor_required`
- **Methods:** GET
- **Logic:** Template-only page. Actual offline visits data lives in the browser's IndexedDB — served by `offline.js`.
- **Returns:** `patients/pending_visits.html`

---

#### `sync_offline_visit`
- **URL:** `/sync-offline-visit/`
- **Auth:** `@doctor_required`
- **Methods:** POST
- **Logic:** Receives JSON body, validates `patient_id` ownership, creates `Visit` record using same logic as `add_visit` (without files — offline visits are text-only).
- **Returns:** JSON `{success, visit_id, offline_id}`

---

#### `check_suggestions`
- **URL:** `/check-suggestions/`
- **Auth:** `@doctor_required`, `@require_POST`
- **Methods:** POST (JSON body)
- **Logic:** Calls `find_suggestions(text, doctor)` from `utils.py`.
- **Returns:** JSON `{success, corrected_text, suggestions: [{original, suggestion, score}, ...]}`

---

#### `save_correction`
- **URL:** `/save-correction/`
- **Auth:** `@doctor_required`, `@require_POST`
- **Methods:** POST (JSON body)
- **Logic:**
  1. Creates or updates `TranscriptionCorrection` record
  2. Increments `usage_count` on update
  3. Adds `correct_word` to `MedicalDictionary` if not present
  4. Invalidates the `medical_dictionary_words` cache key
- **Returns:** JSON `{success, message, usage_count}`

---

#### `transcribe_and_parse`
- **URL:** `/transcribe-visit/`
- **Auth:** `@doctor_required`, `@require_POST`
- **Methods:** POST (multipart/form-data with `audio` file)
- **Logic:** See [Section 6 — Voice Transcription System](#6-voice-transcription-system)
- **Returns:** JSON `{success, transcript, fields: {...}, fallback_used}`

---

### `accounts/views.py`

#### `login_view`
- **URL:** `/login/`
- **Methods:** GET, POST
- **Logic:**
  1. Redirects already-authenticated users to their role's home
  2. On POST: validates credentials, checks if account is inactive *before* `authenticate()` to give a specific "pending approval" error
  3. On success: redirects to `admin_dashboard` or `dashboard` based on role
- **Returns:** `accounts/login.html`

---

#### `logout_view`
- **URL:** `/logout/`
- **Methods:** GET and POST (both log out — GET is for convenience)
- **Returns:** Redirect to `login`

---

#### `register`
- **URL:** `/register/`
- **Methods:** GET, POST
- **Logic:** Creates `User` with `is_active=False`, creates `UserProfile(role='doctor')` and `DoctorProfile`. Account is inactive until an admin activates it.
- **Returns:** `accounts/register.html`, redirect to login on success

---

#### `admin_dashboard`
- **URL:** `/admin-panel/`
- **Auth:** `@admin_required`
- **Methods:** GET
- **Logic:** Aggregates clinic-wide statistics in a single pass, including doctor leaderboards (annotated queryset — no N+1), most-visited patients, recent visits, daily/weekly breakdown using two annotated queries.
- **Returns:** `accounts/admin_dashboard.html` with ~25 context variables

---

#### `manage_doctors`
- **URL:** `/admin-panel/manage-doctors/`
- **Auth:** `@admin_required`
- **Methods:** GET
- **Logic:** Single annotated queryset fetching all doctors with patient_count, visit_count, today_count, month_count, last_visit_date — no loops with extra queries.
- **Returns:** `accounts/manage_doctors.html`

---

#### `add_doctor` / `edit_doctor` / `reset_doctor_password` / `toggle_doctor_status` / `delete_doctor`
- **Auth:** `@admin_required`
- **Methods:** POST for mutations, GET for forms
- **Key Logic:**
  - `add_doctor`: Creates User + UserProfile + DoctorProfile atomically
  - `delete_doctor`: Blocked if doctor has patients (prevents orphaned records)
  - `toggle_doctor_status`: Uses `update_fields=['is_active']` for single-field update efficiency
- **Returns:** JSON responses for all POST actions

---

## 6. Voice Transcription System

The complete pipeline from button click to populated form fields:

### 6.1 Browser Recording (`static/js/voice.js`)

```
Doctor clicks "Record Visit" button
    ↓
navigator.mediaDevices.getUserMedia({ audio: true })
    ↓
MediaRecorder records as audio/webm chunks
    ↓
Doctor clicks "Stop Recording"
    ↓
mediaRecorder.stop() → onstop fires → sendRecording()
```

**ESC to cancel:**---

### 3. Login Page & Registration

- **Removed Registration**: Deleted the `register` view, URL, and template.
- **Rebranded Login**: rewritten `login.html` with Green/Red El-Basma branding and BC SVG logo.

---

### 4. Multi-Doctor Feature Removal

- **Cleaned `accounts/views.py`**: Removed all doctor management views (`manage_doctors`, `add_doctor`, etc.).
- **Simplified URLs**: Removed all doctor CRUD routes.
- **Simplified Templates**: Removed doctor performance tables and management links from the admin dashboard.
- **Deleted Dead Code**: Removed 5 unused `.html` templates from the accounts folder.

---

### 5. Global Branding Sweep

- Replaced all remaining instances of "MediTrack" in titles, metadata, and service workers with **El-Basma Clinic**.

### 6.2 Sending to Backend (`voice.js` → `transcribe_and_parse`)

```javascript
// voice.js — sendRecording()
const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
const formData = new FormData();
formData.append('audio', audioBlob, 'visit.webm');
fetch('/transcribe-visit/', { method: 'POST', headers: { 'X-CSRFToken': CSRF_TOKEN }, body: formData })
```

---

### 6.3 Groq Whisper Transcription (Layer 1)

```python
# patients/views.py — transcribe_and_parse()
# 1. Write audio to temp file
with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as tmp:
    for chunk in audio_file.chunks():
        tmp.write(chunk)

# 2. Send to Groq Whisper Large V3
client = _Groq(api_key=settings.GROQ_API_KEY)
transcription = client.audio.transcriptions.create(
    file=(os.path.basename(tmp_path), f),
    model="whisper-large-v3",
    prompt=MEDICAL_PROMPT,   # Arabic + English drug names hint
    response_format="text",
    timeout=30
)
```

The `MEDICAL_PROMPT` is a comma-separated list of common Arabic and English drug names passed as a pronunciation hint to Whisper, improving medical term recognition.

---

### 6.4 Llama Parsing (Layer 2 — Primary)

The raw transcript is sent to `llama-3.1-8b-instant` on Groq with a structured system prompt:

```python
# PARSE_SYSTEM_PROMPT (patients/views.py)
# Instructs the LLM to extract 10 clinical fields from Arabic/mixed transcript:
# chief_complaint, symptoms, diagnosis, treatment, doctor_notes,
# temperature, blood_pressure, pulse, weight, next_checkup_date
#
# Trigger words for each field are defined (e.g. "شكوى" → chief_complaint)
# Rules: extract only what was said, no translation, no modification
# Return: JSON only, no markdown
```

The LLM response is parsed with `json.loads()`. If the response contains markdown code fences, they are stripped before parsing.

---

### 6.5 OpenAI Fallback (Layer 2b — Secondary)

If Groq's LLM call fails (rate limit, timeout, error):

```python
if _OpenAI and settings.OPENAI_API_KEY:
    oa_client = _OpenAI(api_key=settings.OPENAI_API_KEY)
    oa_completion = oa_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": PARSE_SYSTEM_PROMPT}, ...]
    )
```

---

### 6.6 Regex Fallback (Layer 3 — Tertiary)

If both AI providers fail, `regex_parse_transcript()` in `utils.py` extracts fields using Arabic keyword regex patterns:

```python
# patients/utils.py — regex_parse_transcript()
patterns = {
    'chief_complaint': [r'شكو[اةى][^،\n]*'],
    'symptoms':  [r'أعراض[^،\n]*', r'علامات[^،\n]*'],
    'diagnosis': [r'تشخيص[^،\n]*', r'تشخيصي[^،\n]*'],
    'treatment': [r'علاج[^،\n]*', r'وصفة[^،\n]*', r'دواء[^،\n]*'],
    # ... temperature, blood_pressure, pulse, weight, doctor_notes
}
```

---

### 6.7 Field Population (Browser)

```javascript
// voice.js — fillFields()
Object.entries(data.fields).forEach(([fieldId, value]) => {
    const field = document.getElementById(fieldId);
    field.value += (field.value ? ' ' : '') + value.trim();
    field.dispatchEvent(new Event('input'));
});
```

After filling fields, `checkAllFieldsForSuggestions()` is called.

---

### 6.8 Full Data Flow

```
[Doctor speaks] → MediaRecorder (webm)
    ↓
POST /transcribe-visit/ (multipart audio blob)
    ↓
[Backend] Write to tmp file
    ↓
Groq Whisper Large V3 → raw Arabic/mixed transcript
    ↓
Groq Llama 3.1 8B → JSON fields
    (on failure) → OpenAI GPT-4o-mini → JSON fields
    (on failure) → regex_parse_transcript() → JSON fields
    ↓
JSON response: { success, transcript, fields, fallback_used }
    ↓
[Browser] fillFields() → populates form
    ↓
checkAllFieldsForSuggestions() → POST /check-suggestions/ per field
    ↓
[Backend] find_suggestions() → fuzzy match against MedicalDictionary
    ↓
Auto-corrections applied silently + popups shown for uncertain matches
    ↓
Doctor confirms suggestion → POST /save-correction/ → stored in TranscriptionCorrection
```

---

## 7. Authentication System

### Login Flow

```python
# accounts/views.py — login_view()
# Step 1: Check if account exists but is inactive
try:
    temp_user = User.objects.get(username=username)
    if not temp_user.is_active and temp_user.check_password(password):
        messages.error("Your account is pending admin approval.")
        return render(...)
except User.DoesNotExist:
    pass

# Step 2: Normal authenticate
user = authenticate(request, username=username, password=password)
if user:
    login(request, user)
    # Redirect based on role
    role = user.profile.role
    if role == 'admin': return redirect('admin_dashboard')
    if role == 'doctor': return redirect('dashboard')
```

### `@doctor_required` Decorator

```python
# accounts/decorators.py
def doctor_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.is_active:
            logout(request)
            return redirect('login')
        try:
            profile = request.user.profile
            if profile.role == 'admin':
                return redirect('admin_dashboard')  # admins can't access doctor views
            if profile.role != 'doctor':
                return redirect('login')
        except UserProfile.DoesNotExist:
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper
```

### `@admin_required` Decorator

Similar to `@doctor_required` but redirects doctors to `/dashboard/` instead.

### `@post_required` Decorator

Returns `405 Method Not Allowed` JSON for any non-POST request. Used on state-mutating AJAX endpoints.

### Session Configuration

```python
# clinic/settings.py
SESSION_COOKIE_AGE = 86400          # 1 day default
SESSION_SAVE_EVERY_REQUEST = True   # Refresh expiry on each request
SESSION_EXPIRE_AT_BROWSER_CLOSE = True  # Clears on browser close unless "remember me"
```

---

## 8. File Upload System

### Supported Formats

| Type      | Extensions              | Max Size |
| --------- | ----------------------- | -------- |
| Images    | `.jpg`, `.jpeg`, `.png` | 10 MB    |
| Documents | `.pdf`                  | 10 MB    |
| Links     | External URL (no file)  | N/A      |

### Validation (Backend)

```python
# patients/views.py
ALLOWED_EXTENSIONS = frozenset(['.jpg', '.jpeg', '.png', '.pdf'])
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

# For each uploaded file:
if ext not in ALLOWED_EXTENSIONS:
    file_errors.append(f'"{f.name}": Only JPG, PNG, and PDF files are allowed.')
if f.size > MAX_FILE_SIZE:
    file_errors.append(f'"{f.name}": File too large. Maximum size is 10 MB.')
```

### Storage

Files are stored at `media/visit_files/` on the local filesystem. In `settings.py`:

```python
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024   # 20 MB form body max
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024   # 10 MB per file
```

### Deletion

When a `VisitFile` is deleted, the physical file is removed from disk first:

```python
# patients/views.py — delete_visit_file()
vf.file.delete(save=False)   # Removes from disk
vf.delete()                   # Removes DB record
```

### Frontend (`upload.js`)

- Drag-and-drop zone or click-to-browse
- File type and size are validated in the browser before the form is submitted
- Image files get an inline preview using `FileReader.readAsDataURL()`
- Multiple files can be selected; each gets its own title/type/notes inputs
- Files can be removed before submission; `DataTransfer` is rebuilt on each removal

---

## 9. Drug Dictionary System

### Data Source

`egyptian_drugs.txt` — a plain text file with one Arabic drug trade name per line, containing 14,000+ entries scraped from Egyptian drug databases.

### Importing

```bash
python manage.py import_drugs
# Output: Done. Created: 14321, Already existed: 0, Total: 14321
```

The command uses `get_or_create` to be idempotent — safe to run multiple times.

### Caching

```python
# patients/utils.py — get_dictionary_words()
def get_dictionary_words():
    cached = cache.get('medical_dictionary_words')
    if cached is not None:
        return cached
    words = list(MedicalDictionary.objects.values_list('word', flat=True))
    cache.set('medical_dictionary_words', words, timeout=3600)  # 1 hour
    return words
```

Django uses `LocMemCache` (configured in `settings.py`), so this is an **in-process** cache. Cache is invalidated by `save_correction` whenever a new word is added.

### Fuzzy Matching (`patients/utils.py`)

```python
# find_suggestions(text, doctor)
# 1. Fetch all personal corrections + build correction_map (single DB query)
# 2. Apply personal corrections word-by-word → corrected_text
# 3. Load dictionary words from cache (or DB if cache miss)
# 4. For each word in corrected_text (4+ chars, only Arabic/medical):
#    - rapidfuzz.process.extractOne(word, dictionary_words, scorer=fuzz.WRatio, score_cutoff=70)
#    - If match found and match != word → add to suggestions list
# 5. Return (corrected_text, suggestions)
```

**Scorer:** `fuzz.WRatio` — weighted ratio that handles partial matches and character transpositions. Chosen for Arabic drug names where a single character difference (e.g. ميوكوتيك vs ميوكوتك) should still score ~93%.

**Threshold:** 70 — deliberately permissive to catch OCR-style misreadings.

**Minimum word length:** 4 characters — prevents matching short prepositions and articles.

### Personal Learning System

When a doctor confirms a suggestion popup:
1. `onsuccess` in `voice.js` calls `POST /save-correction/`
2. `TranscriptionCorrection` record is created/updated in DB
3. On next transcription, `apply_personal_corrections()` applies this mapping automatically (no popup needed)
4. Corrections are per-doctor — each doctor has their own private corrections table

---

## 10. API Endpoints

### `GET /search-patients/`

**Auth:** doctor required  
**Query params:** `?q=<search term>` (min 2 chars)

**Response:**
```json
{
    "results": [
        {
            "id": 42,
            "name": "محمد أحمد",
            "phone": "01234567890",
            "age": 45,
            "last_visit_date": "2026-04-10"
        }
    ],
    "query": "محمد"
}
```

---

### `POST /transcribe-visit/`

**Auth:** doctor required  
**Content-Type:** `multipart/form-data`  
**Body:** `audio` (WebM audio blob)

**Response (success):**
```json
{
    "success": true,
    "transcript": "شكوى ألم في الصدر تشخيص التهاب رئوي علاج أموكسيسيلين 500",
    "fields": {
        "chief_complaint": "ألم في الصدر",
        "symptoms": "",
        "diagnosis": "التهاب رئوي",
        "treatment": "أموكسيسيلين 500",
        "doctor_notes": "",
        "temperature": "",
        "blood_pressure": "",
        "pulse": "",
        "weight": "",
        "next_checkup_date": ""
    },
    "fallback_used": false
}
```

---

### `POST /check-suggestions/`

**Auth:** doctor required  
**Content-Type:** `application/json`  
**Body:**
```json
{ "text": "ميوكوتيك وادول نيلوفوسام وهيليكور" }
```

**Response:**
```json
{
    "success": true,
    "corrected_text": "ميوكوتك وادول نيلوفوسام وهيليكور",
    "suggestions": [
        {
            "original": "ميوكوتيك",
            "suggestion": "ميوكوتك",
            "score": 93.1
        }
    ]
}
```

---

### `POST /save-correction/`

**Auth:** doctor required  
**Content-Type:** `application/json`  
**Body:**
```json
{ "wrong_word": "ميوكوتيك", "correct_word": "ميوكوتك" }
```

**Response:**
```json
{
    "success": true,
    "message": "Correction saved: ميوكوتيك → ميوكوتك",
    "usage_count": 3
}
```

---

### `POST /sync-offline-visit/`

**Auth:** doctor required  
**Content-Type:** `application/json`  
**Body:**
```json
{
    "patient_id": 42,
    "offline_id": 1,
    "chief_complaint": "ألم في الرأس",
    "symptoms": "",
    "diagnosis": "",
    "treatment": "",
    "blood_pressure": "120/80",
    "doctor_notes": "",
    "temperature": null,
    "pulse": null,
    "weight": null,
    "next_checkup_date": null,
    "visit_date": "2026-04-12T10:30:00Z"
}
```

**Response:**
```json
{ "success": true, "visit_id": 387, "offline_id": 1 }
```

---

### Admin CRUD Endpoints (`/admin-panel/doctors/`)

All return:
```json
{ "success": true, "message": "Doctor \"Dr. Ahmed\" updated successfully." }
```
or
```json
{ "success": false, "message": "Username already taken." }
```

---

## 11. Management Commands

### `import_drugs`

**File:** `patients/management/commands/import_drugs.py`  
**Purpose:** Seeds the `MedicalDictionary` table from `egyptian_drugs.txt`

**Usage:**
```bash
# Activate venv first
python manage.py import_drugs
```

**Expected output:**
```
Done. Created: 14321, Already existed: 0, Total: 14321
```

**Behaviour:**
- Reads `egyptian_drugs.txt` from the project root
- Uses `get_or_create` — safe to run multiple times (will report `Already existed: N`)
- All words are imported with `category='drug'`
- Run this command once after initial setup, and again whenever `egyptian_drugs.txt` is updated

---

## 12. Static Files & Frontend

### `static/js/voice.js`

The core voice interface. Contains:

| Function                                   | Purpose                                                              |
| ------------------------------------------ | -------------------------------------------------------------------- |
| `getCSRFToken()`                           | Extracts CSRF token from cookie → meta tag → hidden input            |
| `startRecording()`                         | Requests mic, creates MediaRecorder, starts recording                |
| `stopRecording()`                          | Stops MediaRecorder, sets status to "Analysing…"                     |
| `sendRecording()`                          | Builds FormData, POSTs to `/transcribe-visit/`, calls `fillFields()` |
| `fillFields(fields)`                       | Appends LLM-parsed values to form textareas                          |
| `resetStatusUI()`                          | Clears status message and `voice-active` CSS classes                 |
| `checkAllFieldsForSuggestions(fields)`     | Iterates filled fields, calls `/check-suggestions/` for each         |
| `processSuggestions(suggestions, fieldId)` | Shows suggestion popups one at a time, sequentially                  |
| `showSuggestionPopup(...)`                 | Creates floating dark popup with Yes/No buttons                      |
| `closeActivePopup()`                       | Removes the current active popup                                     |
| `escapeRegex(str)`                         | Escapes special chars for use in `new RegExp()`                      |

**Keyboard:** ESC during recording cancels without sending.

---

### `static/js/offline.js`

Offline-first data layer wrapped in an IIFE. Contains:

| Function                       | Purpose                                                                 |
| ------------------------------ | ----------------------------------------------------------------------- |
| `openDB()`                     | Opens/creates `meditrack_offline` IndexedDB with `pending_visits` store |
| `getDB()`                      | Singleton DB getter — opens once and caches                             |
| `saveVisit(visitData)`         | Saves a visit to IndexedDB with `synced: false`                         |
| `getAllPending()`              | Returns all unsynced visits using the `synced` index                    |
| `markSynced(offlineId)`        | Updates a record's `synced` flag to `true`                              |
| `syncAll()`                    | POSTs all pending visits to `/sync-offline-visit/` one by one           |
| `updatePendingBadge()`         | Updates the nav badge showing count of pending visits                   |
| `setOnline()` / `setOffline()` | Updates banners, network dot colour, triggers sync                      |

**Exposed API:** `window.offlineDB = { saveVisit, getAllPending, markSynced, syncAll }`

---

### `static/js/search.js`

AJAX search for the doctor dashboard. Contains:

| Function                         | Purpose                                       |
| -------------------------------- | --------------------------------------------- |
| `doSearch(query)`                | Fetches `/search-patients/?q=` after debounce |
| `renderResults(patients, query)` | Builds result dropdown HTML                   |
| `highlightMatch(text, query)`    | Wraps matching text in `<mark>` tags          |
| `escHtml(str)`                   | XSS-safe HTML escaping                        |

**Behaviour:**
- 300ms debounce on input
- Minimum 2 characters
- Enter key navigates to first result
- ESC closes dropdown
- Click outside closes dropdown
- `window._focusSearch` exposed for Ctrl+F shortcut

---

### `static/js/upload.js`

Drag-and-drop file upload UI. Contains:

| Function                      | Purpose                                                            |
| ----------------------------- | ------------------------------------------------------------------ |
| `handleFiles(files)`          | Validates type/size, calls `addFileToList()` for valid files       |
| `addFileToList(file)`         | Renders a file card with title/type/notes inputs and image preview |
| `window.removeFile(id, name)` | Removes card from DOM, rebuilds DataTransfer without that file     |
| `showError(msg)`              | Shows auto-disappearing error below drop zone                      |
| `formatSize(bytes)`           | Formats bytes as "1.4 MB", "230 KB", etc.                          |

---

### `static/js/shortcuts.js`

Keyboard shortcuts (all use Ctrl/Cmd):

| Shortcut | Action                                               |
| -------- | ---------------------------------------------------- |
| `Ctrl+M` | Toggle voice recording (calls `window._voiceToggle`) |
| `Ctrl+S` | Submit visit form (if `#visit-form` exists on page)  |
| `Ctrl+F` | Focus the dashboard search input                     |

---

### `templates/sw.js` — Service Worker

Served at `/sw.js` via Django's `TemplateView`. Intercepts network requests and caches static assets for offline access. The template context is used to inject the `CACHE_NAME` dynamically.

---

### CSS

All styles are embedded in `templates/base.html` inside `<style>` tags. There are no external CSS files. The design system uses CSS custom properties (`var(--primary)`, `var(--card-bg)`, etc.). Page-specific styles are added in `{% block extra_head %}` inside individual templates.

---

## 13. Environment Variables & Configuration

### `.env` file (project root)

```env
GROQ_API_KEY=gsk_...
```

Read by `python-decouple` in `settings.py`.

### All Configurable Variables

| Variable         | Purpose                          | Required             | Example                                    |
| ---------------- | -------------------------------- | -------------------- | ------------------------------------------ |
| `GROQ_API_KEY`   | Groq API key for Whisper + Llama | **Yes**              | `gsk_abc123...`                            |
| `OPENAI_API_KEY` | OpenAI fallback key              | No                   | `sk-proj-...`                              |
| `SECRET_KEY`     | Django secret key                | Yes (change in prod) | `django-insecure-...`                      |
| `DEBUG`          | Django debug mode                | Yes                  | `True` (dev), `False` (prod)               |
| `ALLOWED_HOSTS`  | Accepted host headers            | Yes                  | `['*']` (dev), `['yourdomain.com']` (prod) |

### Key `settings.py` Values

| Setting                           | Value                          | Purpose                            |
| --------------------------------- | ------------------------------ | ---------------------------------- |
| `DATABASE`                        | SQLite3, WAL mode, 20s timeout | Local file database                |
| `CACHES`                          | LocMemCache `meditrack-cache`  | In-process 1-hour dictionary cache |
| `SESSION_COOKIE_AGE`              | 86400 (1 day)                  | Default session lifetime           |
| `SESSION_EXPIRE_AT_BROWSER_CLOSE` | True                           | Session ends when browser closes   |
| `DATA_UPLOAD_MAX_MEMORY_SIZE`     | 20 MB                          | Max form body size                 |
| `FILE_UPLOAD_MAX_MEMORY_SIZE`     | 10 MB                          | Max individual file size           |
| `TIME_ZONE`                       | `Africa/Cairo`                 | Server timezone                    |
| `MEDIA_ROOT`                      | `BASE_DIR / 'media'`           | Where uploaded files are stored    |
| `STATIC_ROOT`                     | `BASE_DIR / 'staticfiles'`     | `collectstatic` output directory   |

---

## 14. Deployment Checklist

### 1. Environment

```bash
# Clone the repo
git clone <repo-url> && cd clinic

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# Or: source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Variables

Create `.env` in the project root:
```env
GROQ_API_KEY=gsk_your_production_key
SECRET_KEY=generate-a-new-random-50-char-key
OPENAI_API_KEY=sk-optional-fallback-key
```

Generate a new `SECRET_KEY`:
```python
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 3. Settings Changes for Production

In `clinic/settings.py`:
```python
DEBUG = False
ALLOWED_HOSTS = ['yourdomain.com', 'your-server-ip']
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

### 4. Database Setup

```bash
python manage.py migrate
python manage.py createsuperuser  # Create first admin account
python manage.py import_drugs     # Seed 14,000+ drug names
```

### 5. Static Files

```bash
python manage.py collectstatic --noinput
# Files will be in staticfiles/
```

### 6. Gunicorn + Nginx

```bash
# Install gunicorn
pip install gunicorn

# Run (adjust workers based on CPU cores)
gunicorn clinic.wsgi:application --workers 3 --bind 127.0.0.1:8000
```

Nginx config (simplified):
```nginx
server {
    listen 443 ssl;
    server_name yourdomain.com;

    location /static/ { alias /path/to/clinic/staticfiles/; }
    location /media/  { alias /path/to/clinic/media/; }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 7. Create Admin User via Application

After deploying:
1. Register at `/register/` with the clinic owner's credentials
2. Log into Django admin at `/admin/` with the superuser
3. Find the new user's `UserProfile`, set `role = admin`
4. That account can now access `/admin-panel/` and manage doctors

---

## 15. Known Issues & Limitations

### A. SQLite Concurrency Limit

SQLite with WAL mode is suitable for a single-clinic deployment where one doctor writes at a time. If multiple doctors record visits simultaneously, you may see brief write locks. For high-concurrency use (5+ simultaneous users writing), migrate to PostgreSQL.

```python
# Migration to PostgreSQL in settings.py:
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'meditrack',
        'USER': 'meditrack_user',
        'PASSWORD': '...',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

### B. LocMemCache is Per-Process

`LocMemCache` stores data in Python memory. If you run multiple Gunicorn workers (`--workers 3`), each worker has its own independent cache. A cache invalidation in one worker does not affect others.

**Fix for multi-worker deployments:** Replace with Redis:
```python
# pip install django-redis
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",
    }
}
```

### C. Groq Rate Limits

The free/starter Groq tier has daily token limits. For a clinic with 200+ patients/day:
- Whisper: 200 calls/day vs 2,000 RPD limit — safe
- Llama 3.1 8B: ~500 tokens/visit × 200 patients = 100,000 tokens vs 500,000 TPD limit — safe

If limits are reached, the system falls back to OpenAI → Regex automatically.

### D. `last_visit` Property in `search_patients`

The `patient.last_visit` property is called once per search result (max 10). This is an intentional design choice — the result set is bounded and annotating would require a subquery. At scale this is 10 extra queries per search, which is acceptable.

### E. Logout Accepts GET Requests

`/logout/` logs users out on both GET and POST. A malicious page could embed `<img src="/logout/">` to log out a doctor. To harden: change the sidebar logout link to a small form with POST method.

### F. `static/css/` Is Empty

All CSS is embedded in `base.html` and individual template `{% block extra_head %}` blocks. This makes it easy to inspect but harder to cache independently. For production, extract to `.css` files.

### G. No HTTPS Enforcement in Dev

`SECURE_SSL_REDIRECT = False` in dev. The `.env` GROQ_API_KEY is therefore transmitted in cleartext if accessed over plain HTTP from another device on the LAN. Enable SSL or use a tunnel (e.g. `ngrok`) if testing from mobile devices.

### H. Media Files Not Backed Up

Uploaded patient files are stored on the local disk at `media/visit_files/`. There is no automated backup. For production, configure periodic backups of this directory or use Django's `storages` library with S3.

---

*End of Documentation — MediTrack v1.0*
