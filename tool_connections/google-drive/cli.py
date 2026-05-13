#!/usr/bin/env python3
"""
Google Drive CLI — token-safe wrapper (Playwright storage_state, no .env credentials).

Auth file: ~/.browser_automation/gdrive_auth.json
Refresh:   source .venv/bin/activate && python3 tool_connections/shared_utils/playwright_sso.py --gdrive-only

Usage:
  python3 personal/google-drive/cli.py read --url "https://docs.google.com/document/d/DOC_ID/edit"
  python3 personal/google-drive/cli.py read --id DOC_ID --type document
  python3 personal/google-drive/cli.py search --query "Snowflake Tableau"
  python3 personal/google-drive/cli.py ls [--folder FOLDER_ID]

Output: plain text (read), or JSON (search/ls)
Errors: stderr, exit code 1
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Add paths for google_drive.py and its shared_utils dependency
_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))          # personal/google-drive/
sys.path.insert(0, str(_REPO / "tool_connections"))     # tool_connections/ (shared_utils lives here)

_ID_PATTERNS = [
    r"/document/d/([a-zA-Z0-9_-]{20,})",
    r"/spreadsheets/d/([a-zA-Z0-9_-]{20,})",
    r"/presentation/d/([a-zA-Z0-9_-]{20,})",
    r"/file/d/([a-zA-Z0-9_-]{20,})",
]
_TYPE_BY_PATH = {
    "/document/d/": "document",
    "/spreadsheets/d/": "spreadsheet",
    "/presentation/d/": "presentation",
}

def _parse_url(url: str) -> tuple[str, str]:
    """Extract (file_id, file_type) from a Google Drive URL."""
    for pat in _ID_PATTERNS:
        m = re.search(pat, url)
        if m:
            file_id = m.group(1)
            file_type = next((t for k, t in _TYPE_BY_PATH.items() if k in url), "document")
            return file_id, file_type
    sys.exit(f"ERROR: Could not extract file ID from URL: {url}")


def cmd_read(args):
    from google_drive import GDrive

    if args.url:
        file_id, file_type = _parse_url(args.url)
    elif args.id and args.type:
        file_id, file_type = args.id, args.type
    else:
        sys.exit("ERROR: provide --url or both --id and --type")

    try:
        with GDrive() as drive:
            content = drive.read(file_id, file_type)
        print(content)
    except RuntimeError as e:
        sys.exit(f"ERROR: {e}")


def cmd_search(args):
    from google_drive import GDrive

    try:
        with GDrive() as drive:
            results = drive.search(args.query)
        print(json.dumps(results, indent=2))
    except RuntimeError as e:
        sys.exit(f"ERROR: {e}")


def cmd_ls(args):
    from google_drive import GDrive

    try:
        with GDrive() as drive:
            results = drive.list_folder(args.folder) if args.folder else drive.list_my_drive()
        print(json.dumps(results, indent=2))
    except RuntimeError as e:
        sys.exit(f"ERROR: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Google Drive CLI — token-safe wrapper. Auth via ~/.browser_automation/gdrive_auth.json, never echoed."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_read = sub.add_parser("read", help="Export a Google Doc/Sheet/Slides as text/CSV")
    p_read.add_argument("--url", help="Full Google Drive URL (extracts ID + type automatically)")
    p_read.add_argument("--id", help="File ID (use with --type)")
    p_read.add_argument("--type", choices=["document", "spreadsheet", "presentation"],
                        help="File type (use with --id)")

    p_search = sub.add_parser("search", help="Search Google Drive")
    p_search.add_argument("--query", required=True,
                          help="Search query (supports Drive operators: owner:me, etc.)")

    p_ls = sub.add_parser("ls", help="List files in My Drive or a folder")
    p_ls.add_argument("--folder", help="Folder ID to list (default: My Drive root)")

    args = parser.parse_args()

    if args.command == "read":
        cmd_read(args)
    elif args.command == "search":
        cmd_search(args)
    elif args.command == "ls":
        cmd_ls(args)


if __name__ == "__main__":
    main()
