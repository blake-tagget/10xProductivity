#!/usr/bin/env python3
"""
miro CLI — token-safe wrapper for Miro read/write operations.

Token is loaded from .env inside this script — it never appears as an argument
or in stdout, so it does not end up in chat logs.

Reads use the internal REST API (miro.com/api/v1). Writes and deletes use the
Miro board SDK via Playwright — headless by default (~14s SDK warmup).

Usage (from repo root, with .venv activated):
  python3 tool_connections/miro/cli.py list-boards
  python3 tool_connections/miro/cli.py get-frames --board "BOARD_ID="
  python3 tool_connections/miro/cli.py audit-board --board "BOARD_ID=" --margin 3500
  python3 tool_connections/miro/cli.py create-items --board "BOARD_ID=" --file items.json
  python3 tool_connections/miro/cli.py delete-region --board "BOARD_ID=" --x-min 4500 --dry-run

Auth refresh (opens headed browser — SSO only):
  python3 tool_connections/miro/sso.py --force

create-items JSON schema (array of items, processed top-to-bottom):

  Frame:
    {"type":"frame", "ref":"my-frame", "title":"Title", "x":0, "y":0,
     "width":1360, "height":1110, "style":{"fillColor":"#ffffff"}}

  Shape / text / sticky_note — use absolute board x,y (see api-patterns.md):
    {"type":"shape", "x":100, "y":100, "width":300, "height":60,
     "content":"<p><strong>Title</strong></p>",
     "style":{"fillColor":"#9FE1CB","borderColor":"#0F6E56","fontSize":14}}

  Connector:
    {"type":"connector",
     "start":{"x":680,"y":80}, "end":{"x":680,"y":900},
     "style":{"strokeColor":"#888888","strokeWidth":1,"strokeStyle":"dashed"}}

Gotchas (verified 2026-06):
- x, y are CENTER coordinates (Miro SDK convention).
- parentId is read-only at create time — use absolute x,y coordinates only.
  See examples/minimal_items.json and api-patterns.md.
- board.remove requires { id, type } per item — not an array of ids.
- borderWidth, strokeWidth, fontSize must be integers (not floats).
- Playwright chromium must be installed: python3 -m playwright install chromium
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
            sys.exit(
                "ERROR: 401 Unauthorized — MIRO_TOKEN expired. "
                "Run: python3 tool_connections/miro/sso.py --force"
            )
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
    if args.file:
        items = json.loads(Path(args.file).read_text())
    else:
        items = json.loads(sys.stdin.read())

    if not isinstance(items, list):
        sys.exit("ERROR: create-items JSON must be an array of item objects")

    env = _load_env()
    token = env["MIRO_TOKEN"]
    board_id = args.board
    headless = not args.headed

    def run(page):
        print(f"SDK ready. Creating {len(items)} items...", file=sys.stderr)
        return page.evaluate(_CREATE_JS, items)

    result = _run_playwright_board(token, board_id, headless, run)
    print(json.dumps(result, indent=2))


def cmd_audit_board(args):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from audit_board import audit_board as do_audit

    result = do_audit(args.board, args.margin)
    print(json.dumps(result, indent=2))


def cmd_delete_region(args):
    if not args.title_prefix and args.x_min is None and not args.content_match:
        sys.exit(
            "ERROR: specify at least one filter: --title-prefix, --x-min, or --content-match"
        )

    env = _load_env()
    token = env["MIRO_TOKEN"]
    headless = not args.headed
    payload = {
        "titlePrefix": args.title_prefix or "",
        "xMin": args.x_min,
        "contentMatch": args.content_match or "",
        "dryRun": args.dry_run,
    }

    def run(page):
        action = "Listing" if args.dry_run else "Deleting"
        print(
            f"SDK ready. {action} items (prefix={args.title_prefix!r}, x>={args.x_min})...",
            file=sys.stderr,
        )
        return page.evaluate(_DELETE_REGION_JS, payload)

    result = _run_playwright_board(token, args.board, headless, run)
    print(json.dumps(result, indent=2))


def _run_playwright_board(token, board_id, headless, fn):
    from playwright.sync_api import sync_playwright

    encoded_id = urllib.parse.quote(board_id, safe="")
    board_url = f"https://miro.com/app/board/{encoded_id}/"
    mode = "headless" if headless else "headed"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=["--window-size=1400,900"] if not headless else [],
        )
        ctx = browser.new_context(
            ignore_https_errors=True,
            viewport={"width": 1400, "height": 900},
        )
        ctx.add_cookies([{
            "name": "token", "value": token,
            "domain": ".miro.com", "path": "/", "secure": True,
        }])
        page = ctx.new_page()

        print(f"Opening board ({mode})...", file=sys.stderr)
        page.goto(board_url, wait_until="domcontentloaded", timeout=30000)

        print("Waiting for Miro SDK (~14s)...", file=sys.stderr)
        time.sleep(14)

        sdk_ready = page.evaluate(
            "() => !!(window.miro && window.miro.board && window.miro.board.createShape)"
        )
        if not sdk_ready:
            sys.exit("ERROR: Miro SDK not ready after 14s — try again or check the board URL")

        result = fn(page)
        time.sleep(1)
        browser.close()

    return result


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
                obj = await window.miro.board.createShape({
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
                });

            } else if (item.type === 'text') {
                obj = await window.miro.board.createText({
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
                });

            } else if (item.type === 'sticky_note') {
                obj = await window.miro.board.createStickyNote({
                    content: item.content || '',
                    x:       item.x,
                    y:       item.y,
                    style: {
                        fillColor: style.fillColor || '#fff9b1',
                        textAlign: style.textAlign || 'center',
                    },
                });

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

_DELETE_REGION_JS = """
async ({ titlePrefix, xMin, contentMatch, dryRun }) => {
    const ids = new Map();

    function note(type, id, reason) {
        if (!id || ids.has(id)) return;
        ids.set(id, { type, reason });
    }

    const frames = await window.miro.board.get({ type: 'frame' });
    for (const f of frames) {
        const title = f.title || '';
        if (titlePrefix && title.includes(titlePrefix)) {
            note('frame', f.id, title);
        }
    }

    for (const type of ['shape', 'text', 'sticky_note', 'connector']) {
        let items = [];
        try {
            items = await window.miro.board.get({ type });
        } catch (_) {
            continue;
        }
        for (const item of items) {
            const x = item.x;
            const content = item.content || item.plainText || '';
            if (xMin != null && typeof x === 'number' && x >= xMin) {
                note(type, item.id, `x=${Math.round(x)}`);
            } else if (contentMatch && content.includes(contentMatch)) {
                note(type, item.id, 'content-match');
            }
        }
    }

    const matched = [...ids.entries()].map(([id, v]) => ({ type: v.type, id, reason: v.reason }));
    const deleteOrder = ['shape', 'text', 'sticky_note', 'connector', 'frame'];
    const idList = [...ids.entries()].sort(
        (a, b) => deleteOrder.indexOf(a[1].type) - deleteOrder.indexOf(b[1].type)
    );
    let deleted = 0;
    const errors = [];
    if (!dryRun) {
        for (const [id, meta] of idList) {
            try {
                await window.miro.board.remove({ id, type: meta.type });
                deleted++;
            } catch (err) {
                errors.push({ id, type: meta.type, error: err.message });
            }
        }
    }

    return { dryRun: !!dryRun, deleted: dryRun ? 0 : deleted, matched, errors };
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

    p_audit = sub.add_parser(
        "audit-board",
        help="Report widget bounds and suggested empty-canvas origin (REST read)",
    )
    p_audit.add_argument("--board", required=True, help="Board ID")
    p_audit.add_argument(
        "--margin", type=float, default=3500,
        help="Gap (px) past occupiedBounds.xMax for suggestedOriginCenter",
    )

    p_create = sub.add_parser("create-items", help="Batch-create items from JSON")
    p_create.add_argument("--board", required=True, help="Board ID")
    p_create.add_argument("--file", help="Path to JSON file (default: stdin)")
    p_create.add_argument(
        "--headed", action="store_true",
        help="Show browser window (default: headless Playwright)",
    )

    p_delete = sub.add_parser(
        "delete-region",
        help="Delete frames/shapes in a board region (Playwright SDK)",
    )
    p_delete.add_argument("--board", required=True, help="Board ID")
    p_delete.add_argument(
        "--title-prefix", default="",
        help="Delete frames whose title contains this string",
    )
    p_delete.add_argument(
        "--x-min", type=float, default=None,
        help="Delete shapes/text/stickies with center x >= this value",
    )
    p_delete.add_argument(
        "--content-match", default="",
        help="Delete items whose content contains this string",
    )
    p_delete.add_argument(
        "--headed", action="store_true",
        help="Show browser window (default: headless Playwright)",
    )
    p_delete.add_argument(
        "--dry-run", action="store_true",
        help="List matching items without deleting",
    )

    args = parser.parse_args()

    if args.command == "list-boards":
        cmd_list_boards(args)
    elif args.command == "get-frames":
        cmd_get_frames(args)
    elif args.command == "audit-board":
        cmd_audit_board(args)
    elif args.command == "create-items":
        cmd_create_items(args)
    elif args.command == "delete-region":
        cmd_delete_region(args)


if __name__ == "__main__":
    main()
