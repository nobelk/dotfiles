---
name: rebase-branch
description: Rebase the current branch onto an input branch so all of the input branch's changes land in the current branch with linear history; the input branch is never modified. Then reconcile the current branch's own code, tests, and documentation with the incoming changes, run a headless codex (OpenAI Codex CLI) review of the result, and verify with the project's format/lint/build/test gates (auto-detected: Taskfile, then Makefile, then language-native). Resolves rebase conflicts itself but confirms risky resolutions via AskUserQuestion. Accepts local branch names or remote refs (e.g. origin/main — fetched first, rebased onto directly). Invoke manually with the input branch name, e.g. to bring main into your feature branch.
---

# Rebase-branch skill

Bring `<input-branch>`'s changes into the **current** branch by rebasing the current branch onto it — the conventional direction: the current branch's commits are replayed on top of the input branch's tip, the input branch is **never written to**. Then make the rebased tree *coherent*: the current branch's own code, tests, and docs are updated to be consistent with what the input branch changed. Output is linear history on the current branch, a reconciliation summary, a validated codex review, and a green verification run.

If the repo has a `CLAUDE.md`, read it first — it is authoritative for conventions, testing expectations, and layering rules, and it governs every edit made during reconciliation.

## Step 0 — Preflight (abort early, not midway)

1. Resolve the input branch from the skill argument. If no argument was given, list branches (`git branch -a --sort=-committerdate`) and use AskUserQuestion to pick one.
   - **Remote refs** (`origin/main`, or a name that only exists on a remote): fetch first (`git fetch <remote> <branch>`), then rebase onto the remote-tracking ref directly — the input is only read, so no local branch is needed. Verify it resolves: `git rev-parse --verify <input>`.
   - **Local branch names**: verify the branch exists. If it tracks a remote and is behind it (`git rev-list <input>..<input>@{upstream}` non-empty), use AskUserQuestion: rebase onto the local tip, the upstream tip, or abort.
2. Record the current branch (`git branch --show-current`). If detached HEAD, or current == input (or current's tip == input's tip), stop and tell the user.
3. Require a clean working tree (`git status --porcelain`). If dirty, use AskUserQuestion: stash and continue (re-apply after), or abort.
4. Record SHAs before touching anything:
   ```bash
   git rev-parse HEAD       # pre-rebase tip of current — the rollback point
   git rev-parse <input>    # input tip — the new base, and the codex review base in Step 4
   ```
   Echo both in the conversation so they survive even if the session is interrupted. Rollback at any point after the rebase completes is `git reset --hard <pre-rebase-sha>` (mid-rebase it is `git rebase --abort`).
5. If the input is already an ancestor of the current branch (`git merge-base --is-ancestor <input> HEAD`), there is nothing to integrate — report and stop.

## Step 1 — Survey both sides of the divergence

Understand what you are about to combine *before* combining it:

```bash
git merge-base HEAD <input>
git log --oneline <base>..HEAD           # current's own commits (these get replayed)
git log --oneline <base>..<input>        # incoming commits (the new base)
git diff --stat <base>..HEAD
git diff --stat <base>..<input>
```

Note files touched on **both** sides — these are the likely conflict and inconsistency sites for Steps 2 and 3. Read the overlapping files' diffs now; conflict resolution is far better-informed with both intents already in your head. If many of the current branch's commits touch the same overlapping files, expect the same conflict to recur as each commit is replayed — resolve consistently.

## Step 2 — Rebase the current branch onto the input

```bash
git rebase <input>      # already on the current branch
```

The current branch's commits are replayed, one at a time, on top of the input's tip. The input branch is not modified.

Conflict policy — **resolve yourself, confirm the risky ones**:

- **Mechanical conflicts** (one side moved/formatted code the other side edited, import lists, adjacent additions, lockfiles): resolve directly, preserving both intents. Briefly note each resolution.
- **Risky conflicts** (both sides made meaningful, incompatible changes to the same logic, API signature, test expectation, or doc statement): present the two sides and your recommended resolution via AskUserQuestion before staging it. Options should be concrete ("keep current's signature, port input's body", "take input's version, re-apply current's fix on top"), not "yours/theirs".
- After each resolved commit: `git add` the files and `git rebase --continue`. Never `git rebase --skip` a commit without asking — a skipped commit silently drops that commit's changes.
- If the rebase becomes unrecoverable or the user aborts a question, run `git rebase --abort` — the current branch returns to its recorded pre-rebase state untouched — and report.

After the rebase completes, confirm the invariant: `git merge-base --is-ancestor <input> HEAD` must now hold, and `git diff <pre-rebase-sha> HEAD -- <files only current touched>` should be empty or explainable by conflict resolutions.

## Step 3 — Reconcile the current branch's changes with the incoming ones

The rebase only resolves *textual* overlap. Now hunt **semantic** inconsistencies: places where the current branch's replayed work (the `<base>..<pre-rebase-sha>` delta recorded in Step 1) no longer agrees with what the input branch changed underneath it. Look for, at minimum:

