---
name: sync-upstream
description: >-
  Sync this fork with ZhixiangLuo/10xProductivity via upstream remote. Use when
  the user asks to rebase, merge, pull, or sync 10xProductivity with upstream,
  or before pushing (matches .claude pre-push reminder).
---

# Sync 10xProductivity with upstream

## Context

- **This repo** is typically a fork: `origin` = your fork, **`upstream`** = `https://github.com/ZhixiangLuo/10xProductivity.git`.
- Default branch is **`main`** (not `master`).
- The Claude Code hook in `.claude/settings.json` already nudges: `git fetch upstream && git merge upstream/main` before push.

## Preferred workflow (merge, not rebase)

For long-lived forks with independent commits, **`git merge upstream/main`** is reliable. **`git rebase upstream/main`** replays every local commit and often hits painful `add/add` or `modify/delete` conflicts (e.g. duplicate Miro/Sana history).

1. Load paths if needed: from repo root, `set -a && source .env && set +a && source tool_connections/repo_paths.sh` (optional).
2. Stash or commit local WIP: `git status` — if dirty, `git stash push -u -m "WIP"` (include `-u` if new untracked files matter).
3. Fetch: `git fetch upstream`
4. Merge: `git checkout main && git merge upstream/main -m "Merge upstream/main (ZhixiangLuo/10xProductivity)"`
5. Resolve conflicts: prefer **upstream** for community `tool_connections/` unless you are deliberately preserving fork-only recipes; use `git rm` / `git checkout --theirs` as appropriate, then `git commit`.
6. Restore WIP: `git stash pop` if you stashed.
7. Push your fork: `git push origin main`

## If you truly need a linear history

Only after understanding tradeoffs: e.g. create a fresh branch from `upstream/main` and cherry-pick specific commits you still need, or reset a topic branch — **do not** blindly `rebase` years of fork commits without expecting multi-file conflicts.

## After upstream removes a tool from `tool_connections/`

If merge leaves empty or orphan dirs under `tool_connections/`, remove cruft (e.g. `__pycache__`) and keep **your working copy** in `personal/{tool}/` per `setup.md`.
