#!/usr/bin/env python3
"""
Google AI Mode SSO — open or resume the dedicated Chrome profile.

Checks whether the existing profile has a valid signed-in Google session
before asking the user to sign in again.  Use --force to skip the check.

Standalone usage:
    python3 tool_connections/google-ai-mode/sso.py
    python3 tool_connections/google-ai-mode/sso.py --force
"""

import argparse
import sys
import time
from pathlib import Path

from google_ai_mode import (
    CDP_PORT, PROFILE_DIR,
    cdp_ready, ensure_chrome, launch_chrome,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
from tool_connections.shared_utils.browser import sync_playwright


def check(port: int = CDP_PORT) -> bool:
    """Return True if the profile has a valid signed-in Google session."""
    if not cdp_ready(port):
        return False
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            ctx = browser.contexts[0]
            page = ctx.new_page()
            page.goto("https://www.google.com/", wait_until="domcontentloaded", timeout=15_000)
            time.sleep(1)
            url = page.url.lower()
            signed_in = (
                page.locator('a[aria-label*="Google Account"]').count() > 0
                and page.locator('a[aria-label="Sign in"]').count() == 0
                and "accounts.google.com/signin" not in url
                and "sorry/index" not in url
            )
            page.close()
            browser.close()
            return signed_in
    except Exception:
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Open or resume the Google AI Mode Chrome profile.")
    parser.add_argument("--force", action="store_true",
                        help="Focus the profile for sign-in even if session is valid")
    args = parser.parse_args()

    try:
        if args.force:
            ensure_chrome()
            print(f"Google AI Mode Chrome ready — profile: {PROFILE_DIR}")
            print("Sign in to Google in the existing window if needed.")
            sys.exit(0)

        if PROFILE_DIR.exists():
            ensure_chrome()
            if check():
                print(f"Session valid — profile: {PROFILE_DIR}")
                print("No sign-in needed. Use --force to re-authenticate.")
                sys.exit(0)
            if cdp_ready():
                print(f"Chrome already open — profile: {PROFILE_DIR}")
                print("Sign in in the existing window, or run with --force.")
                sys.exit(1)

        launch_chrome()
        print(f"Opened Google AI Mode profile: {PROFILE_DIR}")
        print("Sign in to Google in the Chrome window.")
        print("The session persists in this dedicated profile.")
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
