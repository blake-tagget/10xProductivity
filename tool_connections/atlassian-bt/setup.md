---
tool: atlassian-bt
type: mcp
status: active
updated: 2026-09-09
description: Official Atlassian remote MCP (Rovo) — Jira issues on workdaybt.atlassian.net via OAuth 2.1.
---

# Atlassian MCP — BT Jira Cloud

The official, Atlassian-hosted remote MCP server. HTTP transport, OAuth 2.1 browser flow — no API tokens or `.env` files. Covers Jira Cloud (and Confluence/JSM/Bitbucket, though this repo's Confluence flow still goes through the dedicated `confluence-mcp-bt` server — see below).

Added to reach Jira Cloud issues on `workdaybt.atlassian.net` (e.g. `GTMENT-*` tickets), which neither `jira-ghe` (points at `jira2.workday.com`, a Server/Data Center instance, not Cloud) nor `confluence-mcp-bt` (Confluence pages only, no Jira issue tools) could reach.

## Status

| Item | State |
|------|-------|
| MCP URL | `https://mcp.atlassian.com/v2/mcp` |
| Transport | HTTP (not SSE — legacy endpoint deprecated) |
| Auth | OAuth 2.1 browser flow (or API token, admin-gated) — no secrets in config |
| Site | `workdaybt.atlassian.net` (grants scoped to whatever Atlassian sites the authorizing account can reach) |

## Cursor / Claude Code setup

Added to `~/.cursor/mcp.json`:

```json
"atlassian-bt": {
  "url": "https://mcp.atlassian.com/v2/mcp",
  "type": "http"
}
```

Then run `sync-mcp` to propagate into `~/.claude/settings.json`.

## First-use authorization

1. First tool call triggers a browser-based OAuth 2.1 flow
2. Complete sign-in/consent for the Atlassian site(s) you need (BT: `workdaybt.atlassian.net`)
3. Client receives scoped access tokens — no token ever lands in `mcp.json`
4. This must happen in an **interactive** session — a non-interactive/background agent session cannot complete the browser OAuth step

## Validate

Ask the agent to fetch a known BT ticket, e.g. "look up GTMENT-20168" — a successful issue fetch confirms the connection and that OAuth completed.

## Relationship to other Atlassian connections

| Connection | Site | Scope | Auth |
|---|---|---|---|
| `jira-ghe` | `jira2.workday.com` | Jira Server/DC + GHE | token headers (Claude global config) |
| `confluence-mcp-bt` | `workdaybt.atlassian.net` | Confluence pages/spaces only | API token (Claude global config) |
| `atlassian-bt` (this one) | `workdaybt.atlassian.net` (+ any other authorized Atlassian Cloud site) | Jira issues, and Confluence/JSM/Bitbucket if needed | OAuth 2.1 |

Don't use `atlassian-bt` for BT Confluence page reads/writes if `confluence-mcp-bt` already covers it — that server is purpose-built and token-optimized for Confluence. Use `atlassian-bt` specifically for Jira Cloud issue lookups on the BT site.

## References

- Official repo: [github.com/atlassian/atlassian-mcp-server](https://github.com/atlassian/atlassian-mcp-server)
- Confluence BT setup (adjacent, not this server): `tool_connections/confluence/setup.md`
