---
tool: miro
type: playbook
description: Facilitate a live workshop on an existing Miro board — audit placement, create zones headlessly, rollback safely.
updated: 2026-06-23
---

# Miro — Workshop facilitation playbook

Use when a board already has reference content (architecture drafts, matrices) and you need a **separate live-capture zone** for a facilitated session.

## Principles

1. **Don't touch reference content** — place live zones ≥3500px away from existing widgets.
2. **Frames + stickies, not slide decks** — pre-seed column headers and empty sticky clusters; let the room write.
3. **Headless by default** — `create-items` and `delete-region` run without opening a browser window.
4. **SSO stays headed** — only `sso.py` opens a visible browser for Okta login.

## Workflow

### 1. Auth check

```bash
source .venv/bin/activate
python3 tool_connections/miro/read_miro.py --check
# If 401: python3 tool_connections/miro/sso.py --force
```

### 2. Audit the board

```bash
python3 tool_connections/miro/cli.py audit-board --board "BOARD_ID=" --margin 3500
```

Use `workshopOriginCenter.x` as the left column center for your first frame. Verify `occupiedBounds.xMax` — your zone should start at `xMax + margin`.

Also list existing frames so you don't duplicate reference material:

```bash
python3 tool_connections/miro/cli.py get-frames --board "BOARD_ID="
```

### 3. Build items JSON

See `examples/minimal_items.json`. Rules:

- **Absolute coordinates** for shapes/text/stickies (parentRef fails at create time).
- Frame centers define zones; place child content at absolute positions that visually fall inside frames.
- Prefer `sticky_note` for participant capture areas.
- Integer `fontSize`, `borderWidth`, `strokeWidth`.

### 4. Create (headless)

```bash
python3 tool_connections/miro/cli.py create-items --board "BOARD_ID=" --file my_workshop.json
```

Use `--headed` only when debugging SDK errors.

### 5. Rollback

Always dry-run first:

```bash
python3 tool_connections/miro/cli.py delete-region \
  --board "BOARD_ID=" \
  --title-prefix "Workshop Live" \
  --x-min 4500 \
  --dry-run
```

Then delete:

```bash
python3 tool_connections/miro/cli.py delete-region \
  --board "BOARD_ID=" \
  --title-prefix "Workshop Live" \
  --x-min 4500
```

At least one filter is required (`--title-prefix`, `--x-min`, or `--content-match`).

## Suggested zone layout (4 frames)

| Frame | Agenda block |
|-------|----------------|
| Decision Log (D1–D8) | Update after each block — owner/date/status |
| Topic 1 · Operating Model | 0:15–1:30 stickies |
| Topic 2 · Technical Interop | 1:40–2:55 stickies |
| Close + Parking | 2:55+ owners, open items |

Place at `workshopOriginCenter` from audit-board, two columns × two rows.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Executable doesn't exist` for chromium | `python3 -m playwright install chromium` |
| SDK not ready after 14s | Retry; or `--headed` to inspect login state |
| `parentId` read-only on create | Use absolute x,y — see api-patterns.md |
| `remove` ZodError on `type` | Pass `{ id, type }` per item (cli handles this) |
| Items left after frame delete | Re-run delete-region with `--x-min` for orphan shapes |
