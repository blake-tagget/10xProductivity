#!/usr/bin/env python3
"""
miro CLI — token-safe wrapper for Miro read/write operations.

Token is loaded from .env inside this script — it never appears as an argument
or in stdout, so it does not end up in chat logs.

Usage:
  python3 personal/miro/cli.py list-boards
  python3 personal/miro/cli.py get-frames --board "uXjVG2SvynI="
  python3 personal/miro/cli.py create-items --board "uXjVG2SvynI=" --file items.json
  cat items.json | python3 personal/miro/cli.py create-items --board "uXjVG2SvynI="

create-items JSON schema (array of items, processed top-to-bottom):

  Frame:
    {"type":"frame", "ref":"my-frame", "title":"Title", "x":0, "y":0,
     "width":1360, "height":1110, "style":{"fillColor":"#ffffff"}}

  Shape:
    {"type":"shape", "ref":"box1", "parentRef":"my-frame",
     "x":100, "y":100, "width":300, "height":60,
     "content":"<p><strong>Title</strong></p><p>Sub</p>",
     "style":{"fillColor":"#9FE1CB","fillOpacity":1,"borderColor":"#0F6E56",
               "borderWidth":1,"borderStyle":"normal","color":"#04342C",
               "fontSize":14,"textAlign":"left","textAlignVertical":"middle"}}

  Text:
    {"type":"text", "parentRef":"my-frame",
     "x":680, "y":200, "width":300,
     "content":"<p>Centered caption</p>",
     "style":{"fontSize":11,"color":"#A32D2D","textAlign":"center"}}

  Connector (e.g. separator line — floating, not attached to shapes):
    {"type":"connector",
     "start":{"x":680,"y":80}, "end":{"x":680,"y":900},
     "style":{"strokeColor":"#888888","strokeWidth":1,
               "strokeStyle":"dashed","strokeOpacity":0.35}}

Notes:
- x, y are CENTER coordinates (Miro SDK convention).
- "ref" and "parentRef" are logical names used only within this batch.
- parentRef places the item inside a previously created frame.
- All output is JSON on stdout; errors go to stderr with exit code 1.
"""

import argparse
import json
import sys
import ssl
import time
import urllib.parse
import urllib.request
from pathlib import Path

# ── Load .env from repo root (two levels up from this script) ─────────────────
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_PATH = _REPO_ROOT / ".env"

def _load_env():
    if not _ENV_PATH.exists():
        sys.exit(f"ERROR: .env not found at {_ENV_PATH}")
    return {
        k.strip(): v.strip()
        for line in _ENV_PATH.read_text().splitlines()
        if "=" in line and not line.startswith("#")
        for k, v in [line.split("=", 1)]
    }

# ── Read helpers (urllib, token in cookie — never in stdout) ──────────────────
_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE

def _miro_get(token, path):
    headers = {"Cookie": f"token={token}", "Accept": "application/json"}
    req = urllib.request.Request(f"https://miro.com/api/v1{path}", headers=headers)
    try:
        resp = urllib.request.urlopen(req, context=_CTX, timeout=20)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:500]
        if e.code == 401:
            sys.exit("ERROR: 401 Unauthorized — MIRO_TOKEN expired. Run: python3 personal/miro/sso.py --force")
        sys.exit(f"ERROR: HTTP {e.code} — {body}")

# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_list_boards(args):
    env = _load_env()
    token = env["MIRO_TOKEN"]
    boards = _miro_get(token, "/recent-boards")
    out = [{"id": b["id"], "title": b.get("title", "")} for b in boards]
    print(json.dumps(out, indent=2))


def cmd_get_frames(args):
    env = _load_env()
    token = env["MIRO_TOKEN"]
    board_id = urllib.parse.quote(args.board, safe="")
    result = _miro_get(token, f"/boards/{board_id}/frames")
    frames = result.get("data", result) if isinstance(result, dict) else result
    out = [{"id": f["id"], "title": f.get("title", "")} for f in frames]
    print(json.dumps(out, indent=2))


def cmd_create_items(args):
    # Read item list
    if args.file:
        items = json.loads(Path(args.file).read_text())
    else:
        items = json.loads(sys.stdin.read())

    if not isinstance(items, list):
        sys.exit("ERROR: create-items JSON must be an array of item objects")

    env = _load_env()
    token = env["MIRO_TOKEN"]
    board_id = args.board

    _run_playwright_create(token, board_id, items)


def _run_playwright_create(token, board_id, items):
    from playwright.sync_api import sync_playwright

    encoded_id = urllib.parse.quote(board_id, safe="")
    board_url = f"https://miro.com/app/board/{encoded_id}/"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--window-size=1400,900"])
        ctx = browser.new_context(ignore_https_errors=True)
        ctx.add_cookies([{
            "name": "token", "value": token,
            "domain": ".miro.com", "path": "/", "secure": True,
        }])
        page = ctx.new_page()

        print(f"Opening board...", file=sys.stderr)
        page.goto(board_url, wait_until="domcontentloaded", timeout=30000)

        print("Waiting for Miro SDK (~14s)...", file=sys.stderr)
        time.sleep(14)

        sdk_ready = page.evaluate(
            "() => !!(window.miro && window.miro.board && window.miro.board.createShape)"
        )
        if not sdk_ready:
            sys.exit("ERROR: Miro SDK not ready after 14s — try again or check the board URL")

        print(f"SDK ready. Creating {len(items)} items...", file=sys.stderr)

        result = page.evaluate(_CREATE_JS, items)

        time.sleep(2)
        browser.close()

    print(json.dumps(result, indent=2))


