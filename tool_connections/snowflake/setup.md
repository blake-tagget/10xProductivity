# Snowflake — Quick Start

## Prerequisites

- Snowflake VSCode extension installed (sets up `~/.snowflake/config.toml`)
- OR: manually create `~/.snowflake/config.toml` with account/user/PAT

## Steps

1. **Verify config exists:**
   ```bash
   cat ~/.snowflake/config.toml
   # Should show account, user, password (PAT), warehouse
   ```

2. **Activate venv and install connector:**

   **Workday users** — pip routes through Artifactory automatically once `~/.config/pip/pip.conf`
   is configured. If you haven't set that up yet, see `tool_connections/artifactory/setup.md` first.
   Then:
   ```bash
   cd ~/code/10xProductivity && source .venv/bin/activate
   pip install snowflake-connector-python
   ```

   **Non-Workday / public PyPI users:**
   ```bash
   cd ~/code/10xProductivity && source .venv/bin/activate
   pip install snowflake-connector-python
   ```
   *(No extra flags needed — `pip install` uses whatever `index-url` is set in your `pip.conf`,
   defaulting to PyPI if unconfigured.)*

3. **Copy recipe to personal:**
   ```bash
   cp -r tool_connections/snowflake/ personal/snowflake/
   ```

4. **Sync credentials to .env:**
   ```bash
   python3 personal/snowflake/connection.py --sync
   ```

5. **Verify connection:**
   ```bash
   python3 personal/snowflake/connection.py
   # → SNOWFLAKE_PAT: ok
   ```

6. **Verify CLI:**
   ```bash
   python3 personal/snowflake/cli.py check
   # → {"U": "you@company.com", "WH": "your_warehouse", "ROLE": "...", "account": "..."}
   ```

## Using the CLI

After setup, run queries from `personal/snowflake/`:

```bash
python3 personal/snowflake/cli.py query --sql "SELECT CURRENT_USER()"
python3 personal/snowflake/cli.py query --sql "SELECT * FROM t" --database MY_DB --schema MY_SCHEMA --limit 100
python3 personal/snowflake/cli.py list-databases
python3 personal/snowflake/cli.py list-schemas --database MY_DB
python3 personal/snowflake/cli.py list-tables --database MY_DB --schema MY_SCHEMA
python3 personal/snowflake/cli.py describe --database MY_DB --schema MY_SCHEMA --table MY_TABLE
```

All output is JSON on stdout. Credentials are loaded from `~/.snowflake/config.toml` inside
the script — they never appear as arguments or in stdout.

**Token renewal:** Snowflake UI → Profile → Programmatic Access Tokens → Generate new token →
update `password` in `~/.snowflake/config.toml`.

## See also

`tool_connections/snowflake/connection-pat.md` — full auth examples and query patterns.  
`tool_connections/snowflake/mcp.md` — Snowflake managed MCP for Cursor (pending ED&A platform setup; tracked in ISSAS-1780).
