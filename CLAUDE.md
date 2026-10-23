# 10xProductivity — Claude Code Instructions

## SECURITY: Direct API calls are blocked

**Do NOT read `.env`, `personal/*/` credential files, or any file in this repo that contains tokens, cookies, or API keys. Do NOT run scripts that load credentials and make authenticated requests (e.g. `draw_data_mesh.py`, `read_miro.py`, `sso.py`, Playwright sessions) unless the user explicitly asks for that path in this message.**

Reason: reading credential values into context embeds them in chat/Cursor logs. SaaS integrations must go through MCP (Conduit) in agent sessions.

## Conduit first — do not use 10x CLIs for these

**Google Drive, Docs, Sheets, Gmail, Calendar, Slack, Zoom, BT Jira, JSM, and Workday jira2 + GHE go through Conduit MCP** (`pd__*` / `jira_ghe__*` / `mcp__conduit__*`). Do **not** use the 10x `personal/*/cli.py` wrappers for them in agent sessions.

Setup: `tool_connections/conduit/setup.md`. Cursor rule: `~/code/.cursor/rules/conduit-mcp-default.mdc`.

### Conduit gotchas

- Standalone `jira-ghe` may return `Session not found` while Conduit `jira_ghe__*` works — prefer Conduit.
- Google Docs multi-tab: document get often returns one JSON blob; plain text may be first tab only — read the `tabs` array.

## Still allowed CLI wrappers (no Conduit app yet)

Token-safe only — credential loaded inside script, never echoed; only when the user needs that tool:

- **Miro** — `tool_connections/miro/cli.py` / `personal/miro/cli.py`
- **Sana** — `personal/sana/cli.py`
- **Snowflake** — `personal/snowflake/cli.py` only when MCP lacks the API or for manual one-offs; prefer Snowflake MCP for agent SQL — see `tool_connections/mcp-eda-data-stack.md`

**Deprecated for agents (SSO / scripts only):** Slack, Google Drive, Zoom, Gmail CLIs under `personal/` — Conduit replaced them.

Connections available via MCP (prefer over Python scripts for browser tasks):
- **Playwright browser automation** — use the `playwright` MCP for web navigation, clicking, form-filling, screenshots. No credentials needed. Note: SSO refresh scripts still run via CLI when the user asks to refresh a legacy session.

Other MCPs (see `tool_connections/mcp-eda-data-stack.md` for Snowflake/dbt reconciliation):
- **Atlan** — remote SSO MCP for catalog, lineage, metadata; setup in `tool_connections/atlan/setup.md`
- **Sigma MCP** — remote OAuth MCP for BI queries; setup in `tool_connections/sigma/setup.md`
- **Snowflake MCP** — prefer for agent SQL — see `tool_connections/mcp-eda-data-stack.md`
- **dbt Cloud MCP** — deferred until access is provisioned
- **Jira BT (`jira-bt`)** — supplement only when Conduit `app:jira` / JSM lacks the action. Setup: `tool_connections/jira-bt/setup.md`. Confluence on the same site still goes through `confluence-mcp-bt`.

Connections still blocked (no CLI or MCP yet): **Outlook, GitHub.com** (GitHub.com has a PAT CLI if explicitly needed).

If the user asks to use a blocked tool, respond: "No MCP server or CLI wrapper exists for [tool] yet — I can't make that call without reading your credentials."

---

## Reference only (safe to read, no credentials)

`verified_connections.md` — documents what connections exist and their current status.

## Repo path shortcuts

`REPO_10X`, `REPO_EDDG`, `REPO_COLLAB` are defined in `tool_connections/repo_paths.sh`. Source it (without sourcing `.env`) to get the path variables:

```bash
source ~/code/10xProductivity/tool_connections/repo_paths.sh
```
