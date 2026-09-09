---
type: reconciliation
updated: 2026-09-09
description: Reconcile ED&A MCP setup guidance (Atlan, Snowflake, dbt) with 10xProductivity patterns — what to adopt, what to defer, and when to reconsider.
---

# ED&A data stack MCP — reconciliation

ED&A publishes a three-server MCP profile for Cursor: **Atlan**, **Snowflake**, and **dbt Cloud**. This doc maps that guidance onto 10xProductivity — what we use today, what we defer, and what would need to change to adopt an alternative.

**Decision principle:** use the right surface for the job. For agent-driven Snowflake work, prefer MCP over CLI scripts — repeated CLI connections from agent loops can trigger account lockouts; MCP carries that risk with less effort.

---

## Summary

| Tool | ED&A MCP guide | 10x position | Action |
|------|----------------|--------------|--------|
| **Atlan** | Remote MCP + SSO | **Adopt MCP** | `tool_connections/atlan/setup.md` |
| **Snowflake** | Stdio MCP + `~/.env.mcp.snowflake` (PAT) | **MCP for agents, CLI as supplement** | MCP default in Cursor; CLI when MCP lacks an API |
| **dbt Cloud** | Stdio MCP + `~/.env.mcp.dbt` + `dbt_cloud.yml` | **Defer** — no access yet | Revisit when provisioned |

---

## Atlan — adopt MCP

**Why:** SSO-only, no secrets in config, strong catalog/lineage tooling that complements (not replaces) Snowflake SQL.

**Setup:** `tool_connections/atlan/setup.md`

**Pairing:** Use Atlan for *what exists and how it connects*; use **Snowflake MCP** for agent SQL and sampling; use CLI only when MCP lacks the API you need.

---

## Snowflake — MCP + CLI (use both, prefer MCP for agents)

Three different "Snowflake + agent" patterns appear across ED&A docs and 10x. They are **not interchangeable** — each solves a different integration shape. In practice you use **two**: MCP for agent work, CLI for gaps.

### Why prefer MCP for agent queries

Agents that drive the Snowflake CLI in a loop (many `cli.py query` calls in one session) can open repeated connections under your PAT. That pattern has triggered **account lockouts** in practice. Snowflake MCP keeps the session managed by the MCP server — less connection churn, less lockout risk, and easier to reason about for multi-step agent tasks.

**Rule of thumb:**

| Who is querying | Prefer |
|-----------------|--------|
| Cursor / Claude agent (multi-step, exploratory) | **Snowflake MCP** |
| You, manually, one-off | CLI or MCP — either is fine |
| Script needing an API MCP doesn't expose | **CLI** |
| EDDG / collab container (`radds.snowflake_utils`) | Existing container path |

The CLI still has **more APIs** (extra introspection helpers, batch scripting). Keep it installed — just don't default agents to shell out to it for routine SQL.

### A. PAT CLI via `~/.snowflake/config.toml` — supplement

| | |
|---|---|
| **How** | `personal/snowflake/cli.py` reads `config.toml` internally; credentials never enter agent context |
| **Credential home** | `~/.snowflake/config.toml` (Snowflake VSCode extension) |
| **Status** | Working — `cli.py check` returns user, role, warehouse |
| **Best for** | APIs MCP doesn't cover, local scripts, EDDG/collab workflows, manual one-offs |

**Caution for agents:** avoid chaining many CLI queries in one agent turn. Prefer MCP for that workload.

### B. ED&A stdio Snowflake MCP + `~/.env.mcp.snowflake` ← **agent default**

| | |
|---|---|
| **How** | Cursor launches a stdio MCP server; server loads PAT from `~/.env.mcp.snowflake` |
| **Credential home** | `~/.env.mcp.snowflake` (`chmod 600`) — can be synced from `config.toml` |
| **Auth vars** | `SNOWFLAKE_AUTHENTICATOR=PROGRAMMATIC_ACCESS_TOKEN`, `SNOWFLAKE_TOKEN`, role, warehouse, database, schema |
| **Config source** | Org pack `eda-agent-skills` → `plugins/dataops-engineer/mcp.json` |
| **Best for** | Agent SQL, schema browse, row sampling — default path in Cursor |

