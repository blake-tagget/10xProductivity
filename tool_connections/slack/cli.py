#!/usr/bin/env python3
"""
slack CLI — token-safe wrapper for Workday Slack.

Credentials (SLACK_XOXC, SLACK_D_COOKIE) are loaded from .env inside this
script and never appear as arguments or in stdout.

Usage:
  python3 personal/slack/cli.py search --query "pipeline DAG" [--channel C01ABC] [--after 2026-05-01] [--limit 20]
  python3 personal/slack/cli.py ask --question "What did Jane Smith say about the roadmap today?"
  python3 personal/slack/cli.py read-channel --channel D01UUDMH3M3 [--limit 50] [--hours 24]
  python3 personal/slack/cli.py parse-url --url "https://workday.enterprise.slack.com/archives/C01ABC/p1234567890"

Enterprise-restricted (do not use): conversations.list, users.list, users.lookupByEmail
People lookup: use `ask` with Slack AI — it resolves real names and searches for you.

All output is JSON on stdout; errors go to stderr with exit code 1.
"""

import argparse
import json
import re
import sys
import ssl
import time
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

def _api(xoxc, d_cookie, method, endpoint, data=None, params=None):
    url = f"https://slack.com/api/{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode() if data else None,
        headers={
            "Authorization": f"Bearer {xoxc}",
            "Cookie": f"d={d_cookie}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, context=_CTX, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:500]
        sys.exit(f"ERROR: HTTP {e.code} from {endpoint} — {body}")

def _check_token(r, endpoint):
    if not r.get("ok"):
        err = r.get("error", "unknown")
        if err in ("invalid_auth", "not_authed", "token_revoked"):
            sys.exit(
                f"ERROR: Slack token expired ({err}). "
                "Run: cd ~/code/10xProductivity && source .venv/bin/activate && "
                "python3 tool_connections/shared_utils/playwright_sso.py --slack-only"
            )
        sys.exit(f"ERROR: {endpoint} returned ok=false — {err}")

# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_search(args):
    env = _load_env()
    xoxc, d = env["SLACK_XOXC"], env["SLACK_D_COOKIE"]

    query = args.query
    if args.channel:
        query += f" in:{args.channel}"
    if args.after:
        query += f" after:{args.after}"

    r = _api(xoxc, d, "GET", "search.messages", params={
        "query": query,
        "count": str(args.limit),
        "sort": "timestamp",
    })
    _check_token(r, "search.messages")

    matches = r.get("messages", {}).get("matches", [])
    out = [
        {
            "channel": m.get("channel", {}).get("name"),
            "channel_id": m.get("channel", {}).get("id"),
            "user": m.get("username", m.get("user")),
            "ts": m.get("ts"),
            "text": m.get("text", "")[:500],
            "permalink": m.get("permalink"),
        }
        for m in matches
    ]
    print(json.dumps(out, indent=2))


def cmd_ask(args):
    """Post a question to Slackbot DM and wait for Slack AI response."""
    env = _load_env()
    xoxc, d = env["SLACK_XOXC"], env["SLACK_D_COOKIE"]

    # Open Slackbot DM
    r = _api(xoxc, d, "POST", "conversations.open", {"users": "USLACKBOT"})
    _check_token(r, "conversations.open")
    slackbot_dm = r["channel"]["id"]

    # Post question
    r = _api(xoxc, d, "POST", "chat.postMessage", {
        "channel": slackbot_dm,
        "text": args.question,
    })
    _check_token(r, "chat.postMessage")
    msg_ts = r["ts"]
    print(f"Question posted (ts={msg_ts}). Waiting for Slack AI...", file=sys.stderr)

    # Poll for AI response (up to 60s)
    ai_reply = None
    for i in range(30):
        time.sleep(2)
        r = _api(xoxc, d, "GET", "conversations.replies", params={
            "channel": slackbot_dm,
            "ts": msg_ts,
            "limit": "20",
        })
        _check_token(r, "conversations.replies")
        ai_replies = [
            m for m in r.get("messages", [])
            if float(m.get("ts", "0")) > float(msg_ts)
            and m.get("subtype") == "ai"
            and m.get("text", "") not in ("_Thinking..._", "")
        ]
        if ai_replies:
            ai_reply = ai_replies[-1]
            break
        if i % 5 == 4:
            print(f"Still waiting ({(i+1)*2}s)...", file=sys.stderr)

    if not ai_reply:
        sys.exit("ERROR: Slack AI did not respond within 60s")

    print(json.dumps({
        "question": args.question,
        "answer": ai_reply.get("text", ""),
        "ts": ai_reply.get("ts"),
        "channel_id": slackbot_dm,
    }, indent=2))


def cmd_read_channel(args):
    env = _load_env()
    xoxc, d = env["SLACK_XOXC"], env["SLACK_D_COOKIE"]

    oldest = str(time.time() - args.hours * 3600)
    r = _api(xoxc, d, "GET", "conversations.history", params={
        "channel": args.channel,
        "limit": str(args.limit),
        "oldest": oldest,
    })
    _check_token(r, "conversations.history")

    messages = list(reversed(r.get("messages", [])))
    out = [
        {
            "ts": m.get("ts"),
            "user": m.get("user", m.get("bot_id", "unknown")),
            "text": m.get("text", "")[:1000],
            "subtype": m.get("subtype"),
        }
        for m in messages
    ]
    print(json.dumps(out, indent=2))


def cmd_parse_url(args):
    m = re.search(r"/archives/([A-Z0-9]+)/p(\d+)", args.url)
    if not m:
        sys.exit(f"ERROR: Could not parse Slack URL: {args.url}")
    channel_id = m.group(1)
    raw_ts = m.group(2)
    ts = raw_ts[:10] + "." + raw_ts[10:]
    print(json.dumps({"channel_id": channel_id, "ts": ts}, indent=2))


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Slack CLI — token-safe wrapper. Credentials loaded from .env, never echoed."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_search = sub.add_parser("search", help="Search messages (keyword/date/channel)")
    p_search.add_argument("--query", required=True, help="Search query string")
    p_search.add_argument("--channel", help="Limit to channel name or ID (e.g. 'data-eng' or 'C01ABC')")
    p_search.add_argument("--after", help="Only messages after date (YYYY-MM-DD)")
    p_search.add_argument("--limit", type=int, default=20, help="Max results (default 20)")

    p_ask = sub.add_parser("ask", help="Ask Slack AI a natural-language question via Slackbot")
    p_ask.add_argument("--question", required=True, help="Natural language question for Slack AI")

    p_read = sub.add_parser("read-channel", help="Read recent messages from a channel or DM by ID")
    p_read.add_argument("--channel", required=True, help="Channel ID (e.g. D01UUDMH3M3)")
    p_read.add_argument("--limit", type=int, default=50, help="Max messages (default 50)")
    p_read.add_argument("--hours", type=float, default=24, help="How many hours back (default 24)")

    p_url = sub.add_parser("parse-url", help="Parse a Slack message URL into channel ID + timestamp")
    p_url.add_argument("--url", required=True, help="Full Slack message URL")

    args = parser.parse_args()

    if args.command == "search":
        cmd_search(args)
    elif args.command == "ask":
        cmd_ask(args)
    elif args.command == "read-channel":
        cmd_read_channel(args)
    elif args.command == "parse-url":
        cmd_parse_url(args)


if __name__ == "__main__":
    main()
