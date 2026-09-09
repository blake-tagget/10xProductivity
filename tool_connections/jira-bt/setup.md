---
tool: jira-bt
type: mcp
status: active
updated: 2026-09-09
description: sooperset/mcp-atlassian, self-hosted via uvx — Jira Cloud issues via API token.
---

# Jira MCP — BT Jira Cloud (`mcp-atlassian`)

Self-hosted MCP server ([sooperset/mcp-atlassian](https://github.com/sooperset/mcp-atlassian)), launched locally via `uvx`. Uses a plain Atlassian API token — no OAuth browser flow, works in non-interactive sessions.

Superseded the official Atlassian remote MCP (OAuth 2.1) — that one required an interactive browser sign-in that a non-interactive agent session can't complete, so it never became usable. This server authenticates the same way `confluence-mcp-bt` already does (API token in the MCP config), which works immediately.

Added to reach Jira Cloud issues on the Workday BT site (e.g. `GTMENT-*` tickets), which neither `jira-ghe` (internal Server/DC Jira) nor `confluence-mcp-bt` (Confluence pages only, no Jira issue tools) could reach.

## Status

| Item | State |
|------|-------|
| Launcher | `uvx mcp-atlassian` (local stdio process; `uvx` on PATH or `$HOME/.local/bin/uvx`) |
| Site | Workday BT Jira Cloud — infer base URL from any ticket URL (see `tool_connections/jira/setup.md`) |
| Auth | Atlassian API token (same token already used by `confluence-mcp-bt`, since Cloud API tokens are account-wide, not per-product) |
| Confluence env vars | Deliberately omitted — `confluence-mcp-bt` already covers Confluence on this site; this server is scoped to Jira only |

## Cursor / Claude Code setup

Added to `~/.cursor/mcp.json`:

```json
"jira-bt": {
  "command": "uvx",
  "args": ["--system-certs", "mcp-atlassian"],
  "env": {
    "UV_SYSTEM_CERTS": "1",
    "JIRA_URL": "<Jira Cloud base URL — infer from ticket URL; see jira/setup.md>",
    "JIRA_USERNAME": "you@yourcompany.com",
    "JIRA_API_TOKEN": "<same token as confluence-mcp-bt / ATLASSIAN_BT_TOKEN in .env>"
  }
}
```

**Workday TLS:** `uvx` must use the macOS trust store to reach PyPI through the corporate proxy. Without `--system-certs` / `UV_SYSTEM_CERTS=1`, startup fails with `invalid peer certificate: UnknownIssuer` and Cursor reports the server as failed during tool discovery.

Then run `sync-mcp` to propagate into `~/.claude/settings.json`.

**Requires a session restart** — MCP servers connect at session start; a config change mid-session won't make the tools available until the next Claude Code / Cursor session.

## Validate

Ask the agent to fetch a known BT ticket by key — a successful `jira_get_issue` call confirms the connection.

## Relationship to other Atlassian connections

| Connection | Site | Scope | Auth |
|---|---|---|---|
| `jira-ghe` | Internal Server/DC Jira + GHE | SWE/EDDG tickets | token headers (Claude global config) |
| `confluence-mcp-bt` | Workday BT Confluence Cloud | Confluence pages/spaces only | API token (Claude global config) |
| `jira-bt` (this one) | Workday BT Jira Cloud | Jira issues only | API token, via `uvx mcp-atlassian` |
| `ATLASSIAN_BT_*` in `.env` | Workday BT Jira Cloud | Direct REST (curl/scripts) | Same API token — fallback when MCP is down |

If a new API token is ever needed: Atlassian account → Security → API tokens. Update `confluence-mcp-bt`, `jira-bt`, and `ATLASSIAN_BT_TOKEN` together.

## References

- Repo: [github.com/sooperset/mcp-atlassian](https://github.com/sooperset/mcp-atlassian)
- Docs: mcp-atlassian docs site (linked from repo README)
- Jira Cloud token setup (shared auth pattern): `tool_connections/jira/setup.md`
- Confluence BT setup (adjacent, not this server): `tool_connections/confluence/setup.md`
