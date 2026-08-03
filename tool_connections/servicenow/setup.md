# ServiceNow CLI — Setup Guide

## One-time setup

1. **Install Playwright** (if not already):
   ```bash
   source .venv/bin/activate
   pip install playwright
   playwright install chromium
   ```

2. **Capture your Okta session:**
   ```bash
   source .venv/bin/activate
   python3 tool_connections/servicenow/sso.py
   ```
   A browser window will open. Complete the Okta login for `workday.service-now.com`. The browser will close automatically once the session is captured.

   Auth is saved to: `~/.browser_automation/servicenow_auth.json`

3. **Verify it works:**
   ```bash
   python3 personal/servicenow/cli.py requests
   ```

## Session refresh

Sessions expire after ~8 hours or when Okta forces re-auth.

```bash
# Check + refresh if expired
source .venv/bin/activate && python3 tool_connections/servicenow/sso.py

# Force refresh even if still valid
python3 tool_connections/servicenow/sso.py --force

# Or via the CLI
python3 personal/servicenow/cli.py auth
```

## ED&A toolset analyst bundle — workflow

### Step 1: Find the catalog item sys_ids

```bash
python3 personal/servicenow/cli.py search "snowflake"
python3 personal/servicenow/cli.py search "sigma"
python3 personal/servicenow/cli.py search "atlan"
```

Grab the `sys_id` from each result.

### Step 2: Inspect required fields

```bash
python3 personal/servicenow/cli.py describe <item_sys_id>
```

Look at the `variables` array in the output — each entry has `name` (the field key), `label`, and `mandatory`.

### Step 3a: Simple bundle (no required fields)

```bash
python3 personal/servicenow/cli.py bundle <snowflake_id> <sigma_id> <atlan_id>
```

### Step 3b: Bundle with field values

```bash
python3 personal/servicenow/cli.py bundle <snowflake_id> <sigma_id> <atlan_id> \
    --var <snowflake_id>:role="analyst" \
    --var <snowflake_id>:justification="ED&A toolset access for analyst role" \
    --var <sigma_id>:justification="ED&A toolset access" \
    --var <atlan_id>:justification="ED&A toolset access"
```

### Step 3c: Multiple Snowflake roles

If you need the same catalog item submitted twice (e.g. two Snowflake roles):

```bash
python3 personal/servicenow/cli.py bundle <snowflake_id> <snowflake_id> <sigma_id> <atlan_id> \
    --var 0:role="analyst" --var 0:user="blake.tagget" \
    --var 1:role="read_only" --var 1:user="other.user" \
    --var 2:justification="Sigma access" \
    --var 3:justification="Atlan access"
```

When the same `item_id` appears more than once, use `0:`/`1:`/`2:` positional prefixes.

### Step 3d: Complex bundle from JSON config

Create `bundle.json`:
```json
[
  {
    "item_id": "<snowflake_sys_id>",
    "variables": {
      "role": "analyst",
      "justification": "ED&A toolset analyst access"
    }
  },
  {
    "item_id": "<snowflake_sys_id>",
    "variables": {
      "role": "read_only",
      "justification": "ED&A toolset analyst access"
    }
  },
  {
    "item_id": "<sigma_sys_id>",
    "variables": {
      "justification": "ED&A toolset analyst access"
    }
  },
  {
    "item_id": "<atlan_sys_id>",
    "variables": {
      "justification": "ED&A toolset analyst access"
    }
  }
]
```

```bash
python3 personal/servicenow/cli.py bundle --config bundle.json
```

## Output

All commands write JSON to stdout. The checkout result includes:
- `request_number` — the REQ-XXXXXXXX number to track
- A tracking URL is printed to stderr
