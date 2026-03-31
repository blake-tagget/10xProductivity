#!/usr/bin/env python3
"""
Sync .claude/commands/*.md → .cursor/skills/{name}/SKILL.md

Claude Code uses flat .md files; Cursor uses a directory per skill with SKILL.md.
This script keeps them in sync, with .claude/commands/ as the source of truth.

Usage:
    python3 .claude/sync-skills.py
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
COMMANDS_DIR = REPO_ROOT / ".claude" / "commands"
SKILLS_DIR = REPO_ROOT / ".cursor" / "skills"
REPO_URL = "https://github.com/blake-tagget/10xProductivity"


def parse_frontmatter(text):
    """Return (frontmatter_dict, body) from a markdown file with --- fences."""
    match = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
    if not match:
        return {}, text
    fm_raw, body = match.group(1), match.group(2)
    fm = {}
    for line in fm_raw.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip()
    return fm, body.lstrip("\n")


def build_cursor_frontmatter(name, description):
    # Cursor frontmatter uses a block scalar for multi-line descriptions
    if "\n" in description or len(description) > 80:
        desc_block = "description: >\n  " + "\n  ".join(description.splitlines())
    else:
        desc_block = f"description: {description}"
    return f"---\nname: {name}\n{desc_block}\nsource: {REPO_URL}\n---"


def sync():
    if not COMMANDS_DIR.exists():
        print(f"ERROR: {COMMANDS_DIR} not found", file=sys.stderr)
        sys.exit(1)

    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    synced, skipped = [], []

    for cmd_file in sorted(COMMANDS_DIR.glob("*.md")):
        name = cmd_file.stem
        text = cmd_file.read_text()
        fm, body = parse_frontmatter(text)
        description = fm.get("description", f"{name} skill")

        skill_dir = SKILLS_DIR / name
        skill_dir.mkdir(exist_ok=True)
        skill_file = skill_dir / "SKILL.md"

        new_content = build_cursor_frontmatter(name, description) + "\n\n" + body

        if skill_file.exists() and skill_file.read_text() == new_content:
            skipped.append(name)
            continue

        skill_file.write_text(new_content)
        synced.append(name)

    # Remove skill dirs that no longer have a matching command
    command_names = {f.stem for f in COMMANDS_DIR.glob("*.md")}
    for skill_dir in SKILLS_DIR.iterdir():
        if skill_dir.is_dir() and skill_dir.name not in command_names:
            (skill_dir / "SKILL.md").unlink(missing_ok=True)
            skill_dir.rmdir()
            print(f"  removed: {skill_dir.name}")

    for name in synced:
        print(f"  synced:  {name}")
    for name in skipped:
        print(f"  ok:      {name}")
    print(f"Done. {len(synced)} updated, {len(skipped)} unchanged.")


if __name__ == "__main__":
    sync()
