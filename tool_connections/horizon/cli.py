#!/usr/bin/env python3
"""
Horizon CLI — token-safe wrapper for Workday Horizon (LumApps intranet).

Credentials are loaded from .env inside this script and never appear as
arguments or in stdout.

Usage:
  python3 personal/horizon/cli.py check
  python3 personal/horizon/cli.py get-content --id 5759492855152208
  python3 personal/horizon/cli.py search --query "RBAC" [--limit 10]
  python3 personal/horizon/cli.py list-navigation
  python3 personal/horizon/cli.py list-saved

All output is JSON on stdout; errors go to stderr with exit code 1.

Token renewal (LumApps tokens expire after ~1h):
  python3 personal/horizon/sso.py
"""

import argparse
import json
import ssl
import sys
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_PATH = _REPO_ROOT / ".env"

ORG_ID_FALLBACK = "5368347508080640"
SITE_ID_FALLBACK = "5649930513285120"
API_BASE_FALLBACK = "https://go-cell-002.api.lumapps.com"


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


def _api(env, path, params=None):
    token = env.get("HORIZON_TOKEN", "")
    org_id = env.get("HORIZON_ORG_ID", ORG_ID_FALLBACK)
    api_base = env.get("HORIZON_API_BASE", API_BASE_FALLBACK)
    version = env.get("HORIZON_CLIENT_VERSION", "")

    if not token:
        sys.exit(
            "ERROR: HORIZON_TOKEN not set in .env.\n"
            "Run: python3 personal/horizon/sso.py"
        )

    url = f"{api_base}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    headers = {
        "Authorization": f"Bearer {token}",
        "lumapps-organization-id": org_id,
        "lumapps-call-id": str(uuid.uuid4()),
        "Accept": "application/json",
        "Accept-Language": "en",
        "User-Agent": "Mozilla/5.0",
    }
    if version:
        headers["lumapps-web-client-version"] = version

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, context=_CTX, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        if e.code == 401:
            sys.exit(
                "ERROR: 401 Unauthorized — Horizon token expired.\n"
                "Run: python3 personal/horizon/sso.py"
            )
        sys.exit(f"ERROR: HTTP {e.code} from {path} — {body}")


def _str_or_lang(val, lang="en"):
    if not val:
        return ""
    if isinstance(val, dict):
        return val.get(lang, val.get("en", next(iter(val.values()), "")))
    return str(val)


def _api_post(env, path, body):
    token = env.get("HORIZON_TOKEN", "")
    org_id = env.get("HORIZON_ORG_ID", ORG_ID_FALLBACK)
    api_base = env.get("HORIZON_API_BASE", API_BASE_FALLBACK)
    version = env.get("HORIZON_CLIENT_VERSION", "")

    if not token:
        sys.exit("ERROR: HORIZON_TOKEN not set. Run: python3 personal/horizon/sso.py")

    url = f"{api_base}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "lumapps-organization-id": org_id,
        "lumapps-call-id": str(uuid.uuid4()),
        "Accept": "application/json",
        "Accept-Language": "en",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0",
    }
    if version:
        headers["lumapps-web-client-version"] = version

    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, context=_CTX, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_str = e.read().decode()[:300]
        if e.code == 401:
            sys.exit("ERROR: 401 Unauthorized — run: python3 personal/horizon/sso.py")
        sys.exit(f"ERROR: HTTP {e.code} from {path} — {body_str}")


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_check(args):
    env = _load_env()
    data = _api(env, "/_ah/api/lumsites/v1/notification/countUnread")
    org_id = env.get("HORIZON_ORG_ID", ORG_ID_FALLBACK)
    user_id = env.get("HORIZON_USER_ID", "")
    print(json.dumps({
        "status": "ok",
        "org_id": org_id,
        "user_id": user_id,
        "unread_notifications": data.get("unreadNotificationsCount"),
    }, indent=2))


