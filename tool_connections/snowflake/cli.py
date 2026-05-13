#!/usr/bin/env /usr/local/bin/python3.12
"""
Snowflake CLI — token-safe wrapper for Workday Snowflake.

Credentials are loaded from ~/.snowflake/config.toml inside this script and
never appear as arguments or in stdout.

Usage:
  python3 personal/snowflake/cli.py query --sql "SELECT CURRENT_USER()"
  python3 personal/snowflake/cli.py query --sql "SELECT * FROM t" --database CERTIFIED_PROD --schema COMMON --limit 100
  python3 personal/snowflake/cli.py list-databases
  python3 personal/snowflake/cli.py list-schemas --database CERTIFIED_PROD
  python3 personal/snowflake/cli.py list-tables --database CERTIFIED_PROD --schema COMMON
  python3 personal/snowflake/cli.py describe --database CERTIFIED_PROD --schema COMMON --table WD_ACCOUNT
  python3 personal/snowflake/cli.py check

All output is JSON on stdout; errors go to stderr with exit code 1.

Token renewal:
  Log in to https://app.us-west-2.privatelink.snowflakecomputing.com/ktazvpl/evb32354
  Profile → Programmatic Access Tokens → Generate new token
  Update password in ~/.snowflake/config.toml
"""

import argparse
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

_CONFIG_PATH = Path.home() / ".snowflake" / "config.toml"


def _load_config() -> dict:
    if not _CONFIG_PATH.exists():
        sys.exit(f"ERROR: Snowflake config not found at {_CONFIG_PATH}")
    result = {}
    in_default = False
    for line in _CONFIG_PATH.read_text().splitlines():
        line = line.strip()
        if line == "[connections.default]":
            in_default = True
            continue
        if line.startswith("[") and in_default:
            break
        if in_default and "=" in line:
            k, v = line.split("=", 1)
            result[k.strip()] = v.strip().strip('"')
    return result


def _connect(database=None, schema=None, warehouse=None):
    import snowflake.connector
    cfg = _load_config()
    pat = cfg.get("password", "")
    if not pat:
        sys.exit(
            "ERROR: No password/PAT found in ~/.snowflake/config.toml.\n"
            "Renew: Log in to Snowflake UI → Profile → Programmatic Access Tokens"
        )
    kwargs = dict(
        account=cfg["account"],
        user=cfg["user"],
        password=pat,
        authenticator=cfg.get("authenticator", "snowflake"),
        warehouse=warehouse or cfg.get("warehouse", ""),
        insecure_mode=True,
        login_timeout=20,
    )
    if cfg.get("role"):
        kwargs["role"] = cfg["role"]
    if database:
        kwargs["database"] = database
    if schema:
        kwargs["schema"] = schema
    try:
        return snowflake.connector.connect(**kwargs)
    except Exception as e:
        msg = str(e)
        if "authentication" in msg.lower() or "incorrect username" in msg.lower():
            sys.exit(
                f"ERROR: Snowflake auth failed — PAT may be expired.\n"
                f"Renew: Snowflake UI → Profile → Programmatic Access Tokens\n"
                f"Detail: {msg}"
            )
        sys.exit(f"ERROR: Could not connect to Snowflake — {msg}")


def _run_query(conn, sql, limit=None):
    cur = conn.cursor()
    try:
        cur.execute(sql)
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchmany(limit) if limit else cur.fetchall()
        return [dict(zip(cols, row)) for row in rows]
    finally:
        cur.close()


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_query(args):
    conn = _connect(
        database=args.database,
        schema=args.schema,
        warehouse=args.warehouse,
    )
    try:
        rows = _run_query(conn, args.sql, limit=args.limit)
    finally:
        conn.close()
    print(json.dumps(rows, indent=2, default=str))


def cmd_list_databases(args):
    conn = _connect()
    try:
        rows = _run_query(conn, "SHOW DATABASES")
    finally:
        conn.close()
    names = [r.get("name", r.get("NAME", "")) for r in rows]
    print(json.dumps(names, indent=2))


def cmd_list_schemas(args):
    conn = _connect(database=args.database)
    try:
        rows = _run_query(conn, f"SHOW SCHEMAS IN DATABASE {args.database}")
    finally:
        conn.close()
    names = [r.get("name", r.get("NAME", "")) for r in rows]
    print(json.dumps(names, indent=2))


def cmd_list_tables(args):
    conn = _connect(database=args.database, schema=args.schema)
    try:
        rows = _run_query(conn, f"SHOW TABLES IN {args.database}.{args.schema}")
    finally:
        conn.close()
    out = [
        {
            "name": r.get("name", r.get("NAME", "")),
            "kind": r.get("kind", r.get("KIND", "")),
            "rows": r.get("rows", r.get("ROWS", "")),
        }
        for r in rows
    ]
    print(json.dumps(out, indent=2))


def cmd_describe(args):
    conn = _connect(database=args.database, schema=args.schema)
    try:
        rows = _run_query(conn, f"DESCRIBE TABLE {args.database}.{args.schema}.{args.table}")
    finally:
        conn.close()
    out = [
        {
            "name": r.get("name", r.get("NAME", "")),
            "type": r.get("type", r.get("TYPE", "")),
            "nullable": r.get("null?", r.get("NULL?", "")),
        }
        for r in rows
    ]
    print(json.dumps(out, indent=2))


def cmd_check(_args):
    conn = _connect()
    try:
        rows = _run_query(conn, "SELECT CURRENT_USER() AS u, CURRENT_WAREHOUSE() AS wh, CURRENT_ROLE() AS role")
    finally:
        conn.close()
    cfg = _load_config()
    result = rows[0] if rows else {}
    result["account"] = cfg.get("account", "")
    print(json.dumps(result, indent=2))


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Snowflake CLI — token-safe wrapper. Credentials loaded from ~/.snowflake/config.toml, never echoed."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_query = sub.add_parser("query", help="Run a SQL query and return rows as JSON")
    p_query.add_argument("--sql", required=True, help="SQL to execute")
    p_query.add_argument("--database", help="Database context (e.g. CERTIFIED_PROD)")
    p_query.add_argument("--schema", help="Schema context (e.g. COMMON)")
    p_query.add_argument("--warehouse", help="Override warehouse (default: from config)")
    p_query.add_argument("--limit", type=int, default=1000, help="Max rows returned (default 1000)")

    p_dbs = sub.add_parser("list-databases", help="List all accessible databases")

    p_schemas = sub.add_parser("list-schemas", help="List schemas in a database")
    p_schemas.add_argument("--database", required=True, help="Database name")

    p_tables = sub.add_parser("list-tables", help="List tables in a schema")
    p_tables.add_argument("--database", required=True, help="Database name")
    p_tables.add_argument("--schema", required=True, help="Schema name")

    p_desc = sub.add_parser("describe", help="Describe columns of a table")
    p_desc.add_argument("--database", required=True, help="Database name")
    p_desc.add_argument("--schema", required=True, help="Schema name")
    p_desc.add_argument("--table", required=True, help="Table name")

    sub.add_parser("check", help="Verify connection and print current user/warehouse/role")

    args = parser.parse_args()
    {
        "query": cmd_query,
        "list-databases": cmd_list_databases,
        "list-schemas": cmd_list_schemas,
        "list-tables": cmd_list_tables,
        "describe": cmd_describe,
        "check": cmd_check,
    }[args.command](args)


if __name__ == "__main__":
    main()
