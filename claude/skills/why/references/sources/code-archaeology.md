# Code Archaeology (git + in-repo)

## What this source contains

- ADRs (architecture decision records) and per-ticket spec directories (for example `specs/adr/`, `specs/<KEY>/`)
- Commit history (messages, dates, authors, diffs)
- PR descriptions, review comments, review threads, and the PR's own commit list (via `gh`)
- Inline code comments, TODOs, FIXMEs, deprecation notes
- Tests, whose names and assertions often encode the edge cases that motivated a change
- Related files modified in the same commits (co-change signal)
- CHANGELOG entries and release notes in the repo
- Ticket keys in commit subjects, branch names, and PR bodies

The most trustworthy source, tied directly to the code, and the most complete. Everything that went through the repo should be here. The main agent already read the design records it found; go deeper than it did, not over the same ground.

## How to search it

Expand the seed commit list:

```bash
# History through renames
git log --follow --oneline -- <file>

# Pickaxe: commits that added or removed this exact text
git log -S '<exact_string_from_code>' -- <file>

# Or for patterns:
git log -G '<regex>' -- <file>

# Who wrote each line and when
git blame -L <start>,<end> <file>

# One commit's full diff
git show <hash>

# Commits between two points affecting this file
git log <old>..<new> -p -- <file>
```

Read the PR record, not just the squash commit:

```bash
# Body, review discussion, and the branch's individual commits
gh pr view <number> --json title,body,comments,reviews,commits

# Inline review comments, where most "why not X?" exchanges live
gh api repos/{owner}/{repo}/pulls/<number>/comments --jq '.[] | {path, line, user: .user.login, body}'
```

Look for out-of-band records:

```bash
# ADRs naming the target, and their status lines
rg -l '<symbol>|<package>|<file_path>' specs/adr docs/adr 2>/dev/null
rg -n '^\*{0,2}Status' <adr_file>

# Spec, history, and design docs naming the target
rg -l '<symbol>' --glob '*.md'

# TODOs and FIXMEs near the target
rg -n -C2 '(TODO|FIXME|HACK|XXX|NOTE)' <target_file>

# Related tests
rg -l '<symbol>' --glob '*test*'
```

## Common pitfalls

- **Superseded ADRs.** An ADR marked superseded records an old decision. Follow the link to the current one, and report both if the code still follows the old one.
- **Spec vs. code drift.** A spec says what was planned. Compare against the merged diff and flag any divergence.
