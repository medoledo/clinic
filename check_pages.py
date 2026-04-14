#!/usr/bin/env python
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
        return "/login/" not in resp.url and resp.status_code == 200
    except Exception:
        return False

def check(session, path, expected, method="GET"):
    url = BASE_URL + path
    try:
        if method == "POST":
            token = csrf(session, url)
            r = session.post(url, data={"csrfmiddlewaretoken": token}, allow_redirects=True, timeout=TIMEOUT)
        else:
            r = session.get(url, allow_redirects=True, timeout=TIMEOUT)
            
        body = r.text
        is_home_redirect = path == "/" and "/login/" in r.url and 302 in expected
        
        if "/login/" in r.url and "/login/" not in path and not is_home_redirect:
            return {"url": url, "status": r.status_code, "expected": expected,
                    "ok": False, "bad_body": False, "snippet": "REDIRECTED TO LOGIN"}
        
        bad_body = bool(ERROR_RE.search(body))
        actual_statuses = [r.status_code] + [h.status_code for h in r.history]
        ok = any(s in expected for s in actual_statuses) and not bad_body
        
        snippet = None
        if bad_body:
            for line in body.splitlines():
                if any(w in line for w in ("Error", "Exception", "Traceback", "invalid")):
                    snippet = line.strip()[:130]
                    break
                    
        return {"url": url, "status": r.status_code, "expected": expected,
                "ok": ok, "bad_body": bad_body, "snippet": snippet}
    except Exception as e:
        return {"url": url, "status": None, "expected": expected, "ok": False,
                "bad_body": False, "snippet": str(e)}

def get_discovered_ids(adm_s, doc_s):
    d_id = None; p_id = None; v_id = None; f_id = None
    
    if adm_s:
        resp = adm_s.get(f"{BASE_URL}/admin-panel/manage-doctors/", timeout=TIMEOUT)
        matches = re.findall(r'/admin-panel/doctors/(\d+)/', resp.text)
        for m in matches:
            if m != "0": 
                d_id = m
                break

    if doc_s:
        resp = doc_s.get(f"{BASE_URL}/patients/", timeout=TIMEOUT)
        match = re.search(r'/patients/(\d+)/', resp.text)
        if match:
            p_id = match.group(1)
            resp2 = doc_s.get(f"{BASE_URL}/patients/{p_id}/", timeout=TIMEOUT)
            match2 = re.search(r'/visits/(\d+)/', resp2.text)
            if match2: v_id = match2.group(1)
            resp3 = doc_s.get(f"{BASE_URL}/patients/{p_id}/files/", timeout=TIMEOUT)
            match3 = re.search(r'/visits/files/(\d+)/delete/', resp3.text)
            if match3: f_id = match3.group(1)

    return d_id, p_id, v_id, f_id

def main():
    print(f"\n{BOLD}{CYAN}══════════════════════════════════════════")
    print(f"  MediTrack Full Template Health Check")
    print(f"  Target: {BASE_URL}")
    print(f"══════════════════════════════════════════{RESET}\n")

    pub_s = requests.Session()
    adm_s = requests.Session(); adm_ok = login(adm_s, ADMIN_USERNAME, ADMIN_PASSWORD)
    doc_s = requests.Session(); doc_ok = login(doc_s, DOCTOR_USERNAME, DOCTOR_PASSWORD)

    print(f"{GREEN}✓ Admin login OK{RESET}" if adm_ok else f"{RED}✗ Admin login FAILED{RESET}")
    print(f"{GREEN}✓ Doctor login OK{RESET}" if doc_ok else f"{RED}✗ Doctor login FAILED{RESET}")

    d_id, p_id, v_id, f_id = get_discovered_ids(adm_s if adm_ok else None, doc_s if doc_ok else None)
    if d_id: print(f"{CYAN}ℹ Found Doctor ID: {d_id}{RESET}")
    if p_id: print(f"{CYAN}ℹ Found Patient ID: {p_id}{RESET}")
    if v_id: print(f"{CYAN}ℹ Found Visit ID: {v_id}{RESET}")
    if f_id: print(f"{CYAN}ℹ Found File ID: {f_id}{RESET}")
    print()

    PAGES = [
        ("public", "/", [200, 302], "GET"),
        ("public", "/login/", [200], "GET"),
        ("public", "/register/", [200], "GET"),
        ("admin",  "/admin-panel/", [200], "GET"),
        ("admin",  "/admin-panel/manage-doctors/", [200], "GET"),
        ("admin",  "/admin-panel/doctors/add/", [200], "GET"),
        ("doctor", "/dashboard/", [200], "GET"),
        ("doctor", "/patients/", [200], "GET"),
        ("doctor", "/patients/add/", [200], "GET"),
        ("doctor", "/pending-visits/", [200], "GET"),
        ("doctor", "/upcoming-visits/", [200], "GET"),
        ("doctor", "/search-patients/?q=test", [200], "GET"),
    ]
    
    if d_id:
        PAGES += [
            ("admin", f"/admin-panel/doctors/{d_id}/edit/", [200], "GET"),
            ("admin", f"/admin-panel/doctors/{d_id}/reset-password/", [200], "GET"),
            ("admin", f"/admin-panel/doctors/{d_id}/delete/", [200], "GET"),
        ]
    if p_id:
        PAGES += [
            ("doctor", f"/patients/{p_id}/", [200], "GET"),
            ("doctor", f"/patients/{p_id}/edit/", [200], "GET"),
            ("doctor", f"/patients/{p_id}/files/", [200], "GET"),
            ("doctor", f"/patients/{p_id}/add-visit/", [200], "GET"),
            ("doctor", f"/patients/{p_id}/delete/", [405], "GET"),
        ]
    if v_id:
        PAGES += [
            ("doctor", f"/visits/{v_id}/", [200], "GET"),
            ("doctor", f"/visits/{v_id}/edit/", [200], "GET"),
            ("doctor", f"/visits/{v_id}/print/", [200], "GET"),
            # delete_visit returns 200 via JsonResponse even on GET failure
            ("doctor", f"/visits/{v_id}/delete/", [200], "GET"),
        ]
    if f_id:
        PAGES += [
            # delete_visit_file has a confirm template (200 OK)
            ("doctor", f"/visits/files/{f_id}/delete/", [200], "GET"),
        ]

    sessions = {"public": pub_s, "admin": adm_s, "doctor": doc_s}
    available = {"public": True, "admin": adm_ok, "doctor": doc_ok}
    results = []

    for role, path, expected, method in PAGES:
        if not available[role]: continue
        r = check(sessions[role], path, expected, method)
        r["role"] = role; r["path"] = path
        results.append(r)
        
        s = str(r["status"]) if r["status"] else "---"
        mark = f"{GREEN}  ✓ PASS{RESET}" if r["ok"] else f"{RED}  ✗ FAIL{RESET}"
        if not r["ok"] and r["bad_body"]: mark += f" {RED}(Django Error){RESET}"
        
        print(f"{mark}  [{role:6}]  HTTP {s:<5} {path}")
        if r["snippet"]: print(f"           {YELLOW}→ {r['snippet']}{RESET}")

    total = len(results); passed = sum(1 for r in results if r["ok"])
    print(f"\n{BOLD}══ Results: {passed}/{total} passed {'— All OK ✓' if passed==total else '— FAILED ✗'} ══{RESET}\n")
    sys.exit(0 if passed == total else 1)

if __name__ == "__main__":
    main()
