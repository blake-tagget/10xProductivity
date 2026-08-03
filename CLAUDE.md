# 10xProductivity — Claude Code Instructions

## SECURITY: Direct API calls are blocked

**Do NOT read `.env`, `personal/*/` credential files, or any file in this repo that contains tokens, cookies, or API keys. Do NOT run scripts that load credentials and make authenticated requests (e.g. `draw_data_mesh.py`, `read_miro.py`, `sso.py`, Playwright sessions).**

Reason: reading credential values into context embeds them in chat/Cursor logs. These connections must be accessed via MCP servers only.

Connections with token-safe CLI wrappers (allowed — credential loaded inside script, never echoed):
- **Miro** — `tool_connections/miro/cli.py` (reads REST; writes/deletes headless Playwright SDK)
- **Slack** — `personal/slack/cli.py` (copied from `tool_connections/slack/cli.py`)
- **Sana** — `personal/sana/cli.py` (copied from `tool_connections/sana/cli.py`)
- **Google Drive** — `personal/google-drive/cli.py` (copied from `tool_connections/google-drive/cli.py`; uses `~/.browser_automation/gdrive_auth.json`, not `.env`)
- **Snowflake** — `personal/snowflake/cli.py` (copied from `tool_connections/snowflake/cli.py`; uses `~/.snowflake/config.toml`, not `.env`)

Connections available via MCP (prefer over Python scripts for browser tasks):
- **Playwright browser automation** — use the `playwright` MCP for web navigation, clicking, form-filling, screenshots. No credentials needed. Note: the SSO refresh scripts (`playwright_sso.py` and per-tool `sso.py`) still run via the CLI wrappers — they capture session tokens and write them to `.env` / `~/.browser_automation/`. Use the MCP for general browser automation tasks only.

MCP setup in progress (see `tool_connections/mcp-snowflake-sigma.md`):
- **Sigma MCP** — remote OAuth MCP for BI queries; setup in `tool_connections/sigma/setup.md`
- **Snowflake MCP** — blocked on ED&A platform; interim = `personal/snowflake/cli.py`; see `tool_connections/snowflake/mcp.md`

Connections still blocked (no CLI or MCP yet): **Outlook, GitHub.com**.

If the user asks to use a blocked tool, respond: "No MCP server or CLI wrapper exists for [tool] yet — I can't make that call without reading your credentials."

---

## Reference only (safe to read, no credentials)

`verified_connections.md` — documents what connections exist and their current status.

## Repo path shortcuts

`REPO_10X`, `REPO_EDDG`, `REPO_COLLAB` are defined in `tool_connections/repo_paths.sh`. Source it (without sourcing `.env`) to get the path variables:

```bash
source ~/code/10xProductivity/tool_connections/repo_paths.sh
```
