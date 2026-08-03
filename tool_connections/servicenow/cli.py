#!/usr/bin/env python3
"""
ServiceNow CLI — token-safe wrapper (Playwright storage_state, no .env credentials).

Auth file: ~/.browser_automation/servicenow_auth.json
Refresh:   python3 tool_connections/servicenow/sso.py

Usage:
  # See known catalog items and their fields
  python3 personal/servicenow/cli.py items

  # Search catalog (REST API)
  python3 personal/servicenow/cli.py search "snowflake"

  # Submit a single item (opens browser, fills form, submits)
  python3 personal/servicenow/cli.py submit snowflake \\
      --var select_env=Production \\
      --var role_type=Legacy \\
      --var role=ROLE_DATA_ANALYST \\
      --var business_justification="ED&A analyst toolset access"

  python3 personal/servicenow/cli.py submit sigma \\
      --var business_function="Enterprise Data & Analytics (ED&A)" \\
      --var pii_information=No \\
      --var business_justification="ED&A analyst toolset access"

  python3 personal/servicenow/cli.py submit atlan \\
      --var u_groups="Okta - Atlan - HT"

  # Bundle: submit all three at once
  python3 personal/servicenow/cli.py bundle snowflake sigma atlan \\
      --var snowflake:select_env=Production \\
      --var snowflake:role_type=Legacy \\
      --var snowflake:role=ROLE_DATA_ANALYST \\
      --var snowflake:business_justification="ED&A toolset access" \\
      --var sigma:business_function="Enterprise Data & Analytics (ED&A)" \\
      --var sigma:pii_information=No \\
      --var sigma:business_justification="ED&A toolset access" \\
      --var atlan:u_groups="Okta - Atlan - HT"

  # Same item multiple times (different roles): use positional prefix 0:, 1:
  python3 personal/servicenow/cli.py bundle snowflake snowflake \\
      --var 0:select_env=Production --var 0:role=ROLE_DATA_ANALYST \\
      --var 1:select_env=Production --var 1:role=ROLE_ANALYTICS_ENGINEER \\
      --var 0:business_justification="Primary role" \\
      --var 1:business_justification="Secondary role"

  # Dry run (fill form but don't click Submit)
  python3 personal/servicenow/cli.py bundle snowflake sigma atlan --dry-run ...

  # From JSON config
  python3 personal/servicenow/cli.py bundle --config bundle.json

  # Recent requests
  python3 personal/servicenow/cli.py requests

  # Refresh session
  python3 personal/servicenow/cli.py auth

Output: JSON to stdout. Progress to stderr. Exit code 1 on error.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "tool_connections" / "servicenow"))
sys.path.insert(0, str(_REPO / "tool_connections"))


def _sn():
    from servicenow import ServiceNow
    try:
        return ServiceNow()
    except RuntimeError as e:
        sys.exit(f"ERROR: {e}")


def _parse_vars(var_list: list[str], prefix: str | None = None) -> dict:
    result = {}
    for item in var_list or []:
        if "=" not in item:
            sys.exit(f"ERROR: --var must be key=value, got: {item!r}")
        k, v = item.split("=", 1)
        if prefix:
            if k.startswith(f"{prefix}:"):
                result[k[len(prefix) + 1:]] = v
        else:
            result[k] = v
    return result


# ------------------------------------------------------------------
# Commands
# ------------------------------------------------------------------

def cmd_items(_args):
    from submit import list_items
    print(json.dumps(list_items(), indent=2))


def cmd_search(args):
    sn = _sn()
    results = sn.search_catalog_items(args.query, limit=args.limit)
    if not results:
        print("[]")
        print(f"  No catalog items found for: {args.query!r}", file=sys.stderr)
        return
    print(json.dumps(results, indent=2))


def cmd_submit(args):
    from submit import submit_item, CATALOG_ITEMS
    item_key = args.item_key.lower()
    if item_key not in CATALOG_ITEMS:
        sys.exit(f"ERROR: Unknown item {item_key!r}. Known: {list(CATALOG_ITEMS)}")
    variables = _parse_vars(args.var)
    try:
        result = submit_item(item_key, variables, dry_run=args.dry_run)
        print(json.dumps(result, indent=2))
        _print_result_summary([result])
    except RuntimeError as e:
        sys.exit(f"ERROR: {e}")


def cmd_bundle(args):
    from submit import bundle_submit, CATALOG_ITEMS

    if getattr(args, "config", None):
        config_path = Path(args.config)
        if not config_path.exists():
            sys.exit(f"ERROR: config file not found: {config_path}")
        try:
            bundle = json.loads(config_path.read_text())
        except Exception as e:
            sys.exit(f"ERROR: could not parse config JSON: {e}")
    else:
        item_keys = [k.lower() for k in (args.item_keys or [])]
        if not item_keys:
            sys.exit("ERROR: provide item keys (snowflake, sigma, atlan) or --config FILE")

        has_duplicates = len(item_keys) != len(set(item_keys))
        bundle = []
        for i, item_key in enumerate(item_keys):
            if has_duplicates:
                variables = _parse_vars(args.var, prefix=str(i))
            else:
                variables = _parse_vars(args.var, prefix=item_key)
            bundle.append({"item": item_key, "variables": variables})

    try:
        results = bundle_submit(bundle, dry_run=getattr(args, "dry_run", False))
        print(json.dumps(results, indent=2))
        _print_result_summary(results)
    except RuntimeError as e:
        sys.exit(f"ERROR: {e}")


def cmd_requests(args):
    sn = _sn()
    try:
        results = sn.get_my_requests(limit=args.limit)
        print(json.dumps(results, indent=2))
    except RuntimeError as e:
        sys.exit(f"ERROR: {e}")


def cmd_auth(_args):
    sso_script = _REPO / "tool_connections" / "servicenow" / "sso.py"
    subprocess.run([sys.executable, str(sso_script)], check=False)


def _print_result_summary(results: list[dict]):
    print("\n--- Results ---", file=sys.stderr)
    for r in results:
        item = r.get("item", "?")
        if r.get("error"):
            print(f"  {item}: ERROR — {r['error']}", file=sys.stderr)
        elif r.get("dry_run"):
            print(f"  {item}: dry_run — not submitted", file=sys.stderr)
        else:
            ritm = r.get("ritm") or r.get("req") or "submitted"
            print(f"  {item}: {ritm}", file=sys.stderr)
            if r.get("url") and ("RITM" in r.get("url", "") or "sc_req" in r.get("url", "")):
                print(f"    {r['url']}", file=sys.stderr)


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="ServiceNow CLI — fills and submits ESC catalog forms via Playwright.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("items", help="List known catalog items and their field specs")

    p_search = sub.add_parser("search", help="Search the service catalog (REST API)")
    p_search.add_argument("query", help="Search keyword")
    p_search.add_argument("--limit", type=int, default=20)

    p_submit = sub.add_parser("submit", help="Submit a single catalog item (opens browser)")
    p_submit.add_argument("item_key", metavar="ITEM",
                          choices=["snowflake", "sigma", "atlan", "pharos_swh", "nimbus_sql_lab", "ghe", "bitbucket", "redshift", "tableau_user", "tableau_creator", "github_cloud", "bt_jira", "bt_confluence"],
                          help="Which item to submit")
    p_submit.add_argument("--var", action="append", metavar="field=value",
                          help="Field value (repeatable). See 'items' for field names.")
    p_submit.add_argument("--dry-run", action="store_true",
                          help="Fill form but don't click Submit")

    p_bundle = sub.add_parser(
        "bundle",
        help="Submit multiple items sequentially (one browser window per item)",
    )
    p_bundle.add_argument("item_keys", nargs="*", metavar="ITEM",
                          help="Items to submit: snowflake, sigma, atlan (repeatable, order matters)")
    p_bundle.add_argument(
        "--var", action="append", metavar="ITEM:field=value",
        help=(
            "Per-item field value (repeatable). "
            "Unique items: --var snowflake:role=ROLE_DATA_ANALYST. "
            "Duplicate items: use 0:, 1:, 2: positional prefix."
        ),
    )
    p_bundle.add_argument("--config", metavar="FILE",
                          help='JSON file: [{"item": "snowflake", "variables": {...}}, ...]')
    p_bundle.add_argument("--dry-run", action="store_true",
                          help="Fill forms but don't click Submit")

    p_req = sub.add_parser("requests", help="List recent service requests (REST API)")
    p_req.add_argument("--limit", type=int, default=10)

    sub.add_parser("auth", help="Refresh the ServiceNow session (runs sso.py)")

    args = parser.parse_args()

    dispatch = {
        "items":    cmd_items,
        "search":   cmd_search,
        "submit":   cmd_submit,
        "bundle":   cmd_bundle,
        "requests": cmd_requests,
        "auth":     cmd_auth,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
