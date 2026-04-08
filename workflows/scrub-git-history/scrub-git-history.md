# Scrub PII / Secrets from Git History

Use when sensitive data (emails, internal hostnames, tokens, meeting titles) was committed and needs to be removed from all history before a force-push.

**Tool:** `git-filter-repo` — the officially recommended replacement for `git filter-branch`.

---

## Install git-filter-repo (via Artifactory)

```bash
# Activate the 10xProductivity venv — pip.conf routes through Artifactory
source ~/code/10xProductivity/.venv/bin/activate
pip install git-filter-repo
```

> pip.conf at `~/.config/pip/pip.conf` must have a valid Artifactory token. See `personal/artifactory/connection-api-token.md` for token setup and refresh.

---

## Step 1 — audit: find what needs scrubbing

```bash
cd /path/to/repo

# Search all history for a pattern
git log --all --format="%H" | xargs -I{} git show {} -- "*.md" "*.py" "*.sh" 2>/dev/null \
  | grep "^+" | grep -v "^+++" \
  | grep -E "(your-pattern-here)" | head -20
```

---

## Step 2 — build a replacements file

Create `/tmp/git-scrub-replacements.txt`. Each line is:

```
literal:exact string to find==>replacement
regex:pattern==>replacement
```

Example:

```
literal:myname@company.com==>user@example.com
literal:internal-db-hostname==><INTERNAL_HOST>
literal:My Real Meeting Title==>Example Meeting Title
```

---

## Step 3 — run the scrub

```bash
source ~/code/10xProductivity/.venv/bin/activate
cd /path/to/repo

git-filter-repo --replace-text /tmp/git-scrub-replacements.txt --force
```

> `git-filter-repo` will remove the `origin` remote as a safety measure. Re-add it after.

```bash
git remote add origin https://github.com/<owner>/<repo>.git
# If you also have upstream:
# git remote add upstream https://github.com/<upstream-owner>/<repo>.git
```

---

## Step 4 — verify

```bash
# Confirm the pattern is gone from all history
git log --all --format="%H" | xargs -I{} git show {} -- "*.md" "*.py" 2>/dev/null \
  | grep "^+" | grep -v "^+++" \
  | grep -E "(pattern-you-scrubbed)" | head -5
# → (no output = clean)
```

---

## Step 5 — commit any new changes, then force push

```bash
# Commit any new files (workflow docs, personal connection setup, etc.)
git add <files>
git commit -m "your message"

# Force push to replace remote history
git push origin main --force
```

> Anyone who has cloned the repo will need to re-clone or `git fetch --force` — their local history won't match after a force push.

---

## Notes

- `git-filter-repo` rewrites all commit SHAs — existing PRs, branch pointers from forks, and local clones will diverge.
- Only rewrites file content in blobs. Commit author/email fields are separate — use `--mailmap` or `--commit-callback` if you need to scrub those too.
- For tokens/passwords: rotate the credential immediately, even after scrubbing — assume it was seen.
- After force-pushing a public repo, GitHub may cache the old content in forks. You can contact GitHub support to purge cached views.
