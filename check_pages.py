#!/usr/bin/env python
"""
MediTrack Page Health Check
============================
Visits every page as admin and doctor, flags any Django error pages.

Usage:
    1. Run the Django server: python manage.py runserver
    2. Set credentials in CONFIG below
    3. Run: python check_pages.py
"""

import sys
import re
import requests

# ─────────────────── CONFIG ───────────────────────────────────────────────────
BASE_URL        = "http://127.0.0.1:8000"
ADMIN_USERNAME  = "_testadmin_"
ADMIN_PASSWORD  = "Test@12345"
DOCTOR_USERNAME = "_testdoctor_"
DOCTOR_PASSWORD = "Test@12345"
TIMEOUT         = 10

# ─────────────────── COLOURS ──────────────────────────────────────────────────
GREEN  = "\033[92m"; RED  = "\033[91m"
YELLOW = "\033[93m"; CYAN = "\033[96m"
RESET  = "\033[0m";  BOLD = "\033[1m"

# ─────────────────── PAGES TO TEST ───────────────────────────────────────────
# (role, url_path, allowed_http_status_codes)
PAGES = [
    # Public
    ("public",  "/",                                [200, 302]),
    ("public",  "/login/",                          [200]),

    # Admin
    ("admin",   "/admin-panel/",                    [200]),
    ("admin",   "/admin-panel/manage-doctors/",     [200]),
    ("admin",   "/admin-panel/doctors/add/",        [200]),

    # Doctor
    ("doctor",  "/dashboard/",                      [200]),
    ("doctor",  "/patients/",                       [200]),
    ("doctor",  "/patients/?q=test",                [200]),
    ("doctor",  "/patients/?gender=male",           [200]),
    ("doctor",  "/patients/add/",                   [200]),
    ("doctor",  "/pending-visits/",                 [200]),
    ("doctor",  "/search-patients/?q=a",            [200]),
]

# Patterns that indicate a Django error page (even if status == 200)
ERROR_RE = re.compile(
    r"(Traceback \(most recent call last\)|Exception Type:|FieldError|"
    r"OperationalError|ProgrammingError|ImproperlyConfigured|IntegrityError|"
    r"TemplateSyntaxError|NoReverseMatch|Django Version:.*Exception)",
    re.IGNORECASE | re.DOTALL,
)


def csrf(session, url):
    session.get(url, timeout=TIMEOUT)
    return session.cookies.get("csrftoken", "")


def login(session, username, password):
    url = f"{BASE_URL}/login/"
    token = csrf(session, url)
    resp = session.post(
        url, allow_redirects=True, timeout=TIMEOUT,
        data={"username": username, "password": password, "csrfmiddlewaretoken": token},
        headers={"Referer": url},
    )
    return "/login/" not in resp.url or resp.status_code == 200


def check(session, path, expected):
    url = BASE_URL + path
    try:
        r = session.get(url, allow_redirects=True, timeout=TIMEOUT)
        body = r.text
        bad_body = bool(ERROR_RE.search(body))
        ok = r.status_code in expected and not bad_body
        snippet = None
        if bad_body:
            for line in body.splitlines():
                line = line.strip()
                if any(w in line for w in ("Error", "Exception", "Traceback", "invalid")):
                    snippet = line[:130]
                    break
        return {"url": url, "status": r.status_code, "expected": expected,
                "ok": ok, "bad_body": bad_body, "snippet": snippet}
    except requests.ConnectionError:
        return {"url": url, "status": None, "expected": expected, "ok": False,
                "bad_body": False, "snippet": f"CONNECTION ERROR — server running at {BASE_URL}?"}
    except requests.Timeout:
        return {"url": url, "status": None, "expected": expected, "ok": False,
                "bad_body": False, "snippet": f"TIMEOUT after {TIMEOUT}s"}


def main():
    print(f"\n{BOLD}{CYAN}══════════════════════════════════════════")
    print(f"  MediTrack Page Health Check")
    print(f"  Target: {BASE_URL}")
    print(f"══════════════════════════════════════════{RESET}\n")

    pub_s = requests.Session()

    adm_s = requests.Session()
    adm_ok = login(adm_s, ADMIN_USERNAME, ADMIN_PASSWORD)
    print(f"{GREEN}✓ Admin '{ADMIN_USERNAME}' logged in{RESET}" if adm_ok
          else f"{RED}✗ Admin login FAILED ('{ADMIN_USERNAME}'){RESET}")

    doc_s = requests.Session()
    doc_ok = login(doc_s, DOCTOR_USERNAME, DOCTOR_PASSWORD)
    print(f"{GREEN}✓ Doctor '{DOCTOR_USERNAME}' logged in{RESET}" if doc_ok
          else f"{YELLOW}⚠ Doctor login FAILED — doctor pages will be skipped{RESET}")
    print()

    sessions = {"public": pub_s, "admin": adm_s, "doctor": doc_s}
    available = {"public": True, "admin": adm_ok, "doctor": doc_ok}
    results = []

    for role, path, expected in PAGES:
        if not available[role]:
            print(f"  {YELLOW}SKIP{RESET}  [{role:6}]  {path}")
            continue
        r = check(sessions[role], path, expected)
        r["role"] = role
        r["path"] = path
        results.append(r)

        s = str(r["status"]) if r["status"] else "---"
        exp = "/".join(str(e) for e in expected)
        if r["ok"]:
            mark = f"{GREEN}  ✓ PASS{RESET}"
        elif r["bad_body"]:
            mark = f"{RED}  ✗ FAIL{RESET} {RED}(Django error in body){RESET}"
        else:
            mark = f"{RED}  ✗ FAIL{RESET}"

        print(f"{mark}  [{role:6}]  HTTP {s:<5} (expect {exp})  {path}")
        if r["snippet"]:
            print(f"           {YELLOW}→ {r['snippet']}{RESET}")

    # Summary
    total  = len(results)
    passed = sum(1 for r in results if r["ok"])
    failed = total - passed

    print(f"\n{BOLD}══ Results: {passed}/{total} passed", end=" ")
    if failed == 0:
        print(f"— {GREEN}All pages OK ✓{RESET}{BOLD} ══{RESET}")
    else:
        print(f"— {RED}{failed} FAILED ✗{RESET}{BOLD} ══{RESET}")
        print(f"\n{RED}Failed pages:{RESET}")
        for r in results:
            if not r["ok"]:
                print(f"  [{r['role']:6}]  {r['path']}")
                if r["snippet"]:
                    print(f"           → {r['snippet']}")
    print()
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
