---
tool: sigma
type: mcp
status: pending-security-signoff
tracking: ISSAS-1780
updated: 2026-07-27
description: Sigma Computing hosted MCP server — Cursor setup for natural-language BI queries over Snowflake-backed workbooks.
---

# Sigma MCP — Workday ED&A

Sigma provides a **vendor-hosted remote MCP** (HTTP + OAuth). No local install, no API keys in config. The assistant inherits your existing Sigma permissions, including row/column-level security.

## Status (2026-07-27)

| Item | State |
|------|-------|
| [awesome/mcp](https://ghe.megaleo.com/awesome/mcp) registry entry | **Not listed** |
| [ISSAS-1780](https://jira2.workday.com/browse/ISSAS-1780) | Security guidance complete; **Sigma not fully approved** — vendor clarifying MCP security requirements with Sigma PO (Nihar Marrapu) |
| Endpoint reachability | `https://aws-api.sigmacomputing.com/mcp/v2` returns OAuth protected-resource metadata |
| Prerequisite | Snowflake ED&A access, then [Sigma ServiceNow request](https://workday.service-now.com/esc?id=sc_cat_item&sys_id=e8538ab21b5b9e90857ea8e82d4bcbeb) |

**Note:** Early ISSAS-1780 review mistakenly scanned `SigmaHQ/sigma-mcp-server` (open-source Sigma *rules* MCP). The actual target is Sigma Computing's **hosted BI MCP** at `aws-api.sigmacomputing.com/mcp/v2`.

## Prerequisites

1. **Sigma account** with:
   - "Use Sigma MCP with OAuth" permission on your account type
   - View permissions for connections / data models / workbooks you need
   - At least Can view on target documents; Can use on target connections
2. **Org AI features enabled** — Sigma admin must enable AI for the organization
3. **Snowflake access** — Sigma is warehouse-native; Snowflake is its only data source at Workday

## Get your MCP URL

1. Log in to Sigma (Workday ED&A instance)
2. **Profile (user icon) → MCP → Sigma MCP**
3. Copy the MCP URL listed there

ISSAS-1780 references `https://aws-api.sigmacomputing.com/mcp/v2` for Workday's AWS-hosted Sigma. Use the URL from your profile if it differs.

## Cursor setup

Add to `~/.cursor/mcp.json`:

```json
"sigma": {
  "url": "https://aws-api.sigmacomputing.com/mcp/v2"
}
```

Replace the URL with your org-specific URL from Profile → MCP if different.

Then:

1. **Cursor → Settings → Tools & MCP**
2. Find `sigma` — click **"Needs authentication"** (if Connect does nothing, this is a known Cursor OAuth quirk; see [forum thread](https://forum.cursor.com/t/remote-mcp-server-connect-button-produces-zero-network-requests-oauth-flow-never-starts/150962))
3. Complete Sigma OAuth in the browser
4. Confirm tools appear under the sigma server

No `CLIENT_ID` / secrets in config — OAuth is handled by Sigma.

## Security requirements (from ISSAS-1780)

- [MCP Security Requirements](https://confluence.workday.com/display/INFSEC/MCP+Security+Requirements)
- [GenAI Baseline Requirements](https://confluence.workday.com/display/INFSEC/GenAI+and+Agentic+AI+Baseline+Requirements)
- OAuth inherits Sigma RBAC — assistant only sees what you can see
- Data classification: Confidential/Restricted GTM/Salesforce data in scope; controls apply at the LLM/client layer where results land
- Open action (from security review): federate Sigma OAuth to Workday Okta SSO with phishing-resistant MFA

## Example prompts (once connected)

- "Does the `<table>` exist in the Sample Data connection in Sigma?"
- "What columns are available in `<table>` in Sigma?"
- "Use Sigma to find the top 10 stores by total sales in 2024."

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| "Couldn't reach the MCP server" | Wrong URL — re-copy from Profile → MCP → Sigma MCP |
| Connect button does nothing | Click "Needs authentication" text instead; or copy auth URL from Output → MCP:sigma |
| No tools after auth | Check account type has "Use Sigma MCP with OAuth"; confirm org AI features enabled |
| Permission errors on query | Same as Sigma UI — need Can view / Can use on the underlying document or connection |

## Access request

```bash
# Via 10x ServiceNow CLI (after SSO refresh)
python3 personal/servicenow/cli.py submit sigma \
  --var business_function="Enterprise Data & Analytics (ED&A)" \
  --var pii_information=No \
  --var business_justification="Need Sigma MCP for analyst workflows in Cursor"
```

Catalog: [Request access to Sigma](https://workday.service-now.com/esc?id=sc_cat_item&sys_id=e8538ab21b5b9e90857ea8e82d4bcbeb)  
Support: `#ask-eda`

## References

- [Sigma — Use the Sigma MCP Server](https://sigma-enterprise-group.readme.io/docs/use-sigma-mcp-server)
- [ISSAS-1780](https://jira2.workday.com/browse/ISSAS-1780)
- [Context Atlas — Sigma](https://ghe.megaleo.com/RADDS/context-atlas/blob/main/docs/atlas/domains/sigma.md)
- [Cursor MCP docs](https://cursor.com/docs/mcp)
