---
type: tracking
tracking: ISSAS-1780
updated: 2026-07-27
description: Rollup tracker for Snowflake and Sigma MCP adoption at Workday — security gates, registry status, and setup pointers.
---

# MCP tracker — Snowflake & Sigma (ISSAS-1780)

Single reference for the analyst-community request to use Snowflake and Sigma MCP servers from Cursor/Claude for read-only GTM / Salesforce analysis.

**Jira:** [ISSAS-1780](https://jira2.workday.com/browse/ISSAS-1780)  
**Registry:** [awesome/mcp](https://ghe.megaleo.com/awesome/mcp) — neither server listed yet (2026-07-27)

## Summary

| MCP | Host | Auth | Can set up today? | Detail doc |
|-----|------|------|-------------------|------------|
| **Sigma** | Sigma SaaS (`aws-api.sigmacomputing.com/mcp/v2`) | OAuth 2.1 | **Yes**, if you have Sigma access + MCP permission | `tool_connections/sigma/setup.md` |
| **Snowflake** | Snowflake-managed in ED&A account | OAuth (recommended) or PAT | **No** — no MCP server object in account yet | `tool_connections/snowflake/mcp.md` |

## ISSAS-1780 timeline (abbreviated)

| Date | Event |
|------|-------|
| 2026-06-10 | Cody Reynolds files request for analyst community (Product Ops, Commercial Insights, Business Finance, Marketing Analytics) |
| 2026-06-24 | Security scan posted (initially wrong target — open-source Sigma *rules* MCP, not Sigma BI MCP) |
| 2026-06-25 | Corrected: actual target is Sigma Computing hosted MCP; architecture = remote SaaS, OAuth, permission inheritance |
| 2026-06-30 | Security outlines MCP + GenAI baseline requirements for both servers |
| 2026-07-22 | Nihar Marrapu: ticket "Done" = security advisory complete, **not** Sigma approval; vendor review ongoing |
| 2026-07-23 | Alvin Kuruvilla: security advises on risk; does not "approve" tickets |

## Security gates (both MCPs)

- [MCP Security Requirements](https://confluence.workday.com/display/INFSEC/MCP+Security+Requirements)
- [GenAI and Agentic AI Baseline Requirements](https://confluence.workday.com/display/INFSEC/GenAI+and+Agentic+AI+Baseline+Requirements)

**Snowflake-specific:** least-privilege `DEFAULT_ROLE`, validate generated SQL, [Snowflake MCP security recs](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-mcp#mcp-server-security-recommendations).

**Sigma-specific:** vendor-hosted; OAuth inherits Sigma RBAC; Okta SSO federation for MCP OAuth called out as action item.

## Verification done (2026-07-27)

- Snowflake PAT connection works (`ROLE_DATA_ANALYST`, `DATA_ANALYSIS_WH`)
- `SHOW MCP SERVERS IN ACCOUNT` → empty (no shared server deployed)
- Sigma MCP endpoint returns OAuth protected-resource metadata at `/.well-known/oauth-protected-resource`

## Next actions

1. **Sigma:** Add `sigma` block to `~/.cursor/mcp.json`, OAuth in Cursor settings (see `sigma/setup.md`)
2. **Snowflake:** Ask `#ask-eda` when shared MCP server + OAuth client credentials will be available
3. **Watch ISSAS-1780** for Sigma final security sign-off before treating as org-blessed for broad rollout
4. **Watch awesome/mcp** for official registry entries when published

## Interim data access (no MCP)

Snowflake queries today: `personal/snowflake/cli.py` or collab `radds.snowflake_utils` — see `tool_connections/snowflake/setup.md`.
