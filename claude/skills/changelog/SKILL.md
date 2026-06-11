---
name: changelog
description: Update CHANGELOG.md before merging a branch. Adds bullets under today's date heading summarizing the work done since the default branch. If CHANGELOG.md does not exist, bootstraps it from git history grouped by date. Invoke manually before merging a feature branch.
---

# Changelog skill

Maintain `CHANGELOG.md` in the project root using date-keyed sections, newest date first.

## File format

```markdown
# Changelog

## 2026-04-23
- Added bulk site import from CSV
- Fixed crash when loading an empty config

## 2026-04-22
- Initial commit
```

Conventions:
- Top-level `# Changelog` header at the top of the file.
- One `## YYYY-MM-DD` heading per date. Newest date first.
- Bullets describe **user-visible** changes in past tense ("Added X", "Fixed Y", "Removed Z"). Not raw commit subjects.

## Subagent delegation

Run the expensive, self-contained drafting work in a **`general-purpose` subagent** (via the `Agent`/`Task` tool); keep orchestration in the main loop. The split is fixed:

- **Main loop owns** (never delegate): the `<base>`/branch/dirty-tree inspection in Step 1, the decision of which scope to record, writing/editing `CHANGELOG.md`, showing the final `git diff`, and any question to the user. Subagents cannot prompt the user, so the "ask whether to include uncommitted work" gate in Step 2b stays here.
- **Delegate to a `general-purpose` subagent**: the bullet-drafting in Step 2a (bootstrap) and Step 2b (update) — pass the resolved `<base>` and commit range, and have the subagent run `git log` / `git show <sha> --stat` to reword opaque subjects, returning **only** the proposed `# Changelog` body (bootstrap) or the new bullet list (update). The verbose history stays in the subagent's context; the main loop writes the returned text to disk.

Give the subagent a self-contained prompt: the exact commit range, the file-format conventions above, and the precise result shape to return. The main loop never delegates the file write itself.

## Step 1 — Inspect state

First, determine the repo's default branch — call this `<base>`:

```bash
git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null \
  || (git show-ref --verify --quiet refs/heads/main && echo main) \
  || (git show-ref --verify --quiet refs/heads/master && echo master)
```

`<base>` is a remote-tracking ref (`origin/main`) when `origin/HEAD` is set, else the local
`main`/`master` fallback — both work as the `git log <base>..HEAD` left side. (Don't strip
`origin/`: a bare `main` fails in clones with no local default branch.)

Then run in parallel:
- `test -f CHANGELOG.md && echo exists || echo missing`
- `git rev-parse --abbrev-ref HEAD`
- `git log <base>..HEAD --pretty=format:"%h %ad %s" --date=short --no-merges` (commits to summarize for an update; empty if on `<base>` itself)
- `git status --short` (uncommitted work)

## Step 2a — If CHANGELOG.md is missing: bootstrap

1. Get full history: `git log --pretty=format:"%h%x09%ad%x09%s" --date=short --no-merges`
2. Group commits by date.
3. Write `CHANGELOG.md` with `# Changelog` at the top, then `## YYYY-MM-DD` sections newest first, with one bullet per commit.
4. Rewrite terse commit subjects into user-facing bullets when obviously needed (e.g., `fix bug` → `Fixed crash on empty input`). Don't fabricate detail you can't verify — if a commit subject is opaque, run `git show <sha> --stat` to see what changed before rewording.
5. Show the user the result. Stop.

## Step 2b — If CHANGELOG.md exists: update for the merge

1. Determine new work since `<base>` diverged: `git log <base>..HEAD --pretty=format:"%h %s" --no-merges`.
2. If `git status --short` shows uncommitted changes, ask the user whether to include them too (they may intend to commit first).
3. If both are empty → tell the user there's nothing to record and stop.
4. Read the existing `CHANGELOG.md`.
5. Find or create a `## <today>` heading directly under the `# Changelog` title (today = current date in `YYYY-MM-DD`). If today's heading already exists, append to it; do **not** create a duplicate heading.
6. Append bullets for the new work. Skip bullets already present under today's heading (idempotent re-runs).
7. Show `git diff CHANGELOG.md` so the user can review before merging.

## Writing good bullets

- Past tense, user-visible: `Added bulk import for sites`, not `add import`.
- One change per bullet. Split combined commits if they touched unrelated things.
- Group several small commits into one bullet when they describe one logical change (e.g., a feature + its follow-up fixups).
- Skip pure noise: formatting-only commits, dependency lockfile bumps, typo fixes in comments. Include dependency or tooling changes only when they affect users or developers materially.

## Notes

- "Today" means the local date; obtain it from the system, not from commit timestamps.
- Never amend an existing dated section other than today's — past entries are historical.
- Don't commit the CHANGELOG.md update yourself; let the user fold it into their merge.
- If the repo has no remote and no `main`/`master` branch, ask the user which branch to diff against.
