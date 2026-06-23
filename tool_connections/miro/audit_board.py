#!/usr/bin/env python3
"""Compute canvas bounds and a safe workshop zone for a Miro board.

Prefer the CLI wrapper:
  python3 tool_connections/miro/cli.py audit-board --board "BOARD_ID=" --margin 3500

Standalone:
  python3 tool_connections/miro/audit_board.py --board "BOARD_ID=" --margin 3500
"""

from __future__ import annotations

import argparse
import json
import ssl
import urllib.parse
import urllib.request
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_PATH = _REPO_ROOT / ".env"
_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE


def _load_env() -> dict[str, str]:
    if not _ENV_PATH.exists():
        raise SystemExit(f"ERROR: .env not found at {_ENV_PATH}")
    return {
        k.strip(): v.strip()
        for line in _ENV_PATH.read_text().splitlines()
        if "=" in line and not line.startswith("#")
        for k, v in [line.split("=", 1)]
    }


def _miro_get(token: str, path: str) -> dict:
    req = urllib.request.Request(
        f"https://miro.com/api/v1{path}",
        headers={"Cookie": f"token={token}", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, context=_CTX, timeout=30) as resp:
        return json.loads(resp.read())


def _rect_from_center(cx: float, cy: float, w: float, h: float) -> dict:
    return {"xMin": cx - w / 2, "xMax": cx + w / 2, "yMin": cy - h / 2, "yMax": cy + h / 2}


def _merge_bounds(items: list[dict]) -> dict | None:
    if not items:
        return None
    return {
        "xMin": min(i["xMin"] for i in items),
        "xMax": max(i["xMax"] for i in items),
        "yMin": min(i["yMin"] for i in items),
        "yMax": max(i["yMax"] for i in items),
    }


def audit_board(board_id: str, margin: float = 3000) -> dict:
    env = _load_env()
    token = env["MIRO_TOKEN"]
    encoded = urllib.parse.quote(board_id, safe="")

    board = _miro_get(token, f"/boards/{encoded}/")
    frames_raw = _miro_get(token, f"/boards/{encoded}/frames").get("data", [])
    content = _miro_get(token, f"/boards/{encoded}/content")
    widgets = content.get("content", {}).get("widgets", [])

    frame_rects = []
    for f in frames_raw:
        pos = f.get("position") or {}
        size = f.get("size") or {}
        cx, cy = pos.get("x"), pos.get("y")
        w, h = size.get("width"), size.get("height")
        if cx is None or cy is None or not w or not h:
            continue
        rect = _rect_from_center(cx, cy, w, h)
        frame_rects.append(
            {
                "title": f.get("title", ""),
                "center": {"x": cx, "y": cy},
                "size": {"width": w, "height": h},
                **rect,
            }
        )

    widget_rects = []
    for w in widgets:
        cod = w.get("canvasedObjectData", {})
        raw = cod.get("json", "")
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        pos = data.get("_position", {}).get("offsetPx", {})
        cx, cy = pos.get("x"), pos.get("y")
        if cx is None or cy is None:
            continue
        size = data.get("size") or {}
        width = size.get("width") or 200
        height = size.get("height") or 100
        widget_rects.append(_rect_from_center(cx, cy, width, height))

    occupied = _merge_bounds(frame_rects + widget_rects)
    if not occupied:
        origin = {"x": 4000, "y": 0}
    else:
        origin = {
            "x": occupied["xMax"] + margin,
            "y": occupied["yMin"],
        }

    return {
        "boardTitle": board.get("title", ""),
        "frameCount": len(frames_raw),
        "widgetCount": len(widgets),
        "frames": frame_rects,
        "occupiedBounds": occupied,
        "marginPx": margin,
        "workshopOriginCenter": origin,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit Miro board bounds for workshop placement.")
    parser.add_argument("--board", required=True, help="Board ID")
    parser.add_argument("--margin", type=float, default=3000, help="Gap from existing content (px)")
    args = parser.parse_args()
    print(json.dumps(audit_board(args.board, args.margin), indent=2))


if __name__ == "__main__":
    main()