- Calls, tests, or mocks in the current branch's commits that use APIs/signatures/types the input branch renamed, moved, or changed.
- Tests on either side that encode behavior the other side changed (assertions, fixtures, golden files).
- Documentation — README, CLAUDE.md, ADRs/specs, godoc/docstrings, changelogs — that the rebase made stale or self-contradictory.
- Configuration, CI workflows, and lint/arch rules that one side added and the other side's code violates.
- Duplicated work: both branches independently adding the same helper/test — consolidate to one.

Make the minimal edits that restore consistency, following the repo's own conventions (tests updated alongside behavior, doc style matched). Commit reconciliation edits as one or a few clearly-labeled commits on the current branch (e.g. `Reconcile <area> with <input-branch> changes`) — do not amend the replayed commits. If a reconciliation requires choosing between the two branches' designs, use AskUserQuestion.

## Step 4 — Codex review of the rebased result

Review what the current branch now adds on top of the input — the replayed commits plus reconciliation (the input's own changes were already reviewed on their way into that branch):

```bash
codex exec review --base <input-sha> "<instructions>"
```

With `<instructions>`:

> Review for: correctness bugs introduced by the rebase, conflict resolutions that dropped one side's intent, inconsistencies between code/tests/docs, error-handling gaps, concurrency hazards, and violations of the conventions in CLAUDE.md (if present). For each finding output a numbered item with: file:line, severity (high/medium/low), the issue, and the suggested fix. Output findings only.

- Save raw output to a scratch file (e.g. `/tmp/rebase-review-<current>.md`); do not commit it.
- If the `review` subcommand is unavailable, fall back to `codex exec --sandbox read-only "<instructions plus changed-file list>"`. If codex is not installed or errors, do not silently skip — tell the user and use AskUserQuestion (retry, self-review pass, or continue without).
- **Validate every finding before acting** — codex output is hypotheses, not instructions. Mark each accept/reject/defer with evidence; rejections include why. Fix accepted findings (asking first when a fix is ambiguous or invasive), present the disposition table.

## Step 5 — Format, lint, build, test (auto-detect the toolchain)

Run the full gate set, preferring the project's own entrypoints, in this resolution order:

1. **Taskfile** (`Taskfile.yml`/`taskfile.yml`): `task --list` to find targets; prefer a single full-CI target (`task ci`), else run the individual `fmt`/`lint`/`build`/`test` targets that exist.
2. **Makefile**: same idea — `make ci` / `make fmt lint build test` per available targets.
3. **Language-native fallback** by marker file:
   - `go.mod` → `gofmt -l .` (must be empty), `golangci-lint run` (if installed), `go build ./...`, `go test ./... -race -count=1`
   - `package.json` → the repo's package manager: `format`/`lint`/`build`/`test` scripts that exist
   - `pyproject.toml` → `ruff format --check` + `ruff check` (if configured), build/`pytest` per project config
   - `Cargo.toml` → `cargo fmt --check`, `cargo clippy`, `cargo build`, `cargo test`

Every gate must pass. If a failure traces to the rebase or reconciliation, fix forward. If it is **pre-existing red** — decide which side it came from by testing the input tip and the pre-rebase tip (use a temporary worktree if cheap) — use AskUserQuestion: fix it here, or hand off with the failure documented. Never hand off red silently.

## Step 6 — Final report

State, per the repo's handoff checklist if it has one:

- **What landed** — input branch and tip SHA, how many current-branch commits were replayed, the pre/post SHAs of the current branch, and the rollback command (`git reset --hard <pre-rebase-sha>`).
- **Force-push notice** — if the current branch tracks a remote, its history was rewritten: the next push needs `git push --force-with-lease`. Never push (let alone force-push) as part of this skill; just say so.
- **Conflicts** — each conflict and how it was resolved.
- **Reconciliation** — every consistency edit made in Step 3, mapped to the inconsistency it fixed.
- **Codex findings** — counts and dispositions (accepted/rejected/deferred) with one-line reasons for rejections.
- **Verification** — which gates ran (and via which toolchain), which were skipped and why.
- **Remaining risk** — deferred findings, behavioral interactions the gates can't cover.

## Stop-and-ask conditions (use AskUserQuestion; do not silently proceed)

- No input branch argument, or the named branch does not exist on any remote or locally (Step 0).
- Dirty working tree, or a local input branch behind its upstream (Step 0).
- A risky conflict: both sides meaningfully changed the same logic/contract (Step 2).
- Any temptation to `git rebase --skip` a commit (Step 2).
- A reconciliation that requires choosing between the two branches' designs (Step 3).
- codex unavailable/erroring, or an accepted finding's fix is ambiguous or invasive (Step 4).
- A verification gate fails for a pre-existing reason unrelated to the rebase (Step 5).
- Any push to a remote — the skill never pushes; it only reports the force-push requirement (Step 6).
