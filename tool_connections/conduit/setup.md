---
tool: conduit
type: mcp
status: active
updated: 2026-09-17
description: Workday Conduit — default hosted MCP for Google Workspace, Slack, JSM, and other SaaS via Pipedream OAuth.
---

# Conduit MCP — default integration layer

Conduit is a **hosted remote MCP** (Workday-internal; URL from the
[Workday MCP registry](https://ghe.megaleo.com/pages/awesome/mcp/)) that exposes
approved SaaS connectors (Pipedream-backed) through one server. Use it as the
**default path** for Gmail, Calendar, Drive, Docs, Sheets, Slack, and Jira Service
Management in Cursor and Claude Code. Reach for dedicated MCPs only when Conduit
lacks the capability or the call fails.

**Why Conduit first:** one OAuth surface, per-user tool trimming, no secrets in
`mcp.json`, and far fewer tools than enabling every Pipedream action (`allTools`).

## Status

| Item | State |
|------|-------|
| MCP URL | Conduit MCP endpoint from the Workday MCP registry |
| Auth | Conduit / Pipedream OAuth (per connector); no tokens in config |
| Tool namespace | `conduit` server → tools prefixed `pd__` (e.g. `pd__slack_v2-post-message`) |
| Routing rule | `~/code/.cursor/rules/conduit-mcp-default.mdc` (always apply) |
| Team routing doc | `context-atlas/docs/atlas/ROUTING.md` → Conduit-first section |

## Cursor setup

List **Conduit first** in `~/.cursor/mcp.json` so it is the primary integration server:

```json
"conduit": {
  "url": "<conduit-mcp-url-from-registry>",
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
| `app:google_calendar` | list/get/create/update/delete events, free-busy | Scheduling |
| `app:google_docs` | find, get, create, append, replace, export | Doc read/write |
| `app:google_drive` | search, find, get, download, list, create folder/file, share | File access |
| `app:google_sheets` | list, get info, read/update/add rows, find rows | Spreadsheet data |
| `app:slack_v2` | post, reply, history, search, channels, user lookup | Slack messaging |
| `app:jira_service_desk` | list/get/create requests, comment, request types, status, transition | IT / JSM tickets |
| `app:google_slides` | **disabled** — re-enable in Conduit if needed |
| `mcp:pagerduty_saas` | **disabled** — enable + OAuth when needed |

**Workspace-allowed but not connected yet:** Asana, Linear, Microsoft Outlook/Excel/Calendar, Notion, SharePoint, Smartsheet, Zoom. Enable in Conduit only when you need them.

## Agent routing (Conduit vs supplement MCP)

| Task | Default | Supplement (only if Conduit fails or lacks action) |
|------|---------|-----------------------------------------------------|
| Gmail, Calendar, Drive, Docs, Sheets | **Conduit** | — |
| Slack (agent sessions) | **Conduit** | `personal/slack/cli.py` for scripted/CLI workflows outside MCP |
| Jira Service Management | **Conduit** `jira_service_desk` | `jira-bt` JSM tools |
| BT Jira dev (issues, sprints, boards) | — | **`jira-bt`** |
| Workday Jira (jira2) + GHE | — | **`jira-ghe`** |
| Confluence PT / BT | — | **`confluence-mcp-pt`** / **`confluence-mcp-bt`** |
| PagerDuty | **Conduit** upstream `mcp:pagerduty_saas` | — |
| Pharos, GHA, Bitbucket, Atlan, Data Hub, etc. | — | respective dedicated MCP |

Do **not** add separate Gmail, Calendar, Drive, or Slack MCP servers — Conduit is the path.

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
- "List my open JSM requests" → `pd__jira_service_desk-list-my-requests`

A successful call on any of these confirms OAuth and tool policy.

## Relationship to 10x CLI connections

| Pattern | When to use |
|---------|-------------|
| **Conduit MCP** | Cursor / Claude Code agent sessions — default for Google Workspace, Slack, JSM |
| **CLI wrappers** (`personal/slack/cli.py`, `personal/google-drive/cli.py`, …) | Scripts, SSO refresh, enterprise-search workflow, environments without Conduit |
| **Direct REST** (`ATLASSIAN_BT_*` in `.env`) | One-off curl when both MCP and Conduit are unavailable |

Agents in this repo should prefer Conduit over reading `.env` credentials for the integrations Conduit covers.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| No `pd__*` tools visible | Reload MCP; run `mcp_auth`; check `get_my_connectors` |
| Auth / 401 on a connector | Re-OAuth that app in Conduit UI |
| Action missing | `set_my_connector_tools` to add the specific tool slug |
| JSM works in `jira-bt` but not Conduit | Fall back to `jira-bt`; check Conduit JSM OAuth site |
| Too many tools / slow discovery | Ensure connectors use explicit tool lists, not `allTools` |

## References

- Conduit UI and MCP URL: Workday MCP registry → search **Conduit**
- BT Jira dev (supplement): `tool_connections/jira-bt/setup.md`
- ED&A data MCPs (Atlan, Snowflake): `tool_connections/mcp-eda-data-stack.md`
- Cursor routing rule: `~/code/.cursor/rules/conduit-mcp-default.mdc`
