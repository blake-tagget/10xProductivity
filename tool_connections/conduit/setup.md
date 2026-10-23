---
tool: conduit
type: mcp
status: active
updated: 2026-10-22
description: Workday Conduit — default hosted MCP for Google Workspace, Slack, Zoom, BT Jira, JSM, jira2+GHE (upstream mcp:jira_ghe), and other SaaS.
---

# Conduit MCP — default integration layer

Conduit is a **hosted remote MCP** (Workday SSO / VPN) that exposes SaaS
connectors (Pipedream-backed) through one server. Use it as the
**default path** for Gmail, Calendar, Drive, Docs, Sheets, Slack, Zoom, BT Jira
Cloud, and Jira Service Management in Cursor and Claude Code. Reach for
dedicated MCPs or 10x CLI wrappers only when Conduit lacks the capability or
the call fails.

**Not in [awesome/mcp](https://ghe.megaleo.com/awesome/mcp)** (verified 2026-10-20) —
do not look for Conduit on the Workday MCP registry. Open the Conduit web UI
(Workday network), then **Home → Connect a client** to copy the MCP server URL.
Canonical routing (including the host) lives in RADDS/context-atlas
`docs/atlas/ROUTING.md` (Conduit-first section). Local machines keep the URL in
gitignored `verified_connections.md`.

**Why Conduit first:** one OAuth surface, per-user tool trimming, no secrets in
`mcp.json`, and far fewer tools than enabling every Pipedream action (`allTools`).

## Status

| Item | State |
|------|-------|
| UI / MCP URL | Conduit web UI → Connect a client (not listed in awesome/mcp) |
| Auth | Conduit / Pipedream OAuth (per connector); no tokens in config |
| Tool namespace | `conduit` server → tools prefixed `pd__` (e.g. `pd__slack_v2-post-message`) |
| Routing rule | `~/code/.cursor/rules/conduit-mcp-default.mdc` (always apply) |
| Team routing doc | `context-atlas/docs/atlas/ROUTING.md` → Conduit-first section |

## Cursor setup

List **Conduit first** in `~/.cursor/mcp.json` so it is the primary integration server.
Paste the MCP URL from Conduit **Connect a client** (ends with `/mcp`):

```json
"conduit": {
  "url": "<paste-from-conduit-connect-a-client>",
  "headers": {}
}
```

Then:

1. **Cursor → Settings → Tools & MCP** — reload or toggle the `conduit` server
2. On first use, run **`mcp_auth`** for Conduit (or click **Needs authentication**)
3. In the Conduit UI, connect each app (Gmail, Slack, etc.) via OAuth
4. Confirm tools appear under `conduit` (`pd__gmail-*`, `pd__slack_v2-*`, …)

No API keys or env files in `mcp.json`. OAuth is per-user in Conduit.

## Enabled connectors (trimmed defaults)

Connectors are enabled per-user with an explicit tool list — **not** `allTools`.
Ask the agent to adjust via Conduit `set_my_connector_tools` if you need an action
that was trimmed.

| Connector | Tools enabled | Typical use |
|-----------|---------------|-------------|
| `app:gmail` | find-email, list-thread-messages, send-email, list-labels, create-draft | Email search, send, draft |
| `app:google_calendar` | list/get/create/update/delete events, free-busy, calendars | Scheduling |
| `app:google_docs` | find, get, create, append, replace, export, tabs | Doc read/write |
| `app:google_drive` | search, find, get, download, list, create folder/file, share, move | File access |
| `app:google_sheets` | list, get info, read/update/add rows, find rows, create | Spreadsheet data |
| `app:slack_v2` | post, reply, history, search, channels, user lookup, reactions | Slack messaging |
| `app:zoom` | list/get meetings, recordings, summary, transcript, create/update/delete | Meetings / recordings |
| `app:jira` | get/search issues, boards, sprints, projects, comments | BT Jira Cloud |
| `app:jira_service_desk` | list/get/create requests, comment, request types, status, transition | IT / JSM tickets |
| `mcp:jira_ghe` | upstream Workday Jira + GHE MCP (`executeApi`, ticket helpers, …) — `allTools` | jira2 + ghe.megaleo.com |
| `app:google_slides` | **disabled** — re-enable in Conduit if needed |
| `mcp:pagerduty_saas` | **disabled** — enable + OAuth when needed |

**Workspace-allowed but not connected yet:** Asana, Linear, Microsoft Excel, Notion, Smartsheet, TestRail. Enable in Conduit only when you need them.

## Agent routing (Conduit vs supplement MCP)

| Task | Default | Supplement (only if Conduit fails or lacks action) |
|------|---------|-----------------------------------------------------|
| Gmail, Calendar, Drive, Docs, Sheets | **Conduit** | 10x Google Drive CLI / Playwright only for local mount or CDP workflows |
| Slack (agent sessions) | **Conduit** | `personal/slack/cli.py` for scripted/CLI workflows outside MCP |
| Zoom | **Conduit** | `personal/zoom/` SSO CLI for enterprise cookie / `docs.zoom.us` AI summary text |
| BT Jira Cloud (issues, boards, sprints) | **Conduit** `app:jira` | **`jira-bt`** |
| Jira Service Management | **Conduit** `jira_service_desk` | `jira-bt` JSM tools |
| Workday Jira (jira2) + GHE | **Conduit** upstream `mcp:jira_ghe` | do **not** re-add standalone `jira-ghe` in `mcp.json` |
| Confluence PT / BT | — | **`confluence-mcp-pt`** / **`confluence-mcp-bt`** |
| PagerDuty | **Conduit** upstream `mcp:pagerduty_saas` | — |
| Pharos, GHA, Bitbucket, Atlan, Data Hub, etc. | — | respective dedicated MCP |

Do **not** add separate Gmail, Calendar, Drive, Slack, Zoom, or `jira-ghe` MCP servers — Conduit is the path.
`app:jira` is BT Cloud (`workdaybt.atlassian.net`); jira2 + GHE is Conduit `mcp:jira_ghe`.

## Managing tools

Inspect what is enabled:

```
get_my_connectors
```

Trim or add a specific tool (tool slugs without the `pd__` prefix):

```json
set_my_connector_tools({
  "connectorId": "app:gmail",
  "allTools": false,
  "tools": ["send-email", "find-email", "create-draft"]
})
```

Disable a whole connector:

```json
set_connector_enabled({ "connectorId": "app:google_slides", "enabled": false })
```

**Do not** set `allTools: true` to work around a missing action — add the one tool you need.

## Validate

Ask the agent:

- "List my last 5 Gmail messages" → `pd__gmail-find-email`
- "What's on my calendar tomorrow?" → `pd__gcal-list-events`
- "Post a test message to #my-channel" → `pd__slack_v2-post-message`
- "List my upcoming Zoom meetings" → `pd__zoom-list-meetings`
- "Get BT ticket GTMENT-12345" → `pd__jira-get-issue`
- "List my open JSM requests" → `pd__jira_service_desk-list-my-requests`
- "Get SWE-123 details" / "read GHE file …" → Conduit `mcp:jira_ghe` (`getTicketDetails` / `executeApi`)

A successful call on any of these confirms OAuth and tool policy.

## Relationship to 10x CLI connections

| Pattern | When to use |
|---------|-------------|
| **Conduit MCP** | Cursor / Claude Code agent sessions — **required** default for Google Workspace, Slack, Zoom, BT Jira, JSM, jira2 + GHE |
| **CLI wrappers** (`personal/slack/cli.py`, `personal/google-drive/cli.py`, `personal/zoom/`, …) | **Deprecated for agents** — SSO refresh / scripts / Zoom docs AI text / no-Conduit environments only |
| **`jira-bt` MCP** | BT Jira Cloud when Conduit `app:jira` lacks the action or OAuth fails |
| **Direct REST** (`ATLASSIAN_BT_*` in `.env`) | One-off curl when both MCP and Conduit are unavailable |

Agents in this repo should prefer Conduit over reading `.env` credentials for the integrations Conduit covers.

## Gotchas

| Issue | What to do |
|-------|------------|
| Standalone `jira-ghe` returns `Session not found` | Use Conduit upstream tools (`jira_ghe__executeApi` / `mcp__conduit__jira_ghe__*`) — they often still work |
| Google Docs only shows first tab as plain text | `get-document` returns a large JSON; read the `tabs` array (or tab-specific tools) for other tabs |
| Agent reaches for 10x `personal/*/cli.py` | Wrong — Conduit is the agent path; CLIs are deprecated for sessions (see global `~/.claude/CLAUDE.md`) |

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| No `pd__*` / `jira_ghe__*` tools visible | Reload MCP; run `mcp_auth`; check `get_my_connectors`; restart Claude/Cursor after `sync-mcp` |
| Auth / 401 on a connector | Re-OAuth that app in Conduit UI |
| Action missing | `set_my_connector_tools` to add the specific tool slug |
| JSM works in `jira-bt` but not Conduit | Fall back to `jira-bt`; check Conduit JSM OAuth site |
| Too many tools / slow discovery | Ensure Pipedream connectors use explicit tool lists, not `allTools` |

## References

- Conduit UI / MCP URL: Conduit web UI → Connect a client (or `context-atlas` ROUTING.md)
- BT Jira Cloud (supplement MCP): `tool_connections/jira-bt/setup.md`
- ED&A data MCPs (Atlan, Snowflake): `tool_connections/mcp-eda-data-stack.md`
- Cursor routing rule: `~/code/.cursor/rules/conduit-mcp-default.mdc`
