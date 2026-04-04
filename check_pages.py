#!/usr/bin/env python
"""
MediTrack Page Health Check
============================
Visits every page as admin and doctor, flags any Django error pages.
Automatically discovers real Patient and Visit IDs for testing.

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
ADMIN_USERNAME  = "medoledo144"
ADMIN_PASSWORD  = "0543509195Te"
DOCTOR_USERNAME = "Basyony12"
DOCTOR_PASSWORD = "0543509195Te"
TIMEOUT         = 10

# ─────────────────── COLOURS ──────────────────────────────────────────────────
GREEN  = "\033[92m"; RED  = "\033[91m"
YELLOW = "\033[93m"; CYAN = "\033[96m"
RESET  = "\033[0m";  BOLD = "\033[1m"

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
    try:
        token = csrf(session, url)
        resp = session.post(
            url, allow_redirects=True, timeout=TIMEOUT,
            data={"username": username, "password": password, "csrfmiddlewaretoken": token},
            headers={"Referer": url},
        )
        success = "/login/" not in resp.url and resp.status_code == 200
        if not success:
            print(f"  {YELLOW}DEBUG: Login failed for {username}. Final URL: {resp.url}, Status: {resp.status_code}{RESET}")
        return success
    except Exception as e:
        print(f"  {RED}DEBUG: Login error for {username}: {e}{RESET}")
        return False


def check(session, path, expected):
    url = BASE_URL + path
    try:
        r = session.get(url, allow_redirects=True, timeout=TIMEOUT)
        body = r.text
        
        # Detect if we were kicked out to the login page
        if "/login/" in r.url and "/login/" not in path:
            return {"url": url, "status": r.status_code, "expected": expected,
                    "ok": False, "bad_body": False, "snippet": f"REDIRECTED TO LOGIN (unauthorized?)"}
        
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


def get_first_ids(session):
    """Hits the patient list to scrape the first available patient and visit ID."""
    p_resp = session.get(f"{BASE_URL}/patients/", timeout=TIMEOUT)
    # Corrected regex to find patient IDs
    p_match = re.search(r'/patients/(\d+)/', p_resp.text)
    p_id = p_match.group(1) if p_match else None
    
    v_id = None
    if p_id:
        d_resp = session.get(f"{BASE_URL}/patients/{p_id}/", timeout=TIMEOUT)
        v_match = re.search(r'/visits/(\d+)/', d_resp.text)
        v_id = v_match.group(1) if v_match else None
        
    return p_id, v_id


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

    # Dynamic ID discovery
    p_id = None; v_id = None
    if doc_ok:
        p_id, v_id = get_first_ids(doc_s)
        if p_id: print(f"{CYAN}ℹ Found Patient ID: {p_id}{RESET}")
        if v_id: print(f"{CYAN}ℹ Found Visit ID: {v_id}{RESET}")
        print()

    # ─────────────────── PAGES TO TEST ───────────────────────────────────────
    PAGES = [
        ("public",  "/",                                [200, 302]),
        ("public",  "/login/",                          [200]),
        ("admin",   "/admin-panel/",                    [200]),
        ("admin",   "/admin-panel/manage-doctors/",     [200]),
        ("admin",   "/admin-panel/doctors/add/",        [200]),
        ("doctor",  "/dashboard/",                      [200]),
        ("doctor",  "/patients/",                       [200]),
        ("doctor",  "/patients/?q=test",                [200]),
        ("doctor",  "/patients/?gender=male",           [200]),
        ("doctor",  "/patients/add/",                   [200]),
        ("doctor",  "/pending-visits/",                 [200]),
        ("doctor",  "/search-patients/?q=a",            [200]),
    ]
    
    if p_id:
        PAGES += [
            ("doctor", f"/patients/{p_id}/",            [200]),
            ("doctor", f"/patients/{p_id}/edit/",       [200]),
            ("doctor", f"/patients/{p_id}/files/",      [200]),
            ("doctor", f"/patients/{p_id}/add-visit/",  [200]),
        ]
    if v_id:
        PAGES += [
            ("doctor", f"/visits/{v_id}/",              [200]),
            ("doctor", f"/visits/{v_id}/edit/",         [200]),
            ("doctor", f"/visits/{v_id}/print/",        [200]),
        ]

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
    print()
    sys.exit(0 if failed == 0 else 1)

if __name__ == "__main__":
    main()