**Tradeoffs vs CLI:**

| Factor | CLI (A) | MCP (B) |
|--------|---------|---------|
| Agent multi-query safety | Higher lockout risk | Lower — managed session |
| API surface | Broader | Covers most agent needs |
| Agent integration | Shell subprocess | Native MCP tools in Cursor |
| Credential copies | One (`config.toml`) | Two unless synced from `config.toml` |

**Credential bridge:** generate `~/.env.mcp.snowflake` from `config.toml` (don't hand-maintain a second PAT). A `--sync-mcp` flag on `connection.py` would be the natural bridge — not built yet.

### C. Snowflake-managed MCP + OAuth (ISSAS-1780 track)

| | |
|---|---|
| **How** | Remote MCP URL on Snowflake account; OAuth `CLIENT_ID` / `CLIENT_SECRET` |
| **Credential home** | Env vars for OAuth client; user auth via Cursor sign-in |
| **Status** | **Blocked** — `SHOW MCP SERVERS IN ACCOUNT` empty as of 2026-07-27; ED&A must provision server object |
| **Best for** | Org-wide least-privilege MCP with Snowflake-native tool definitions |

**Detail:** `tool_connections/snowflake/mcp.md`

**When to reconsider C:** ED&A deploys a shared MCP server and publishes OAuth credentials. May supersede or coexist with B — ask `#ask-eda` which is canonical when that happens.

### Snowflake token management — one rule

**Source of truth:** `~/.snowflake/config.toml`

Do **not** maintain parallel PAT copies in `10xProductivity/.env`, `~/.env.mcp.snowflake`, and `mcp.json` unless you have actively adopted that integration. The ED&A guide's "secrets in env files, never in `mcp.json`" is good hygiene for MCP servers; it does not require abandoning `config.toml` — it requires not duplicating tokens by hand.

`connection.py --sync` writes to `10xProductivity/.env` for legacy scripts. That is optional and separate from MCP env files.

---

## dbt Cloud — defer

No dbt Cloud access yet. When provisioned, the ED&A guide expects:

| Item | Purpose |
|------|---------|
| `~/.dbt/dbt_cloud.yml` | Host `cloud.workday.privatelink.getdbt.com`, account/project IDs |
| `~/.env.mcp.dbt` | `DBT_PROJECT_DIR`, `DBT_TOKEN_FILE` |
| `mcp.json` block | From `eda-agent-skills` pack; includes `DISABLE_TOOLS` for privatelink tenant |
| Validation | List jobs via MCP; ad-hoc runs in lower-env CI only |

**10x action when ready:** add `tool_connections/dbt/setup.md` following the Atlan/Sigma MCP pattern. Until then, agents should not attempt dbt MCP setup.

**Relationship to Snowflake:** dbt MCP orchestrates dbt Cloud jobs and project metadata; it does not replace Snowflake CLI for warehouse queries. Atlan covers lineage/catalog across the stack.

---

## Recommended agent routing

| Question type | Tool |
|---------------|------|
| "What tables exist / what's certified / lineage?" | **Atlan MCP** |
| "Run this SQL / sample rows / list schemas" | **Snowflake MCP** (not CLI loops) |
| "Need a CLI-only API / batch script outside Cursor" | **Snowflake CLI** |
| "Trigger a dbt job / inspect dbt models" | **dbt MCP** (when provisioned) |
| "BI workbook / Sigma semantic layer" | **Sigma MCP** (`tool_connections/sigma/setup.md`) |

---

## Open questions for `#ask-eda`

1. Is managed MCP (C) still planned alongside stdio MCP (B), or does one supersede the other?
2. Where is `eda-agent-skills` `plugins/dataops-engineer/mcp.json` published for analysts who don't have the pack cloned?
3. Does the stdio Snowflake MCP expose connection-pooling or rate limits that formally address PAT lockout risk?

---

## References

- Atlan setup: `tool_connections/atlan/setup.md`
- Snowflake CLI: `tool_connections/snowflake/setup.md`
- Snowflake managed MCP (blocked): `tool_connections/snowflake/mcp.md`
- Sigma MCP tracker: `tool_connections/mcp-snowflake-sigma.md`
- ServiceNow bundles: `tool_connections/servicenow/setup.md`
