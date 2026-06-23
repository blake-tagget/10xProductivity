---
tool: miro
type: api-patterns
description: Verified Miro internal API patterns — read AND write. REST /api/v1/ for reads; window.miro.board SDK via headless Playwright for writes/deletes (REST write endpoints are CSRF-blocked). Read before writing any Miro API code.
updated: 2026-06-23
---

# Miro API — Verified Patterns

## Critical: Use the internal `miro.com/api/v1/` API, NOT `api.miro.com/v2/`

The official REST API (`api.miro.com/v2/`) requires OAuth app registration. The internal API uses the same `token` session cookie the browser uses — no app needed.

```python
from pathlib import Path
import urllib.request, json, ssl, urllib.parse, re, html

env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}

HEADERS = {"Cookie": f"token={env['MIRO_TOKEN']}", "Accept": "application/json"}
BASE = "https://miro.com/api/v1"
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE

def miro_get(path):
    req = urllib.request.Request(f"{BASE}{path}", headers=HEADERS)
    try:
        resp = urllib.request.urlopen(req, context=ctx, timeout=20)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode()[:500]}
```

---

## Verified endpoints

### `GET /users/me/` — current user
```python
r = miro_get("/users/me/")
# → {"name": "...", "email": "...", "lastKnownOrgId": "..."}
```

### `GET /recent-boards` — recently viewed boards
```python
boards = miro_get("/recent-boards")
# Returns a LIST directly (not {"data": [...]})
for b in boards:
    print(b["id"], b["title"])
```

### `GET /boards/{board_id}/` — board metadata
```python
board_id = urllib.parse.quote("BOARD_ID_HERE=", safe="")
board = miro_get(f"/boards/{board_id}/")
print(board["title"], board["description"])
```

### `GET /boards/{board_id}/frames` — list frames with titles and positions
```python
board_id = urllib.parse.quote(env["MIRO_BOARD_ID"], safe="")
frames = miro_get(f"/boards/{board_id}/frames")
# {"total": N, "data": [{"id": "...", "title": "Frame name", ...}, ...]}
for f in frames["data"]:
    print(f["id"], f["title"])
```

---

## ⚠ Critical: `GET /boards/{id}/widgets/` does NOT return content

The widgets list endpoint returns only `id`, `updatedAt`, `createdAt` — no text, no type, no position. Filtering by `?widgetType=X` is silently ignored.

**The correct endpoint for board content is `/content`:**

```python
board_id = urllib.parse.quote(env["MIRO_BOARD_ID"], safe="")
r = miro_get(f"/boards/{board_id}/content")
widgets = r["content"]["widgets"]  # list of all widget objects
```

---

## Widget schema from `/content`

Each widget:
```json
{
  "id": "...",
  "canvasedObjectData": {
    "type": "shape",
    "json": "(nested JSON string — must be parsed separately)"
  },
  "objectHistoryData": { "creationTime": "...", "lastChangeTime": "..." }
}
```

Widget types: `shape`, `sticker`, `frame`, `line`, `image`

Parsing the inner JSON:
```python
def strip_html(text):
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()

for w in widgets:
    cod = w["canvasedObjectData"]
    raw = cod.get("json", "")
    if not raw:
        continue
    data = json.loads(raw)

    text = strip_html(data.get("text", ""))  # HTML — use strip_html()
    pos = data.get("_position", {}).get("offsetPx", {})
    x, y = pos.get("x", 0), pos.get("y", 0)
    parent = data.get("_parent")  # None or {"id": "frame_id"}
    size = data.get("size")       # {"width": ..., "height": ...}
```

---

## Mapping widgets to frames

Frame membership comes from `_parent` in the inner JSON — **not** from position overlap.