def cmd_get_content(args):
    env = _load_env()
    org_id = env.get("HORIZON_ORG_ID", ORG_ID_FALLBACK)
    content_id = args.id

    meta = _api(env, f"/v2/organizations/{org_id}/contents/{content_id}/metadata")
    layout = _api(env, f"/v2/organizations/{org_id}/contents/{content_id}/layout")

    # Extract readable text from layout components
    def extract_text(obj, depth=0):
        if depth > 5 or not obj:
            return []
        texts = []
        if isinstance(obj, dict):
            for key in ("text", "title", "body", "content", "value", "label"):
                if isinstance(obj.get(key), str) and len(obj[key]) > 3:
                    texts.append(obj[key])
            for v in obj.values():
                texts.extend(extract_text(v, depth + 1))
        elif isinstance(obj, list):
            for item in obj:
                texts.extend(extract_text(item, depth + 1))
        return texts

    text_snippets = extract_text(layout)

    print(json.dumps({
        "id": content_id,
        "metadata": meta.get("metadata", []),
        "layout_component_count": len(layout.get("components", [])),
        "text_snippets": text_snippets[:20],
    }, indent=2))


def cmd_search(args):
    env = _load_env()
    org_id = env.get("HORIZON_ORG_ID", ORG_ID_FALLBACK)

    data = _api_post(env, "/_ah/api/lumsites/v1/omnisearch/search", {
        "query": args.query,
        "lang": "en",
        "maxResults": args.limit,
        "organizationId": org_id,
    })

    items = data.get("items", [])
    out = [
        {
            "id": item.get("id"),
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": _str_or_lang(item.get("snippet"), "en")[:300],
            "is_top_result": item.get("isTopResult", False),
        }
        for item in items
    ]
    print(json.dumps(out, indent=2))


def cmd_list_navigation(args):
    env = _load_env()
    org_id = env.get("HORIZON_ORG_ID", ORG_ID_FALLBACK)
    site_id = env.get("HORIZON_SITE_ID", SITE_ID_FALLBACK)

    data = _api(
        env,
        f"/v2/organizations/{org_id}/sites/{site_id}/map/navigations/main-navigation",
        params={"lang": "en"},
    )

    def flatten_nav(node, depth=0):
        if not node:
            return []
        items = []
        title = node.get("title", {})
        label = title.get("en", "") if isinstance(title, dict) else str(title)
        slug = node.get("slug", {})
        slug_str = slug.get("en", "") if isinstance(slug, dict) else str(slug)
        if label:
            items.append({
                "depth": depth,
                "label": label,
                "slug": slug_str,
                "page_id": node.get("pageId"),
                "type": node.get("pageType", node.get("type")),
            })
        for child in node.get("children", []):
            items.extend(flatten_nav(child, depth + 1))
        return items

    nav_items = flatten_nav(data)
    print(json.dumps(nav_items, indent=2))


def cmd_list_saved(args):
    env = _load_env()
    org_id = env.get("HORIZON_ORG_ID", ORG_ID_FALLBACK)
    user_id = env.get("HORIZON_USER_ID", "")
    if not user_id:
        sys.exit("ERROR: HORIZON_USER_ID not set — re-run: python3 personal/horizon/sso.py")

    data = _api(env, f"/v2/organizations/{org_id}/users/{user_id}/saved-items")
    items = data.get("items", [])
    out = [
        {
            "id": item.get("resourceId"),
            "type": item.get("resourceType"),
            "title": item.get("title", {}).get("en", item.get("title", "")),
        }
        for item in items
    ]
    print(json.dumps(out, indent=2))


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Horizon CLI — token-safe wrapper. Credentials from .env, never echoed."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check", help="Verify token and print org/user info")

    p_content = sub.add_parser("get-content", help="Get content metadata and text by ID")
    p_content.add_argument("--id", required=True, help="Content ID (numeric)")

    p_search = sub.add_parser("search", help="Search Horizon content")
    p_search.add_argument("--query", required=True, help="Search query")
    p_search.add_argument("--limit", type=int, default=10, help="Max results (default 10)")

    sub.add_parser("list-navigation", help="List main navigation tree")
    sub.add_parser("list-saved", help="List your saved items")

    args = parser.parse_args()
    {
        "check": cmd_check,
        "get-content": cmd_get_content,
        "search": cmd_search,
        "list-navigation": cmd_list_navigation,
        "list-saved": cmd_list_saved,
    }[args.command](args)


if __name__ == "__main__":
    main()
