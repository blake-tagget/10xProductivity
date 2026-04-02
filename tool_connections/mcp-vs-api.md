---
type: usage-notes
description: When to use MCP convenience tools vs direct API (executeApi) for Workday internal tools, based on observed reliability.
updated: 2026-04-01
---

# MCP Convenience Tools vs Direct API

## TL;DR

**Prefer `executeApi` (direct API) over MCP convenience tools for most operations.** Convenience tools have hidden assumptions that silently fail or error. `executeApi` gives you full control and is more reliable — it's just a thin auth-injecting wrapper around the raw API.

---

## What the MCPs are (and aren't)

The Workday internal MCPs (`jira-ghe`, `workday-mcp-bitbucket-server`, `confluence-mcp-bt/pt`) work like this:

- **Convenience tools** (`getPullRequestDetailsAndFiles`, `get_file_content`, etc.) — pre-built wrappers with opinions baked in. Fast when they work; opaque when they don't.
- **`executeApi` / `executeApi`-equivalent** — a JavaScript sandbox that injects auth headers and lets you make raw API calls via `ghe()` or `jira()` fetch helpers. This is the direct API approach.

---

## Observed reliability issues with convenience tools

### `getPullRequestComments` (jira-ghe) — fails outside a git repo

```
Failed to get PR comments: spawnSync git ENOENT
```

This tool shells out to `git` locally to resolve context. It fails entirely when Claude Code isn't running inside the repo directory. `executeApi` has no such assumption.

### `executeApi` returns headers, not body, on first call

The `ghe()` / `jira()` helpers return a fetch `Response` object — not the parsed JSON. You must call `.json()` explicitly:

```javascript
// WRONG — returns Response headers object, not data
const result = await ghe('/repos/UIC/EDDG-RDA/pulls/294/reviews/5088657');
return result; // ← just headers

// CORRECT — parse the body
const res = await ghe('/repos/UIC/EDDG-RDA/pulls/294/reviews/5088657');
const data = await res.json();
return data; // ← actual payload
```

### `pharos-cli` MCP — frequently hangs or returns empty

Use the terminal CLI instead:
```bash
pharos sql run --sql "SELECT * FROM uxresearch.my_table LIMIT 5"
```

---

## When convenience tools ARE fine

- `getPullRequestDetailsAndFiles` — reliable, no env assumptions, good for reading PR file diffs
- `get_file_content` (Bitbucket) — reliable for reading repo files
- `browse_repository` (Bitbucket) — reliable for exploring repo structure
- `list_pages_in_space` / `get_page_content` (Confluence) — reliable

---

## The direct API pattern for jira-ghe

Always use this two-step pattern in `executeApi`:

```javascript
// Single call
const res = await ghe('/repos/OWNER/REPO/pulls/123');
const pr = await res.json();
return pr;

// Multiple calls — chain them
const prRes = await ghe('/repos/OWNER/REPO/pulls/123');
const pr = await prRes.json();

const commentsRes = await ghe('/repos/OWNER/REPO/issues/123/comments');
const comments = await commentsRes.json();

return { pr, comments };
```

For POST/PATCH:
```javascript
const res = await ghe('/repos/OWNER/REPO/issues/123/comments', {
  method: 'POST',
  body: JSON.stringify({ body: 'My comment' })
});
const data = await res.json();
return { status: res.status, url: data.html_url };
```

---

## 10x tools (Slack, Outlook, Google Drive, Sana) — already direct API

The 10x tool connections use direct Python HTTP calls (no MCP protocol overhead). These are already the right approach:

- More reliable — no hidden assumptions
- Auth is explicit (env vars / playwright session)
- Full control over request/response

No changes needed for 10x tools — they're already the preferred pattern.

---

## Summary

| Tool | Approach | Reliability |
|---|---|---|
| `jira-ghe` convenience tools | avoid for comments/context ops | inconsistent |
| `jira-ghe` executeApi | use this | reliable with `.json()` pattern |
| `workday-mcp-bitbucket-server` file/browse ops | fine | reliable |
| `pharos-cli` MCP | avoid | hangs frequently |
| pharos terminal CLI | use this | reliable |
| 10x Python direct API | use this | reliable |