# JavaScript that runs inside the Miro board page.
# Receives the items array, returns {created, errors, refs} where refs maps
# logical ref names to actual Miro item IDs.
_CREATE_JS = """
async (items) => {
    const refs = {};   // logical ref → miro ID
    const created = [];
    const errors = [];

    function resolveParent(parentRef) {
        if (!parentRef) return undefined;
        const id = refs[parentRef];
        if (!id) {
            errors.push(`Unknown parentRef: ${parentRef}`);
            return undefined;
        }
        return id;
    }

    for (const item of items) {
        try {
            let obj;
            const style = item.style || {};

            if (item.type === 'frame') {
                obj = await window.miro.board.createFrame({
                    title:  item.title || '',
                    x:      item.x,
                    y:      item.y,
                    width:  item.width,
                    height: item.height,
                    style:  { fillColor: style.fillColor || '#ffffff' },
                });

            } else if (item.type === 'shape') {
                const parentId = resolveParent(item.parentRef);
                const params = {
                    content: item.content || '',
                    shape:   item.shape || 'rectangle',
                    x:       item.x,
                    y:       item.y,
                    width:   item.width,
                    height:  item.height,
                    style: {
                        fillColor:         style.fillColor         || '#ffffff',
                        fillOpacity:       style.fillOpacity       != null ? style.fillOpacity : 1,
                        borderColor:       style.borderColor       || '#000000',
                        borderWidth:       style.borderWidth       != null ? Math.round(style.borderWidth) : 1,
                        borderStyle:       style.borderStyle       || 'normal',
                        borderOpacity:     style.borderOpacity     != null ? style.borderOpacity : 1,
                        color:             style.color             || '#000000',
                        fontSize:          style.fontSize          != null ? Math.round(style.fontSize) : 14,
                        textAlign:         style.textAlign         || 'left',
                        textAlignVertical: style.textAlignVertical || 'middle',
                    },
                };
                if (parentId) params.parentId = parentId;
                obj = await window.miro.board.createShape(params);

            } else if (item.type === 'text') {
                const parentId = resolveParent(item.parentRef);
                const params = {
                    content: item.content || '',
                    x:       item.x,
                    y:       item.y,
                    width:   item.width || 200,
                    style: {
                        color:     style.color     || '#000000',
                        fontSize:  style.fontSize  != null ? Math.round(style.fontSize) : 14,
                        textAlign: style.textAlign || 'left',
                        fillColor: style.fillColor || 'transparent',
                    },
                };
                if (parentId) params.parentId = parentId;
                obj = await window.miro.board.createText(params);

            } else if (item.type === 'connector') {
                const s = item.start || {};
                const e = item.end   || {};
                const startParam = s.ref ? { item: refs[s.ref], snapTo: 'auto' }
                                         : { position: { x: s.x, y: s.y } };
                const endParam   = e.ref ? { item: refs[e.ref], snapTo: 'auto' }
                                         : { position: { x: e.x, y: e.y } };
                obj = await window.miro.board.createConnector({
                    start: startParam,
                    end:   endParam,
                    style: {
                        strokeColor:    style.strokeColor || '#888888',
                        strokeWidth:    style.strokeWidth != null ? Math.round(style.strokeWidth) : 1,
                        strokeStyle:    style.strokeStyle || 'dashed',
                        startStrokeCap: 'none',
                        endStrokeCap:   'none',
                    },
                });

            } else {
                errors.push(`Unknown item type: ${item.type}`);
                continue;
            }

            if (item.ref) refs[item.ref] = obj.id;
            created.push({ type: item.type, ref: item.ref || null, miroId: obj.id });

        } catch (err) {
            errors.push({ type: item.type, ref: item.ref || null, error: err.message });
        }
    }

    return { created: created.length, errors, refs };
}
"""

# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Miro CLI — token-safe wrapper. Token loaded from .env, never echoed."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list-boards", help="List recently viewed boards")

    p_frames = sub.add_parser("get-frames", help="List frames on a board")
    p_frames.add_argument("--board", required=True, help="Board ID (e.g. 'uXjVG2SvynI=')")

    p_create = sub.add_parser("create-items", help="Batch-create items from JSON")
    p_create.add_argument("--board", required=True, help="Board ID")
    p_create.add_argument("--file", help="Path to JSON file (default: stdin)")

    args = parser.parse_args()

    if args.command == "list-boards":
        cmd_list_boards(args)
    elif args.command == "get-frames":
        cmd_get_frames(args)
    elif args.command == "create-items":
        cmd_create_items(args)


if __name__ == "__main__":
    main()
