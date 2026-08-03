---
tool: snowflake
type: mcp
status: pending-platform-setup
tracking: ISSAS-1780
updated: 2026-07-27
description: Snowflake managed MCP server — setup status, security gates, and Cursor config for Workday ED&A Snowflake.
---

# Snowflake MCP — Workday ED&A

Reference for standing up the **Snowflake-managed MCP server** in Cursor. Distinct from the existing PAT/CLI workflow documented in `connection-pat.md` and `setup.md`.

## Status (2026-07-27)

| Item | State |
|------|-------|
| [awesome/mcp](https://ghe.megaleo.com/awesome/mcp) registry entry | **Not listed** — not yet published as an approved Workday MCP |
| [ISSAS-1780](https://jira2.workday.com/browse/ISSAS-1780) security advisory | Security team guidance **complete**; does not equal rollout approval |
| Shared MCP server in Workflake account | **`SHOW MCP SERVERS IN ACCOUNT` returned zero** (verified with `ROLE_DATA_ANALYST`) |
| Personal Snowflake access | Active — `ROLE_DATA_ANALYST`, `DATA_ANALYSIS_WH` |
| Interim data path | PAT + `personal/snowflake/cli.py` or collab container `radds.snowflake_utils` |

**Blocker:** ED&A must create the MCP server object and OAuth security integration in Snowflake before analysts can connect from Cursor. Individual PAT auth in `mcp.json` is possible for demos but Snowflake recommends OAuth and ISSAS-1780 calls for least-privilege `DEFAULT_ROLE`.

## Security requirements (from ISSAS-1780)

Follow before broad adoption:

- [MCP Security Requirements](https://confluence.workday.com/display/INFSEC/MCP+Security+Requirements)
- [GenAI and Agentic AI Baseline Requirements](https://confluence.workday.com/display/INFSEC/GenAI+and+Agentic+AI+Baseline+Requirements)
- [Snowflake MCP security recommendations](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-mcp#mcp-server-security-recommendations)

Key Snowflake-specific points:

- MCP sessions use the connecting user's **`DEFAULT_ROLE` only** — secondary roles are not supported.
- Set `DEFAULT_ROLE` to a least-privilege role with only the access needed for MCP tools.
- Set `DEFAULT_WAREHOUSE` (sessions fail if null).
- Validate any SQL the agent generates before acting on results.

## What ED&A / platform must provision

1. **MCP server object** — e.g. read-only SQL tool for certified GTM/Salesforce schemas:

```yaml
tools:
  - name: "sql_read_only"
    type: "SYSTEM_EXECUTE_SQL"
    description: "Read-only SQL against certified analyst schemas"
    config:
      read_only: true
      warehouse: "DATA_ANALYSIS_WH"
```

2. **OAuth security integration** with Cursor redirect URIs — see [Set up OAuth authentication](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-mcp#set-up-oauth-authentication). Snowflake does **not** support dynamic client registration; analysts need shared `CLIENT_ID` / `CLIENT_SECRET` from the integration.

3. **Grants** — `USAGE` on the MCP server; `SELECT` on target tables/schemas per tool type.

MCP server URL format (once created):

```
https://<account>.snowflakecomputing.com/api/v2/databases/<db>/schemas/<schema>/mcp-servers/<name>
```

Use hyphens in account URL if the client requires it (Snowflake docs note hostname issues with underscores).

## Cursor config (when server exists)

Add to `~/.cursor/mcp.json` (store secrets in env, not inline):

```json
"snowflake": {
  "url": "https://<account>.snowflakecomputing.com/api/v2/databases/<db>/schemas/<schema>/mcp-servers/<name>",
  "auth": {
    "CLIENT_ID": "${env:SNOWFLAKE_MCP_CLIENT_ID}",
    "CLIENT_SECRET": "${env:SNOWFLAKE_MCP_CLIENT_SECRET}"
  }
}
```

Then **Cursor → Settings → Tools & MCP → Sign in** to complete Snowflake OAuth.

### PAT fallback (demo / personal only)

Snowflake quickstart shows Bearer PAT in headers. Not recommended for production (token leakage risk). Pattern:

```json
"snowflake": {
  "url": "https://<account>.snowflakecomputing.com/api/v2/databases/<db>/schemas/<schema>/mcp-servers/<name>",
  "headers": {
    "Authorization": "Bearer <PAT>"
  }
}
```

Prefer OAuth when the shared integration is available.

## Verify platform readiness

```sql
SHOW MCP SERVERS IN ACCOUNT;
DESCRIBE MCP SERVER <name>;
```

With Cursor connected: ask the agent to list Snowflake MCP tools, then run a trivial read-only query against a certified table.

## Interim: no MCP

Until the shared server exists, use existing paths:

| Path | When |
|------|------|
| `python3 personal/snowflake/cli.py query --sql "..."` | Local 10x venv |
| `radds.snowflake_utils` in collab container | EDDG / notebook workflows |
| Context Atlas routing | `~/code/context-atlas/docs/atlas/ROUTING.md` — Snowflake has no MCP today |

Common schemas: `CERTIFIED_PROD.GTM`, `BASE_PROD.SALESFORCE`, `CERTIFIED_PROD.COMMON`.

## Access prerequisites

- [ServiceNow — Request access to Snowflake](https://workday.service-now.com/esc?id=sc_cat_item&sys_id=9708058d1bf2c650857ea8e82d4bcba3)
- Default analyst role: `ROLE_DATA_ANALYST`
- Support: `#ask-eda`, `#snowflake-rbac-automation-support`

## Who to ask

- **MCP server URL / OAuth credentials:** `#ask-eda`
- **ISSAS-1780 / security posture:** ticket watchers; Sigma PO Nihar Marrapu on related Sigma work

## References

- [Getting Started with Managed Snowflake MCP Server](https://www.snowflake.com/en/developers/guides/getting-started-with-snowflake-mcp-server/)
- [Snowflake-managed MCP server docs](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-mcp)
- [Workday MCP registry](https://ghe.megaleo.com/pages/awesome/mcp/) — check here when Snowflake is published
- [Context Atlas — Snowflake ED&A](https://ghe.megaleo.com/RADDS/context-atlas/blob/main/docs/atlas/domains/snowflake-eda.md)
