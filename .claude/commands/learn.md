---
description: Capture API/tool discoveries from this session and update the relevant connection docs in this repo
---

# /learn — Capture Session Learnings

You just did something non-trivial to call an external API or tool. Now capture what you learned so the next session starts with better context.

## Your task

Review the current conversation and extract anything that was **discovered, corrected, or validated** about calling external APIs or tools. Then update the appropriate docs.

### Step 1 — Identify what was learned

Look for:
- Endpoint URLs or tRPC procedures that were tried (both working and 404/failed ones)
- Correct request format (HTTP method, query params, request body shape)
- Schema validation errors that revealed required fields
- Auth quirks (headers, cookie names, workspace IDs)
- Response structure (where data lives in the JSON)
- Pagination or batching behavior
- Techniques that worked around limitations (e.g. querying multiple times to stitch together data)
- Endpoints confirmed to NOT exist (saves future trial-and-error)

### Step 2 — Identify which tool/connection this belongs to

Find the tool you were working with and match it to a file in `personal/`:

```bash
ls personal/   # see what tool dirs exist
```

If `personal/{tool}/api-patterns.md` doesn't exist yet, create it.

### Step 3 — Update the personal docs

Read the existing `personal/{tool}/api-patterns.md` (if it exists). Then update it:

- **Add** newly discovered working endpoints with their exact schemas and example code
- **Add** confirmed dead-end endpoints to a "don't bother" list
- **Update** any patterns that turned out to be wrong
- **Add** techniques or workarounds that reduced API calls (e.g. snippet iteration, batch format)
- Keep code snippets copy-paste ready — they are the primary value
- Add `updated: YYYY-MM-DD` to the frontmatter

### Step 4 — Update connection-sso.md if auth changed

If you discovered something new about auth (new headers, cookie names, token formats), also update `personal/{tool}/connection-sso.md` → "Verified snippets" section.

### Step 5 — Abstract specifics and publish to tool_connections

`personal/` is gitignored — learnings captured there stay private. To share them with others, extract the generic, reusable knowledge and publish it to `tool_connections/{tool}/api-patterns.md`.

**What belongs in `tool_connections/` (publishable):**
- API schemas, required fields, correct request formats
- Response structure (field names, nesting, types)
- Working endpoint list and confirmed 404s
- Error messages and their fixes
- Reusable code patterns that reference env vars (not hardcoded values)

**What stays in `personal/` only (private):**
- Actual credential values, tokens, session cookies
- Personal asset IDs, chat IDs, or workspace IDs specific to your account
- Content from meetings or documents (transcripts, summaries, notes)
- Queries that reference specific people or internal projects

**How to abstract:**
- Replace any hardcoded ID, token, or URL with `env["VAR_NAME"]` using existing env var names from `.env`
- Replace personal examples ("search for a specific person's meeting") with generic placeholders ("search for meeting by participant name")
- Keep code snippets runnable — they should work for anyone with valid `.env` creds

**Sanitization scan — check for these before considering Step 5 done:**

| Pattern | Where it hides | Fix |
|---|---|---|
| Email addresses | `# →` output comments, `.env` example values | `your@email.com` |
| Real names | `# →` output, transcript snippet examples, verified-by lines | `Alice`, `Bob`, or remove |
| Hardcoded IDs in `.py` constants | `INVITE_URL = "https://..."`, `chat_id = "..."` | Placeholder string or `env["VAR"]` |
| Resource IDs in code examples | Board IDs, meeting doc IDs, chat IDs used in snippets | `<RESOURCE_ID>` or `env["VAR"]` |
| Org-specific subdomains in Notes | `yourorg.tool.com`, `yourorg.okta.com` | `<your-org>.tool.com` |
| Meeting/document names in `# →` | Output comments echoing real resource names | Generic placeholder |
| Account/tenant identifiers | Snowflake account IDs, workspace slugs in URLs | `<account-id>` |

Read the existing `tool_connections/{tool}/api-patterns.md` (if any), then update it with the abstracted learnings. Create it if it doesn't exist yet.

### Step 6 — Sync commands to Cursor skills

Run the sync script to keep `.cursor/skills/` up to date with any changes made in steps above:

```bash
python3 .claude/sync-skills.py
```

This regenerates `.cursor/skills/{name}/SKILL.md` from every `.claude/commands/*.md` file. Always run it after editing any command.

---

## Output

After updating the files, briefly summarize what was added/changed — one bullet per file touched. No need for lengthy explanation.
