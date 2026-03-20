"""HTTP integration tests for the Tripletex AI Accounting Agent.

Starts uvicorn in a subprocess and sends real HTTP requests to verify
the /solve, /health, and / endpoints work correctly.
"""
import json
import subprocess
import sys
import time
import urllib.request
import urllib.error

APP_DIR = f"{__import__('os').path.dirname(__import__('os').path.abspath(__file__))}/app"
PORT = 18991  # unlikely to conflict
BASE = f"http://127.0.0.1:{PORT}"

# Sample credentials matching competition format
CREDS = {
    "base_url": "https://kkpqfuj-amager.tripletex.dev/v2",
    "session_token": "eyJ0b2tlbklkIjoyMTQ3NjUyNjMyLCJ0b2tlbiI6ImQ4NWU3MDZmLWI1MjQtNDk0MS04ZTQ1LWUxZWNiMjVlN2M2MyJ9",
}


def _post(path: str, body: dict) -> tuple[int, dict]:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _get(path: str) -> tuple[int, dict]:
    req = urllib.request.Request(f"{BASE}{path}")
    resp = urllib.request.urlopen(req, timeout=10)
    return resp.status, json.loads(resp.read())


def start_server() -> subprocess.Popen:
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=APP_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    # Wait for server to be ready
    for _ in range(30):
        time.sleep(0.3)
        try:
            urllib.request.urlopen(f"{BASE}/health", timeout=2)
            return proc
        except Exception:
            pass
    # Print output if startup failed
    proc.terminate()
    print(proc.stdout.read().decode()[:2000])
    raise RuntimeError("Server failed to start")


def test_root(passed: list, failed: list):
    name = "GET /"
    try:
        status, body = _get("/")
        assert status == 200, f"status={status}"
        assert body.get("status") == "running", f"body={body}"
        passed.append(name)
    except Exception as e:
        failed.append((name, str(e)))


def test_health_get(passed: list, failed: list):
    name = "GET /health"
    try:
        status, body = _get("/health")
        assert status == 200, f"status={status}"
        assert body.get("status") == "ok", f"body={body}"
        passed.append(name)
    except Exception as e:
        failed.append((name, str(e)))


def test_health_post(passed: list, failed: list):
    name = "POST /health"
    try:
        status, body = _post("/health", {})
        assert status == 200, f"status={status}"
        assert body.get("status") == "ok", f"body={body}"
        passed.append(name)
    except Exception as e:
        failed.append((name, str(e)))


def test_solve_create_customer(passed: list, failed: list):
    """POST /solve with a create-customer prompt.

    The actual Tripletex API call will likely fail (test creds),
    but we verify the endpoint accepts the request and returns
    {"status": "completed"} (the agent always returns this).
    """
    name = "POST /solve create-customer"
    try:
        status, body = _post("/solve", {
            "prompt": "Opprett en kunde med navn Test AS",
            "tripletex_credentials": CREDS,
        })
        assert status == 200, f"status={status}"
        assert body.get("status") in ("completed", "error"), f"body={body}"
        passed.append(name)
    except Exception as e:
        failed.append((name, str(e)))


def test_solve_create_employee(passed: list, failed: list):
    name = "POST /solve create-employee"
    try:
        status, body = _post("/solve", {
            "prompt": "Create an employee named John Smith with email john@smith.com",
            "tripletex_credentials": CREDS,
        })
        assert status == 200, f"status={status}"
        assert body.get("status") in ("completed", "error"), f"body={body}"
        passed.append(name)
    except Exception as e:
        failed.append((name, str(e)))


def test_solve_create_invoice(passed: list, failed: list):
    name = "POST /solve create-invoice"
    try:
        status, body = _post("/solve", {
            "prompt": "Opprett en faktura til kunde Acme AS for 10 timer konsulentarbeid à 1200 kr",
            "tripletex_credentials": CREDS,
        })
        assert status == 200, f"status={status}"
        assert body.get("status") in ("completed", "error"), f"body={body}"
        passed.append(name)
    except Exception as e:
        failed.append((name, str(e)))


def test_solve_missing_creds(passed: list, failed: list):
    """POST /solve without credentials should still return 200 with status completed."""
    name = "POST /solve missing-creds"
    try:
        status, body = _post("/solve", {
            "prompt": "Opprett en kunde med navn Test AS",
            "tripletex_credentials": {},
        })
        assert status == 200, f"status={status}"
        assert body.get("status") == "completed", f"body={body}"
        passed.append(name)
    except Exception as e:
        failed.append((name, str(e)))


def test_solve_empty_body(passed: list, failed: list):
    name = "POST /solve empty-body"
    try:
        status, body = _post("/solve", {})
        assert status == 200, f"status={status}"
        assert body.get("status") == "completed", f"body={body}"
        passed.append(name)
    except Exception as e:
        failed.append((name, str(e)))


def main():
    print("Starting server...")
    proc = start_server()
    print(f"Server running on port {PORT}")

    passed = []
    failed = []

    tests = [
        test_root,
        test_health_get,
        test_health_post,
        test_solve_missing_creds,
        test_solve_empty_body,
        test_solve_create_customer,
        test_solve_create_employee,
        test_solve_create_invoice,
    ]

    for t in tests:
        print(f"  Running {t.__name__}...", end=" ")
        t(passed, failed)
        if passed and passed[-1] == t.__name__.replace("test_", "").replace("_", " ").upper()[:50]:
            print("PASS")
        elif failed and failed[-1][0] in t.__name__:
            print(f"FAIL: {failed[-1][1][:80]}")
        else:
            print("PASS" if not failed or failed[-1][0] not in (t.__name__,) else "FAIL")

    proc.terminate()
    proc.wait()

    print(f"\n{'='*50}")
    print(f"Results: {len(passed)} passed, {len(failed)} failed")
    for name in passed:
        print(f"  PASS: {name}")
    for name, err in failed:
        print(f"  FAIL: {name}: {err[:100]}")
    print(f"{'='*50}")

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
