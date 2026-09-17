# 10xProductivity — Claude Code Instructions

## SECURITY: Direct API calls are blocked

**Do NOT read `.env`, `personal/*/` credential files, or any file in this repo that contains tokens, cookies, or API keys. Do NOT run scripts that load credentials and make authenticated requests (e.g. `draw_data_mesh.py`, `read_miro.py`, `sso.py`, Playwright sessions).**

Reason: reading credential values into context embeds them in chat/Cursor logs. These connections must be accessed via MCP servers only.

Connections with token-safe CLI wrappers (allowed — credential loaded inside script, never echoed):
- **Miro** — `tool_connections/miro/cli.py` (reads REST; writes/deletes headless Playwright SDK)
- **Slack** — `personal/slack/cli.py` (copied from `tool_connections/slack/cli.py`)
- **Sana** — `personal/sana/cli.py` (copied from `tool_connections/sana/cli.py`)
- **Google Drive** — `personal/google-drive/cli.py` (copied from `tool_connections/google-drive/cli.py`; uses `~/.browser_automation/gdrive_auth.json`, not `.env`)
- **Snowflake** — `personal/snowflake/cli.py` only when MCP lacks the API or for manual one-offs; **do not** chain many CLI queries in one agent session (lockout risk). Prefer Snowflake MCP for agent SQL — see `tool_connections/mcp-eda-data-stack.md`

Connections available via MCP (prefer over Python scripts for browser tasks):
- **Playwright browser automation** — use the `playwright` MCP for web navigation, clicking, form-filling, screenshots. No credentials needed. Note: the SSO refresh scripts (`playwright_sso.py` and per-tool `sso.py`) still run via the CLI wrappers — they capture session tokens and write them to `.env` / `~/.browser_automation/`. Use the MCP for general browser automation tasks only.

MCP connections — **Conduit is the default for SaaS integrations** (`tool_connections/conduit/setup.md`). Use supplement MCPs only when Conduit lacks the action or fails.

- **Conduit** — hosted MCP for Gmail, Calendar, Drive, Docs, Sheets, Slack, JSM; OAuth per connector; tools prefixed `pd__`; setup in `tool_connections/conduit/setup.md`. List first in `~/.cursor/mcp.json`.

Other MCPs (see `tool_connections/mcp-eda-data-stack.md` for Snowflake/dbt reconciliation):
- **Atlan** — remote SSO MCP for catalog, lineage, metadata; setup in `tool_connections/atlan/setup.md`
- **Sigma MCP** — remote OAuth MCP for BI queries; setup in `tool_connections/sigma/setup.md`
- **Snowflake MCP** — prefer for agent SQL (ED&A stdio MCP + `~/.env.mcp.snowflake`); CLI as supplement — see `tool_connections/mcp-eda-data-stack.md`. Snowflake-managed OAuth MCP still blocked on ED&A platform — `tool_connections/snowflake/mcp.md`
- **dbt Cloud MCP** — deferred until access is provisioned — see `tool_connections/mcp-eda-data-stack.md`
- **Jira (BT Jira Cloud)** — supplement MCP: self-hosted `mcp-atlassian` via `uvx` (`jira-bt`) for BT Jira **dev** work (issues, sprints, boards). **JSM / service desk → Conduit first** (`pd__jira_service_desk-*`). Setup: `tool_connections/jira-bt/setup.md`. Confluence on the same site still goes through `confluence-mcp-bt`.

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
