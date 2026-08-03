"""
ServiceNow SSO capture — plugin for playwright_sso.py discovery.

Navigates to Workday's ServiceNow ESC, completes Okta SSO, and saves
the full browser storage_state for REST API access.

Standalone usage:
    python3 tool_connections/servicenow/sso.py
    python3 tool_connections/servicenow/sso.py --force
"""

import json
import ssl
import sys
import time
import urllib.request
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    import os
    os.system(f"{sys.executable} -m pip install playwright -q")
    os.system(f"{sys.executable} -m playwright install chromium -q")
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

sys.path.insert(0, str(Path(__file__).parents[2] / "tool_connections"))
from shared_utils.browser import BROWSER_AUTOMATION_DIR

TOOL_NAME = "servicenow"
ENV_KEYS: list[str] = []  # No .env vars — auth lives in AUTH_FILE only
AUTH_FILE = BROWSER_AUTOMATION_DIR / "servicenow_auth.json"
INSTANCE = "https://workday.service-now.com"
ESC_URL = f"{INSTANCE}/esc"


def _load_cookies() -> dict:
    if not AUTH_FILE.exists():
        return {}
    try:
        state = json.loads(AUTH_FILE.read_text())
        return {c["name"]: c["value"] for c in state.get("cookies", [])
                if "service-now.com" in c.get("domain", "")}
    except Exception:
        return {}


def check(env: dict) -> bool:
    """Return True if the ServiceNow session is still valid."""
    cookies = _load_cookies()
    if not cookies:
        return False
    cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
    # A redirect to okta means the session is expired
    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, hdrs, newurl):
            return None

    try:
        opener = urllib.request.build_opener(_NoRedirect())
        req = urllib.request.Request(
            f"{INSTANCE}/api/now/table/sys_user?sysparm_limit=1&sysparm_fields=name",
            headers={"Cookie": cookie_str, "Accept": "application/json"},
        )
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with opener.open(req, timeout=8) as r:
            return r.status == 200
    except urllib.request.HTTPError as e:
        return e.code not in (301, 302, 401, 403)
    except Exception:
        return False


def capture(env: dict) -> dict:
    """
    Open ServiceNow ESC in a headed browser, complete Okta SSO,
    and save storage_state to AUTH_FILE.
    """
    print(f"  Opening ServiceNow ESC — Okta SSO required (~60s)...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--window-size=1200,800", "--window-position=100,100"],
        )
        ctx = browser.new_context(ignore_https_errors=True)
        page = ctx.new_page()

        page.goto(ESC_URL, wait_until="commit", timeout=30_000)

        # Step 1: wait for Okta redirect (URL leaves service-now.com)
        print("  Waiting for Okta redirect...", flush=True)
        try:
            page.wait_for_url("**/okta.com/**", timeout=30_000)
            print("  Okta login page open — complete your login now...", flush=True)
        except PlaywrightTimeout:
            # If no Okta redirect, might already be authenticated — check for glide_user cookie
            pass

        # Step 2: wait for Okta login to complete and redirect back to ServiceNow
        print("  Waiting for ServiceNow session (3 min timeout — complete Okta login)...", flush=True)
        try:
            page.wait_for_url(f"{INSTANCE}/**", timeout=180_000)
        except PlaywrightTimeout:
            ctx.close()
            browser.close()
            raise RuntimeError("Timed out waiting for ServiceNow login. Did you complete the Okta flow?")
        except KeyboardInterrupt:
            ctx.close()
            browser.close()
            raise RuntimeError("Aborted by user.")

        # Step 3: wait for the authenticated session cookie to appear
        print("  Waiting for session to be fully established...", flush=True)
        deadline = time.time() + 30
        while time.time() < deadline:
            cookies = {c["name"]: c["value"] for c in ctx.cookies() if "service-now.com" in c.get("domain", "")}
            if "glide_session_store" in cookies or "glide_user" in cookies:
                break
            time.sleep(1)
        else:
            print("  Warning: timed out waiting for glide_session_store — saving whatever we have.", file=sys.stderr)

        try:
            page.wait_for_load_state("networkidle", timeout=15_000)
        except PlaywrightTimeout:
            pass
        time.sleep(2)

        AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
        ctx.storage_state(path=str(AUTH_FILE))
        print(f"    storage_state saved → {AUTH_FILE}")

        ctx.close()
        browser.close()

    cookie_count = len(_load_cookies())
    print(f"    {cookie_count} ServiceNow cookies captured")
    return {}  # No .env vars written — all auth in AUTH_FILE


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if not args.force and check({}):
        print("servicenow: ok — nothing to do. Use --force to refresh.")
        sys.exit(0)

    capture({})
    print("  Session saved. Test with: python3 personal/servicenow/cli.py requests")
