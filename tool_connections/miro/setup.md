---
name: miro-setup
description: Set up Miro connection. Auth is Okta SAML session token cookie. Reads via REST; writes via headless Playwright SDK.
---

# Miro — Setup

## Auth method: Okta SAML session token (internal API)

Miro's official REST API (`api.miro.com/v2`) requires OAuth app registration. This connection uses the internal API (`miro.com/api/v1/`) with the `token` cookie the web app uses — zero setup beyond SSO.

**What to ask the user:** Nothing for reads. For token refresh, run the SSO script (opens a headed browser).

---

## One-time setup

```bash
cd /path/to/10xProductivity
source .venv/bin/activate
python3 -m playwright install chromium   # required for create-items / delete-region
python3 tool_connections/miro/sso.py     # captures MIRO_TOKEN → .env
```

---

## Verify

```bash
python3 tool_connections/miro/read_miro.py --check
# → OK — session valid

python3 tool_connections/miro/cli.py list-boards
```

If 401: `python3 tool_connections/miro/sso.py --force`

---

## CLI commands (token-safe — credential never echoed)

All commands load `MIRO_TOKEN` from repo-root `.env` internally.

| Command | API | Browser |
|---------|-----|---------|
| `read_miro.py --check` | REST | No |
| `cli.py list-boards` | REST | No |
| `cli.py get-frames --board ID` | REST | No |
| `cli.py audit-board --board ID` | REST | No |
| `cli.py create-items --board ID --file items.json` | SDK | Headless (default) |
| `cli.py delete-region --board ID --x-min N` | SDK | Headless (default) |
| `sso.py --force` | — | Headed (Okta login) |

Add `--headed` to `create-items` or `delete-region` when debugging.

Full item JSON schema and gotchas: `api-patterns.md`  
Workshop workflow: `workshop-playbook.md`  
Example items file: `examples/minimal_items.json`

---

## `.env` entries

```bash
# --- Miro ---
# Refresh: python3 tool_connections/miro/sso.py --force
MIRO_TOKEN=your-token-here
```

---

## File map

```
tool_connections/miro/
  cli.py              # Main CLI — read + write + audit + delete
  read_miro.py        # Lightweight REST read helper
  sso.py              # Token capture (headed browser only)
  audit_board.py      # Bounds calculator (also: cli.py audit-board)
  api-patterns.md     # Verified API/SDK patterns — read before coding
  workshop-playbook.md
  examples/minimal_items.json
```