```python
# Step 1: build titled frame lookup (titles are in /frames, not in /content)
titled = {f["id"]: f["title"]
          for f in miro_get(f"/boards/{board_id}/frames")["data"]}

# Step 2: group widgets by frame
frame_contents = {}
for w in widgets:
    cod = w["canvasedObjectData"]
    if cod["type"] not in ("shape", "sticker"):
        continue
    raw = cod.get("json", "")
    if not raw:
        continue
    data = json.loads(raw)
    text = strip_html(data.get("text", ""))
    if not text:
        continue
    parent = data.get("_parent")
    parent_id = parent["id"] if isinstance(parent, dict) else parent
    frame_name = titled.get(str(parent_id), "Main canvas") if parent_id else "Main canvas"
    pos = data.get("_position", {}).get("offsetPx", {})
    frame_contents.setdefault(frame_name, []).append({
        "type": cod["type"], "text": text,
        "x": pos.get("x", 0), "y": pos.get("y", 0),
    })

# Step 3: print sorted by position (y then x = top-to-bottom, left-to-right)
for frame_name, items in frame_contents.items():
    print(f"\n=== {frame_name} ===")
    for item in sorted(items, key=lambda i: (i["y"], i["x"])):
        print(f"  [{item['type']}] {item['text']}")
```

---

## Board IDs

Miro board IDs in URLs are base64 strings (e.g. `aBcDeFgHiJk=`). URL-encode the `=` when using in API paths:

```python
board_id = urllib.parse.quote(env["MIRO_BOARD_ID"], safe="")
# "aBcDeFgHiJk=" → "aBcDeFgHiJk%3D"
```

---

## Confirmed 404 / non-functional endpoints

```
GET /boards/{id}/widgets/{widget_id}   ← individual widget by ID returns 404
GET /boards/{id}/items                 ← 404
GET /boards/{id}/cards, /texts, /shapes, /stickynotes  ← all 404
GET /boards/{id}/export, /data         ← 404
GET /boards/{id}/widgets/?widgetType=X ← filter silently ignored; stubs only
api.miro.com/v2/ with session token    ← 401 (requires OAuth Bearer)
miro.com/api/v2/                       ← 404
```

---

## Common errors and fixes

| Error | Cause | Fix |
|---|---|---|
| `401` | Session token expired | Re-run SSO script to refresh `MIRO_TOKEN` |
| `403` on board | No view access to that board | User must grant access in Miro |
| Widget content empty | Using `/widgets/` instead of `/content` | Switch to `/boards/{id}/content` |
| Frame title `None` in content | Titles not in content endpoint JSON | Cross-reference with `/boards/{id}/frames` |
| Widget text is raw HTML | `text` field contains `<p>`, `<mark>` etc. | Apply `strip_html()` helper |

---

## ⚠ REST write API is CSRF-blocked — use window.miro.board SDK instead

### Why REST writes don't work

`POST /boards/{id}/shapes/` and related endpoints return `403 wrongCsrfToken` unconditionally. The CSRF token obtained from `POST /api/v1/csrf` is **not accepted** for board mutations, even when:
- Passed as `X-MR-CSRF-Token` header with a freshly generated token
- All session cookies are included
- The request originates from within a Playwright browser page context

Board mutations use Miro's internal WebSocket protocol — the REST endpoints exist but are not usable without a valid internal CSRF secret tied to the browser session.

**Do NOT attempt these write approaches:**
```
POST /boards/{id}/widgets/     → 405 Method Not Allowed
POST /boards/{id}/shapes/      → 403 wrongCsrfToken
POST /boards/{id}/objects/     → 403 wrongCsrfToken
POST /boards/{id}/stickynotes/ → 403 wrongCsrfToken
```

---

## ✅ Correct write path: window.miro.board SDK via Playwright (headless OK)

After a board loads in Playwright (with the `token` cookie injected), `window.miro.board` exposes the full Miro Plugin SDK. Call it via `page.evaluate()`. No REST auth issues.

**Use the CLI wrapper** — do not hand-roll Playwright unless you need something the CLI doesn't cover:

```bash
source .venv/bin/activate
python3 tool_connections/miro/cli.py audit-board --board "BOARD_ID=" --margin 3500
python3 tool_connections/miro/cli.py create-items --board "BOARD_ID=" --file items.json
python3 tool_connections/miro/cli.py delete-region --board "BOARD_ID=" --x-min 4500 --dry-run
```

- **Default: headless** — no browser window. Add `--headed` to debug.
- **SDK warmup: ~14s** after `domcontentloaded` before `window.miro.board` is ready.
- **Chromium required:** `python3 -m playwright install chromium`
- **SSO is separate** — `sso.py` always uses a headed browser for Okta; do not change that for writes.

### Headless setup (verified 2026-06)

```python
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(
        ignore_https_errors=True,
        viewport={"width": 1400, "height": 900},
    )
    ctx.add_cookies([{"name": "token", "value": TOKEN, "domain": ".miro.com",
                      "path": "/", "secure": True}])
    page = ctx.new_page()
    page.goto(f"https://miro.com/app/board/{BOARD_ID}/",
              wait_until="domcontentloaded", timeout=30000)
    time.sleep(14)

    sdk_ready = page.evaluate(
        "() => !!(window.miro && window.miro.board && window.miro.board.createShape)"
    )
    assert sdk_ready
```

### board.remove — requires id AND type

```javascript
// WRONG — ZodError: Expected string, received array
await miro.board.remove({ id: [id1, id2] });

// WRONG — ZodError: type is Required
await miro.board.remove({ id });

// RIGHT — one item at a time, children before frames
await miro.board.remove({ id: shapeId, type: 'shape' });
await miro.board.remove({ id: frameId, type: 'frame' });
```

Delete order used by `cli.py delete-region`: shape → text → sticky_note → connector → frame.

### parentId is read-only at create time

```javascript
// FAILS: "Cannot change this property, because it's read-only: parentId"
await miro.board.createShape({ ..., parentId: frameId });

// WORKS: absolute board coordinates (visually inside the frame)
await miro.board.createShape({ x: 5500, y: 1200, ... });
```

Frame membership can be adjusted manually in the UI after creation, or use absolute coords that align with frame bounds from `audit-board`.

### Audit board bounds before placing content

```bash
python3 tool_connections/miro/cli.py audit-board --board "BOARD_ID=" --margin 3500
# → occupiedBounds, workshopOriginCenter
```

Or run `audit_board.py` directly. Computes widget bounding box from `/content` and suggests a safe origin to the right of existing content.

### create-items JSON types

| type | SDK method | Notes |
|------|------------|-------|
| `frame` | `createFrame` | title, x, y, width, height |
| `shape` | `createShape` | content is HTML; absolute x,y |
| `text` | `createText` | absolute x,y |
| `sticky_note` | `createStickyNote` | plain text content |
| `connector` | `createConnector` | start/end with `{x,y}` or `{ref}` |

See `examples/minimal_items.json` for a working batch.

### Setup (manual Playwright — prefer cli.py)

```python
import json, time
from pathlib import Path
from playwright.sync_api import sync_playwright

env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--window-size=1400,900"])
    ctx = browser.new_context(ignore_https_errors=True)
    ctx.add_cookies([{"name": "token", "value": env["MIRO_TOKEN"], "domain": ".miro.com",
                      "path": "/", "secure": True}])
    page = ctx.new_page()
    page.goto(f"https://miro.com/app/board/{env['MIRO_BOARD_ID']}/",
              wait_until="domcontentloaded", timeout=30000)
    time.sleep(12)  # SDK needs ~12s after domcontentloaded

    sdk_ready = page.evaluate(
        "() => !!(window.miro && window.miro.board && window.miro.board.createShape)"
    )
    assert sdk_ready, "Miro SDK not ready — increase sleep or check token"
```

### createShape

