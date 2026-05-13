"""
Horizon (LumApps) SSO capture — plugin for playwright_sso.py discovery.

Navigates to Horizon, completes Okta SSO, and extracts the Bearer token
by intercepting the first authenticated API call to go-cell-002.api.lumapps.com.
Also captures org ID, site ID, and user ID from the front-init response.

Standalone usage:
    cd ~/code/10xProductivity && source .venv/bin/activate
    python3 personal/horizon/sso.py
    python3 personal/horizon/sso.py --force
"""

import json
import sys
import time
import ssl
import urllib.parse
import urllib.request
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    import os
    os.system(f"{sys.executable} -m pip install playwright -q")
    os.system(f"{sys.executable} -m playwright install chromium -q")
    from playwright.sync_api import sync_playwright

TOOL_NAME = "horizon"
ENV_KEYS = ["HORIZON_TOKEN", "HORIZON_ORG_ID", "HORIZON_SITE_ID",
            "HORIZON_USER_ID", "HORIZON_API_BASE"]

START_URL = "https://horizon.workdayinternal.com"
API_HOST = "go-cell-002.api.lumapps.com"


def check(env: dict) -> bool:
    token = env.get("HORIZON_TOKEN", "")
    org_id = env.get("HORIZON_ORG_ID", "")
    api_base = env.get("HORIZON_API_BASE", f"https://{API_HOST}")
    if not token or not org_id:
        return False
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(
            f"{api_base}/_ah/api/lumsites/v1/notification/countUnread",
            headers={
                "Authorization": f"Bearer {token}",
                "lumapps-organization-id": org_id,
            },
        )
        with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
            data = json.loads(r.read())
            return "unreadNotificationsCount" in data
    except Exception:
        return False


def capture(env: dict) -> dict:
    captured = {}

    print("  Opening Horizon — complete any Okta prompts in the browser window.")
    print("  Browser will stay open until token is captured (up to 3 min).")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=50)
        context = browser.new_context()
        page = context.new_page()

        # Use page.route() — runs synchronously inside Playwright's event loop,
        # so captured dict is always visible on the main thread after each wait.
        def handle_route(route):
            request = route.request
            if API_HOST in request.url and "HORIZON_TOKEN" not in captured:
                auth = request.headers.get("authorization", "")
                if auth.startswith("Bearer "):
                    captured["HORIZON_TOKEN"] = auth[7:]
                    captured["HORIZON_ORG_ID"] = request.headers.get(
                        "lumapps-organization-id", ""
                    )
                    captured["HORIZON_CLIENT_VERSION"] = request.headers.get(
                        "lumapps-web-client-version", ""
                    )
                    print(f"  Token captured from: {request.url.split('?')[0]}")
            route.continue_()

        def handle_response(response):
            if "front-init" not in response.url:
                return
            try:
                body = json.loads(response.body())
                instance = body.get("instanceInfo", {})
                if instance.get("id") and "HORIZON_SITE_ID" not in captured:
                    captured["HORIZON_SITE_ID"] = str(instance["id"])
                user = body.get("user", {})
                if user.get("id") and "HORIZON_USER_ID" not in captured:
                    captured["HORIZON_USER_ID"] = str(user["id"])
            except Exception:
                pass

        context.route("**/*", handle_route)
        page.on("response", handle_response)

        # Navigate — don't wait for full load so Okta page appears immediately
        page.goto(START_URL, timeout=30_000, wait_until="domcontentloaded")

        # Wait for SSO to complete: poll until back on horizon domain
        # Each wait_for_timeout(2000) gives Playwright 2s to process network events
        print("  Waiting for SSO and Horizon page load...", flush=True)
        for _ in range(90):  # up to 3 minutes
            page.wait_for_timeout(2_000)
            if "HORIZON_TOKEN" in captured:
                break
            current = page.url
            if "horizon.workdayinternal.com/home" in current:
                # We're on Horizon but token not yet captured — trigger an API call
                try:
                    page.goto(
                        f"https://horizon.workdayinternal.com/home/ls/content/5759492855152208/ia-rbac",
                        timeout=15_000,
                        wait_until="domcontentloaded",
                    )
                except Exception:
                    pass

        if "HORIZON_TOKEN" not in captured:
            browser.close()
            raise RuntimeError(
                "Could not capture Horizon token after 3 minutes. "
                "Check that SSO completed and the Horizon page loaded."
            )

        # Fallback constants from sniff if not extracted from front-init
        if "HORIZON_SITE_ID" not in captured:
            captured["HORIZON_SITE_ID"] = "5649930513285120"
        if "HORIZON_ORG_ID" not in captured:
            captured["HORIZON_ORG_ID"] = "5368347508080640"

        captured["HORIZON_API_BASE"] = f"https://{API_HOST}"

        time.sleep(2)
        browser.close()

    return {k: v for k, v in captured.items() if k in ENV_KEYS}


if __name__ == "__main__":
    import argparse
    import re

    ENV_FILE = Path(__file__).parents[2] / ".env"

    def load_env():
        if not ENV_FILE.exists():
            return {}
        return {k.strip(): v.strip() for line in ENV_FILE.read_text().splitlines()
                if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}

    def write_env(tokens):
        content = ENV_FILE.read_text() if ENV_FILE.exists() else ""
        for key, value in tokens.items():
            new_line = f"{key}={value}"
            if re.search(rf"^{re.escape(key)}=", content, flags=re.MULTILINE):
                content = re.sub(rf"^{re.escape(key)}=.*$", new_line, content, flags=re.MULTILINE)
            else:
                content += f"\n{new_line}\n"
        ENV_FILE.write_text(content)

    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Re-capture even if token is valid")
    args = parser.parse_args()

    env = load_env()
    if not args.force and check(env):
        print("  HORIZON_TOKEN: ok (still valid, use --force to re-capture)")
        sys.exit(0)

    print("  Capturing Horizon token via SSO...")
    tokens = capture(env)
    write_env(tokens)
    print(f"  Captured and wrote: {list(tokens.keys())}")
    print("  Verifying...")
    env.update(tokens)
    if check(env):
        print("  HORIZON_TOKEN: ok")
    else:
        print("  HORIZON_TOKEN: FAILED — verify manually")
        sys.exit(1)
