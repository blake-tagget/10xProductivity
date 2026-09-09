---
tool: atlan
type: mcp
status: active
updated: 2026-09-09
description: Atlan hosted MCP — catalog search, lineage, and metadata in Cursor via Workday SSO.
---

# Atlan MCP — Workday ED&A

Atlan provides a **hosted remote MCP** (HTTP + SSO). No API keys, no env files, no tokens in `mcp.json`.

Use it for **catalog metadata** — finding assets, lineage, glossary terms, certifications, and descriptions. For row-level data, pair with **Snowflake MCP** (preferred for agents) or `personal/snowflake/cli.py` when MCP lacks the API you need.

## Status

| Item | State |
|------|-------|
| MCP URL | `https://workday.atlan.com/mcp` |
| Auth | SSO via Cursor `mcp_auth` (no secrets in config) |
| Prerequisite | Atlan access — [ServiceNow AD group request](https://workday.service-now.com/esc?id=sc_cat_item&sys_id=3b8b8b3c1b5b9e90857ea8e82d4bcbeb) (`Okta - Atlan - HT`) |

## Prerequisites

1. **Atlan account** — request via ServiceNow (see below) or your team's onboarding bundle
2. **Cursor** with MCP support

## Cursor setup

Add to `~/.cursor/mcp.json`:

```json
"atlan": {
  "url": "https://workday.atlan.com/mcp"
}
```

Then:

1. **Cursor → Settings → Tools & MCP** — reload or toggle the `atlan` server
2. On first use, run **`mcp_auth`** for Atlan (or click **Needs authentication** in MCP settings)
3. Complete Workday SSO in the browser
4. Confirm tools appear under the `atlan` server (`search_assets_tool`, `semantic_search_tool`, `ask_tool`, etc.)

No `CLIENT_ID`, PAT, or env files — OAuth/SSO is handled by Atlan.

## Validate

Ask the agent to search the catalog, e.g.:

- "Search Atlan for Tables in `CERTIFIED_PROD`"
- "What is the lineage for `BASE_PROD.SALESFORCE`?"
- "Find glossary terms related to customer tenant"

A successful `search_assets_tool` call returning catalog hits confirms the connection.

## Example prompts

- "Which Snowflake tables are certified VERIFIED in the GTM domain?"
- "What feeds `BASE_PROD.SALESFORCE.OPPORTUNITY`?"
- "Find Atlan assets tagged PII in the salesforce schema"
- "Compare descriptions on this table vs its linked glossary term"

Write operations (tagging, metadata updates) use **propose** mode — the agent shows a preview and waits for your approval before executing.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Unauthorized` | Re-run `mcp_auth` and complete SSO |
| Server red / no tools | Toggle `atlan` off and on in MCP settings |
| Permission errors | Same as Atlan UI — check your Atlan role and data-domain access |
| Need row-level data | Use Snowflake CLI (`tool_connections/snowflake/setup.md`), not Atlan `query_assets` unless you have warehouse grants |

## Access request

```bash
# Via 10x ServiceNow CLI (after SSO refresh)
python3 personal/servicenow/cli.py submit atlan \
  --var u_groups="Okta - Atlan - HT"
```

Or bundle with Snowflake/Sigma:

```bash
python3 personal/servicenow/cli.py bundle snowflake sigma atlan \
  --var snowflake:select_env=Production \
  --var snowflake:role=ROLE_DATA_ANALYST \
  --var snowflake:business_justification="ED&A analyst toolset" \
  --var atlan:u_groups="Okta - Atlan - HT"
```

Support: `#ask-eda`

## How this fits the ED&A stack

See `tool_connections/mcp-eda-data-stack.md` for how Atlan relates to Snowflake and dbt MCP options.

## References

- ED&A setup guide pattern: org `mcp-setup-atlan-snowflake-dbt` doc (Atlan section)
- ServiceNow catalog: `tool_connections/servicenow/setup.md`
- Snowflake queries (complement): `tool_connections/snowflake/setup.md`