```python
# ⚠ Pass all data as page.evaluate(js, data) argument — not f-string interpolation
# This handles HTML content in the 'content' field safely

shapes = [
    {"id": "MY_KEY", "x": 0, "y": 0, "color": "#d0e8f1",
     "content": "<p style='font-size:9px'>SCHEMA</p><p>TABLE_NAME</p>"}
]

result = page.evaluate("""
async (batch) => {
    const ids = {};
    for (const n of batch) {
        const shape = await window.miro.board.createShape({
            content: n.content,
            shape: 'rectangle',
            x: n.x, y: n.y,
            width: 320, height: 68,
            style: {
                fillColor: n.color,
                fillOpacity: 1,
                borderColor: '#888888',
                borderWidth: 2,       // ⚠ integer — 1.5 → ValidationError
                borderStyle: 'normal',
                color: '#1a1a1a',
                fontSize: 11,         // ⚠ integer
                textAlign: 'center',
                textAlignVertical: 'middle',
            }
        });
        ids[n.id] = shape.id;
    }
    return ids;
}
""", shapes)
# result = {"MY_KEY": "<miro-shape-id>", ...}
```

### createConnector

```python
# ⚠ Use start/end with item property — NOT startItem/endItem
# startItem/endItem → "Cannot set unrecognized properties" ValidationError

edges = [{"srcId": "<miro-id-1>", "dstId": "<miro-id-2>", "label": "my_transform.sql"}]

result = page.evaluate("""
async (batch) => {
    let created = 0, errors = [];
    for (const e of batch) {
        try {
            await window.miro.board.createConnector({
                start: { item: e.srcId, snapTo: 'auto' },
                end:   { item: e.dstId, snapTo: 'auto' },
                style: {
                    strokeColor: '#555555',
                    strokeWidth: 2,   // ⚠ integer
                    strokeStyle: 'normal',
                    endStrokeCap: 'filled_triangle',
                    startStrokeCap: 'none',
                },
                captions: [{ content: e.label, position: 0.5 }]
            });
            created++;
        } catch(err) { errors.push(err.message); }
    }
    return { created, errors };
}
""", edges)
```

### Re-read shapes back (to reconnect in a follow-up session)

```python
import re

def extract_two_part_id(content):
    """Parse SCHEMA.TABLE from <p>SCHEMA</p><p>TABLE</p> HTML."""
    parts = re.findall(r"<p[^>]*>(.*?)</p>", content, re.DOTALL)
    parts = [re.sub(r"<[^>]+>", "", p).strip() for p in parts if p.strip()]
    return f"{parts[0]}.{parts[1]}" if len(parts) >= 2 else re.sub(r"<[^>]+>", "", content).strip()

shapes = page.evaluate("""
async () => {
    const items = await window.miro.board.get({ type: 'shape' });
    return items.map(s => ({ miroId: s.id, content: s.content }));
}
""")
shape_map = {extract_two_part_id(s["content"]): s["miroId"] for s in shapes}
```

### Available SDK methods

```
createShape, createConnector, createFrame, createStickyNote, createText,
createCard, createAppCard, createEmbed, createImage, get, getById,
getSelection, select, deselect, remove, bringToFront, sendToBack,
viewport, ui, notifications, storage, events, getUserInfo, getInfo
```

---

## Validation gotchas summary

| Field | Wrong | Right |
|---|---|---|
| `borderWidth` | `1.5` (float) | `2` (int) |
| `strokeWidth` | `1.5` (float) | `2` (int) |
| `fontSize` | `11.0` (float) | `11` (int) |
| Connector endpoints | `startItem: {id}` | `start: {item: id}` |
| Data passing | f-string interpolation | `page.evaluate(js, data)` arg |
| `parentId` on create | `createShape({ parentId })` | absolute x,y at create time |
| `board.remove` | `{ id: [...] }` or `{ id }` only | `{ id, type }` one at a time |
| Playwright browser | always headed | headless works for SDK writes |
