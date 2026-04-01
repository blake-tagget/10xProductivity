---
tool: slack
type: api-patterns
description: Verified Slack API patterns — search, DMs, Slack AI synthesis. Covers enterprise restrictions and fastest paths for common tasks. Read before writing any Slack API code.
updated: 2026-04-01
---

# Slack API — Verified Patterns

## Auth setup

```python
from pathlib import Path
import urllib.request, json, ssl, urllib.parse

env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
xoxc, d = env["SLACK_XOXC"], env["SLACK_D_COOKIE"]

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

def api(method, endpoint, data=None, params=None):
    url = f"https://slack.com/api/{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url,
        data=json.dumps(data).encode() if data else None,
        headers={"Authorization": f"Bearer {xoxc}", "Cookie": f"d={d}",
                 "Content-Type": "application/json; charset=utf-8"},
        method=method)
    with urllib.request.urlopen(req, context=ssl_ctx, timeout=15) as resp:
        return json.loads(resp.read())
```

---

## ⚠ Enterprise-restricted endpoints

On enterprise Slack instances, the following endpoints are blocked. Do not attempt them:

| Endpoint | Error |
|---|---|
| `conversations.list` | `enterprise_is_restricted` |
| `users.list` | returns 0 members |
| `users.lookupByEmail` | `not_allowed_token_type` |

Do not try to enumerate users or list DM channels directly. Use Slack AI (see below) to resolve people by name.

---

## Finding messages from a named person — use Slack AI first

`search.messages` with `from:username` requires knowing the exact Slack handle. On enterprise instances, there is no reliable way to resolve a real name to a handle. Slack AI resolves people by real name and has broader internal access.

**Fastest path:**

1. Post a natural-language question to the Slackbot DM
2. Slack AI resolves the person and searches across channels and DMs
3. It returns a summary with message links containing channel IDs and timestamps
4. Use `conversations.history` on the returned channel ID to read the full thread

```python
import time

# Step 1: Open Slackbot DM (USLACKBOT is the same across all workspaces)
r = api("POST", "conversations.open", {"users": "USLACKBOT"})
slackbot_dm = r["channel"]["id"]

# Step 2: Ask Slack AI
r = api("POST", "chat.postMessage", {
    "channel": slackbot_dm,
    "text": "Find messages from Jane Smith to me today — what did they ask about?"
})
msg_ts = r["ts"]

# Step 3: Poll for AI response (arrives in ~1-5s, but can take up to 60s for complex queries)
for _ in range(30):
    time.sleep(2)
    r = api("GET", "conversations.replies",
            params={"channel": slackbot_dm, "ts": msg_ts, "limit": "20"})
    ai_replies = [m for m in r.get("messages", [])
                  if float(m.get("ts", "0")) > float(msg_ts) and m.get("subtype") == "ai"]
    if ai_replies and ai_replies[-1].get("text", "") != "_Thinking..._":
        print(ai_replies[-1].get("text", ""))
        break

# Step 4: Parse the channel ID from the message links in the AI response
# Link format: https://<workspace>.slack.com/archives/<CHANNEL_ID>/p<TIMESTAMP>
# Use conversations.history on that channel ID to read the full thread
```

---

## Reading a thread by channel ID

Once you have a channel ID (from Slack AI output, a message link, or known in advance):

```python
import time as _time

oldest_ts = _time.time() - 86400  # last 24h; or pass a specific epoch timestamp

r = api("GET", "conversations.history",
        params={"channel": "<CHANNEL_ID>", "limit": "50", "oldest": str(oldest_ts)})

for m in reversed(r.get("messages", [])):  # reversed = oldest first
    print(f"[{m.get('ts')}] {m.get('user', 'bot')}: {m.get('text', '')[:300]}")
```

---

## Keyword search with date filter — `search.messages`

Works well for topic/keyword searches across channels. Not reliable for `from:` lookups without an exact handle.

```python
from datetime import datetime
today = datetime.now().strftime("%Y-%m-%d")

r = api("GET", "search.messages",
        params={"query": f"your keyword after:{today}", "count": "20", "sort": "timestamp"})

for m in r.get("messages", {}).get("matches", []):
    print(f"{m.get('channel', {}).get('name')}: {m.get('text', '')[:200]}")
```

**Supported operators:**
- `in:#channel-name` — specific channel
- `from:@username` — by exact Slack handle
- `after:YYYY-MM-DD` / `before:YYYY-MM-DD`
- `has:link` / `has:file`

---

## Parsing a Slack message URL to channel ID + timestamp

```python
import re

# URL format: https://<workspace>.slack.com/archives/<CHANNEL_ID>/p<TIMESTAMP_NO_DOT>
m = re.search(r"/archives/([A-Z0-9]+)/p(\d+)", slack_url)
channel_id = m.group(1)
ts = m.group(2)[:10] + "." + m.group(2)[10:]  # p1775066970557599 → 1775066970.557599
```

Channel ID prefixes: `D` = DM, `C` = public/private channel, `G` = group DM

---

## Common errors and fixes

| Error | Cause | Fix |
|---|---|---|
| `enterprise_is_restricted` | Endpoint blocked on enterprise instance | See restricted list above — use Slack AI instead |
| `not_allowed_token_type` | xoxc token can't use this endpoint | Don't use — find alternative |
| `channel_not_found` | Wrong channel ID or no access | Verify ID from Slack AI response or message link |
| `0 results` from `from:name` search | Handle doesn't match exactly | Use Slack AI people-lookup instead |
| Slack AI stuck on `_Thinking..._` | Still processing | Poll up to 60s — complex queries take longer |
| `401` | Session token expired (~8h TTL) | Re-run `python3 tool_connections/shared_utils/playwright_sso.py --slack-only` |
