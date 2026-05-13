#!/usr/bin/env python3
"""
sana CLI — token-safe wrapper for Sana Agents.

Credentials (SANA_SESSION_COOKIE, SANA_WORKSPACE_ID) are loaded from .env
inside this script and never appear as arguments or in stdout.

Usage:
  python3 personal/sana/cli.py whoami
  python3 personal/sana/cli.py list-assistants
  python3 personal/sana/cli.py search --query "roadmap Q3 pricing" [--limit 20]
  python3 personal/sana/cli.py search-meetings --query "agent credit model discussion" [--limit 20]

Notes:
- Sana uses tRPC batch GET format — non-batch calls silently fail for most endpoints.
- Meeting transcripts can only be reconstructed from search fragments (no direct fetch API).
- Run multiple search queries with different phrasing to maximize transcript coverage.
- Refresh token (unknown TTL, refresh on 401):
    cd ~/code/10xProductivity && source .venv/bin/activate && python3 personal/sana/sso.py --force

All output is JSON on stdout; errors go to stderr with exit code 1.
"""

import argparse
import json
import re
import sys
import ssl
import urllib.parse
import urllib.request
from pathlib import Path

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

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE

def _headers(session_cookie, workspace_id):
    return {
        "Cookie": f"sana-ai-session={session_cookie}",
        "sana-ai-workspace-id": workspace_id,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

def _trpc_get(session_cookie, workspace_id, procedure):
    """Simple (non-batch) tRPC GET — works for user.me and assistantV2.list."""
    url = f"https://sana.ai/x-api/trpc/{procedure}"
    req = urllib.request.Request(url, headers=_headers(session_cookie, workspace_id))
    try:
        resp = urllib.request.urlopen(req, context=_CTX, timeout=20)
        r = json.loads(resp.read())
        if r is None:
            sys.exit(
                "ERROR: Sana returned null — session likely expired. "
                "Run: cd ~/code/10xProductivity && source .venv/bin/activate && "
                "python3 personal/sana/sso.py --force"
            )
        return r
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:500]
        if e.code == 401:
            sys.exit(
                "ERROR: 401 Unauthorized — Sana session expired. "
                "Run: cd ~/code/10xProductivity && source .venv/bin/activate && "
                "python3 personal/sana/sso.py --force"
            )
        sys.exit(f"ERROR: HTTP {e.code} from {procedure} — {body}")

def _trpc_batch_get(session_cookie, workspace_id, procedure, input_data):
    """Batch tRPC GET — required for most Sana endpoints (non-batch silently fails)."""
    encoded = urllib.parse.quote(json.dumps({"0": input_data}))
    url = f"https://sana.ai/x-api/trpc/{procedure}?batch=1&input={encoded}"
    req = urllib.request.Request(url, headers=_headers(session_cookie, workspace_id))
    try:
        resp = urllib.request.urlopen(req, context=_CTX, timeout=20)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:500]
        if e.code == 401:
            sys.exit(
                "ERROR: 401 Unauthorized — Sana session expired. "
                "Run: cd ~/code/10xProductivity && source .venv/bin/activate && "
                "python3 personal/sana/sso.py --force"
            )
        sys.exit(f"ERROR: HTTP {e.code} from {procedure} — {body}")

def _strip_mark(text):
    return re.sub(r"</?mark>", "", text or "")

# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_whoami(args):
    env = _load_env()
    r = _trpc_get(env["SANA_SESSION_COOKIE"], env["SANA_WORKSPACE_ID"], "user.me")
    user = r.get("result", {}).get("data", {}).get("user", {})
    print(json.dumps({
        "email": user.get("email"),
        "name": user.get("name"),
        "id": user.get("id"),
    }, indent=2))


def cmd_list_assistants(args):
    env = _load_env()
    r = _trpc_get(env["SANA_SESSION_COOKIE"], env["SANA_WORKSPACE_ID"], "assistantV2.list")
    assistants = r.get("result", {}).get("data", [])
    out = [
        {"id": a.get("id"), "name": a.get("name"), "description": a.get("description", "")[:200]}
        for a in assistants
    ]
    print(json.dumps(out, indent=2))


def cmd_search(args):
    env = _load_env()
    session, workspace = env["SANA_SESSION_COOKIE"], env["SANA_WORKSPACE_ID"]

    input_data = {"query": {"text": args.query, "webSearch": False, "sourceSearch": True}}
    r = _trpc_batch_get(session, workspace, "searchV2.search", input_data)

    if not isinstance(r, list) or "result" not in r[0]:
        sys.exit(f"ERROR: Unexpected response shape: {str(r)[:300]}")

    items = r[0]["result"]["data"]["root"]["children"]
    out = []
    for item in items[:args.limit]:
        fields = item.get("fields", {})
        out.append({
            "title": fields.get("title"),
            "source": fields.get("source"),
            "mimeType": fields.get("mimeType"),
            "assetId": fields.get("assetId"),
            "sequenceId": fields.get("sequenceId"),
            "snippet": _strip_mark(fields.get("snippet", ""))[:400],
            "createdAtEpochMs": fields.get("createdAtEpochMs"),
        })
    print(json.dumps(out, indent=2))


def cmd_search_meetings(args):
    env = _load_env()
    session, workspace = env["SANA_SESSION_COOKIE"], env["SANA_WORKSPACE_ID"]

    input_data = {"query": {"text": args.query, "webSearch": False, "sourceSearch": True}}
    r = _trpc_batch_get(session, workspace, "searchV2.search", input_data)

    if not isinstance(r, list) or "result" not in r[0]:
        sys.exit(f"ERROR: Unexpected response shape: {str(r)[:300]}")

    items = r[0]["result"]["data"]["root"]["children"]
    fragments = []
    for item in items:
        fields = item.get("fields", {})
        if fields.get("source") != "sana-ai:meeting":
            continue
        fragments.append({
            "title": fields.get("title"),
            "assetId": fields.get("assetId"),
            "sequenceId": fields.get("sequenceId"),
            "snippet": _strip_mark(fields.get("snippet", ""))[:400],
            "createdAtEpochMs": fields.get("createdAtEpochMs"),
        })

    fragments = sorted(fragments, key=lambda x: x.get("sequenceId") or 0)[:args.limit]
    print(json.dumps({
        "query": args.query,
        "fragment_count": len(fragments),
        "tip": "Run multiple queries with different phrasing to maximize transcript coverage. Deduplicate by (assetId, sequenceId).",
        "fragments": fragments,
    }, indent=2))


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Sana CLI — token-safe wrapper. Credentials loaded from .env, never echoed."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("whoami", help="Show current Sana user")

    sub.add_parser("list-assistants", help="List available Sana AI assistants")

    p_search = sub.add_parser("search", help="Full-text search across all Sana content")
    p_search.add_argument("--query", required=True, help="Search query")
    p_search.add_argument("--limit", type=int, default=20, help="Max results (default 20)")

    p_meetings = sub.add_parser("search-meetings", help="Search meeting transcripts only")
    p_meetings.add_argument("--query", required=True, help="Search query")
    p_meetings.add_argument("--limit", type=int, default=20, help="Max fragments (default 20)")

    args = parser.parse_args()

    if args.command == "whoami":
        cmd_whoami(args)
    elif args.command == "list-assistants":
        cmd_list_assistants(args)
    elif args.command == "search":
        cmd_search(args)
    elif args.command == "search-meetings":
        cmd_search_meetings(args)


if __name__ == "__main__":
    main()
