# Horizon — Quick Start

Horizon is Workday's internal intranet, powered by LumApps. Auth is Okta SSO
— no API token page exists. The Bearer token is captured automatically from
the browser session after login.

## Prerequisites

- Python venv with Playwright installed (`pip install playwright && playwright install chromium`)
- Access to `horizon.workdayinternal.com` (Workday network or VPN)

## Steps

1. **Copy recipe to personal:**
   ```bash
   cp -r tool_connections/horizon/ personal/horizon/
   ```

2. **Capture token via SSO:**
   ```bash
   source .venv/bin/activate
   python3 personal/horizon/sso.py
   ```
   A browser window opens. On managed Workday machines Okta SSO completes
   automatically (~20s). On personal machines, complete the login prompt once.
   The token is written to `.env` automatically.

3. **Verify:**
   ```bash
   python3 personal/horizon/cli.py check
   # → {"status": "ok", "org_id": "...", "unread_notifications": "..."}
   ```

## Using the CLI

```bash
python3 personal/horizon/cli.py search --query "RBAC"
python3 personal/horizon/cli.py search --query "data platform" --limit 20
python3 personal/horizon/cli.py get-content --id 5759492855152208
python3 personal/horizon/cli.py list-navigation
python3 personal/horizon/cli.py list-saved
```

All output is JSON on stdout. Credentials are loaded from `.env` inside the
script — they never appear as arguments or in stdout.

## Token refresh

LumApps tokens expire after ~1 hour. Re-run `sso.py` when you get a 401:

```bash
python3 personal/horizon/sso.py
```

On managed machines this is fully automated (no browser interaction needed).

## `.env` entries written by sso.py

```bash
# --- Horizon ---
HORIZON_TOKEN=<bearer token — expires ~1h>
HORIZON_ORG_ID=<lumapps org id>
HORIZON_SITE_ID=<lumapps site id>
HORIZON_USER_ID=<your lumapps user id>
HORIZON_API_BASE=https://go-cell-002.api.lumapps.com
```
