---
name: rebase-branch
description: Rebases the current branch onto an input branch (local name or remote ref such as origin/main) for linear history without modifying the input, resolves conflicts (confirming risky ones), reconciles code, tests, docs, specs, and ADRs with the incoming changes, then codex-reviews the result and runs the project's format/lint/build/test gates. Use to bring main or another branch into the current feature branch.
---

# Rebase-branch skill

Bring `<input-branch>`'s changes into the **current** branch by rebasing the current branch onto it — the conventional direction: the current branch's commits are replayed on top of the input branch's tip, the input branch is **never written to**. Then make the rebased tree *coherent*: the current branch's own code, tests, and docs are updated to be consistent with what the input branch changed. Output is linear history on the current branch, a reconciliation summary, a documentation and spec staleness sweep, a validated codex review, and a green verification run.

If the repo has a `CLAUDE.md`, read it first — it is authoritative for conventions, testing expectations, and layering rules, and it governs every edit made during reconciliation.

## Subagent delegation

Run the read-heavy analysis and verification in a **`general-purpose` subagent** (via the `Agent` tool), but keep every git **state change** and interactive gate in the main loop. The split is fixed and load-bearing — a subagent must never drive the rebase, because conflict resolution needs the `AskUserQuestion` gate:

- **Main loop owns** (never delegate): all of Step 0 preflight and SHA recording, **the entire rebase in Step 2** (the replay, conflict resolution, and every risky-conflict `AskUserQuestion`), applying reconciliation **edits** and the design-choice gate in Step 3, the Step 4 fix-and-ask cycle, and the Step 6 report. Subagents cannot prompt the user — anything that might stop-and-ask stays here.
- **Delegate to a `general-purpose` subagent** (each returns a compact result):
  - **Step 1** — run the survey git commands and read the overlapping file diffs, returning a summary of which files changed on both sides and the likely conflict/inconsistency sites. Read-only; no state change.
  - **Step 3 (analysis only)** — hand the `<base>..<pre-rebase-sha>` delta and the input's changes to a subagent that hunts semantic inconsistencies (stale calls, contradicting tests/docs, duplicated helpers) and returns a list of sites to fix. The main loop makes the edits and owns any design-choice question.
  - **Step 3a (analysis only)** - hand the same delta to a second subagent that runs the documentation and spec staleness sweep and returns the candidate set plus each stale statement with its file, line, and the rebased-tree evidence that contradicts it. Read-only; the main loop makes the edits. Dispatch it in the same message as the Step 3 hunter - they share no data dependency.
  - **Step 4** — launch the codex review through the companion script, wait for it under the Step 4 deadline and liveness rules, fetch the result, and return the raw findings verbatim (also written to the scratch file), or report that codex failed so the main loop runs the fallback; then split the findings into disjoint batches (~3–5 each, contradictory findings sharing a batch) and adjudicate them in parallel subagents launched **in a single message**, each returning its slice of the disposition table. The main loop merges the slices, applies accepted fixes, and owns the ambiguous/invasive gate.
  - **Step 5** — run the auto-detected format/lint/build/test gate and return pass/fail plus only the failing output.

Give each subagent a self-contained prompt: the exact commands, the SHAs/branch names, and the precise result shape to return.

**Parallelize by default — but never parallelize a state change.** When delegated *read-only* tasks have no data dependency, dispatch them as multiple `Agent` calls in a **single message** so they run concurrently rather than one at a time. The hard constraint overrides this wherever they collide: **every git state change (the rebase replay, conflict resolution, and reconciliation edits) is strictly sequential and stays in the main loop** — never fan out work that mutates the working tree or index. That leaves the read-only analysis to parallelize: within Step 1's survey and within Step 3's semantic-inconsistency hunt, fan out independent readers in one message. The Step 4 review → adjudication path is a serial chain between steps, but the adjudication batches within it fan out in parallel.

## Step 0 — Preflight (abort early, not midway)

1. Resolve the input branch from the skill argument. If no argument was given, list branches (`git branch -a --sort=-committerdate`) and use AskUserQuestion to pick one.
   - **Remote refs** (`origin/main`, or a name that only exists on a remote): fetch first with an explicit refspec, `git fetch <remote> '+refs/heads/<branch>:refs/remotes/<remote>/<branch>'` (a plain `git fetch <remote> <branch>` can land only in `FETCH_HEAD` in a single-branch clone or with a narrowed `remote.<remote>.fetch`, leaving the tracking ref stale while reporting success), then rebase onto the remote-tracking ref directly — the input is only read, so no local branch is needed. Verify it resolves: `git rev-parse --verify refs/remotes/<remote>/<branch>`.
   - **Local branch names**: verify the branch exists. If it tracks a remote, fetch its upstream first (same explicit refspec), then check whether it is behind (`git rev-list <input>..<input>@{upstream}` non-empty); if so, use AskUserQuestion: rebase onto the local tip, the upstream tip, or abort.
2. Record the current branch (`git branch --show-current`). If detached HEAD, or current == input (or current's tip == input's tip), stop and tell the user.
3. Require a clean working tree (`git status --porcelain`). If dirty, run the Step 0.5 ancestor check first; if it exits, stop without stashing. Otherwise use AskUserQuestion: stash and continue (re-applied after the rebase), or abort. **If they choose stash, run `git stash push -u -m "rebase-branch <current>"`, confirm it exited 0 and `git status --porcelain` is now empty, and record `git rev-parse stash@{0}` in the conversation as `<stash-oid>`** — it is reapplied in Step 2 after the rebase completes, and must not be left hidden. If the stash fails or leaves the tree dirty, stop and report.
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
git merge-base HEAD <input>          # <base>: record it now; the rebase moves it
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

**Reapply stashed work, if any.** If Step 0.3 created a stash, restore it now so the user's
pre-existing uncommitted changes aren't left buried. Find the entry by object id, not position
(`git stash list --format='%gd %H'`, match `<stash-oid>`; another stash may have been pushed since),
then `git stash pop --index <that stash@{N}>` so staged changes stay staged. If `--index` fails on
index conflicts, run `git stash pop <that stash@{N}>` and tell the user the staging was not kept.
Resolve any pop conflicts the same way as rebase conflicts — mechanical ones directly, risky ones via
AskUserQuestion — before moving on. Confirm no entry with `<stash-oid>` remains in `git stash list`.
(If no stash was created, skip this.) From here on, the restored paths are the user's work: Steps 3,
3a and 4 commit only the paths they edit, with `git commit --only -- <paths>` (a plain `git commit`
would also take every restored staged entry), confirm afterwards that the restored entries are still
staged and uncommitted, and ask before committing a path that also carries restored changes.

## Step 3 — Reconcile the current branch's changes with the incoming ones

The rebase only resolves *textual* overlap. Now hunt **semantic** inconsistencies: places where the current branch's replayed work (the `<base>..<pre-rebase-sha>` delta recorded in Step 1) no longer agrees with what the input branch changed underneath it. Look for, at minimum:

- Calls, tests, or mocks in the current branch's commits that use APIs/signatures/types the input branch renamed, moved, or changed.
- Tests on either side that encode behavior the other side changed (assertions, fixtures, golden files).
- Documentation, specs, and ADRs that the rebase made stale or self-contradictory - swept systematically in Step 3a below, not by eye.
- Configuration, CI workflows, and lint/arch rules that one side added and the other side's code violates.
- Duplicated work: both branches independently adding the same helper/test — consolidate to one.

Make the minimal edits that restore consistency, following the repo's own conventions (tests updated alongside behavior, doc style matched). Commit reconciliation edits as one or a few clearly-labeled commits on the current branch (e.g. `Reconcile <area> with <input-branch> changes`) — do not amend the replayed commits. If a reconciliation requires choosing between the two branches' designs, use AskUserQuestion.

## Step 3a - Documentation and spec staleness sweep

Prose does not fail a test, so a rebase leaves docs stale silently - this step is mandatory and runs even when Step 3 found no code inconsistencies. The highest-yield failures are a decision record the input branch has already overtaken, and an enumeration that was complete before the rebase and is short by one after it.

**Build the candidate set** - every document either side touched, plus every document that *describes* something either side changed:

```bash
git diff --name-only <base>..<pre-rebase-sha> -- '*.md' '*.rst' '*.txt' '*.adoc'
git diff --name-only <base>..<input>          -- '*.md' '*.rst' '*.txt' '*.adoc'
```

Then widen: for each non-doc file changed on either side, find the docs that name it or the identifiers it defines (`rg -l '<TypeName>|<path/fragment>' --glob '*.md'`). A spec never edited by either branch still goes stale when the thing it describes moves. Include godoc and docstrings on the changed code itself, plus the repo's own convention files (README, CLAUDE.md/AGENTS.md, ADR index, changelog).

**Check each candidate against the rebased tree** - not against memory of what it used to say:

- **Decision records the input branch overtook.** An ADR/spec the input branch merged may accept a decision the current branch's own spec contradicts, or record a validation line that cannot pass once this branch lands. Read the input's new/changed ADRs in full and reconcile every contradiction; where both records are now true of different phases, scope each one explicitly. Never leave two accepted records disagreeing.
- **Enumerations and counts.** "Every kind", "all N families", "the four rules", case tables, exhaustive switches mirrored in prose. For each, derive the set from the rebased code (`rg` the type's variants, the enum's members, the config's keys) and diff it against the doc. A rebase that adds one variant leaves every enumeration of that variant's set one short - including enumerations inside *tests* that claim exhaustiveness.
- **Behavioral claims.** A doc sentence asserting what the code does ("the worker drains rather than crashing", "this decorator covers every inbound path") is a claim to verify against the rebased code, not prose to preserve. Trace it: find the code path and confirm it still behaves that way after the input's changes. A claim that no longer holds is either a doc fix or a code bug - decide which, and say which.
- **Cross-references and identifiers.** ADR numbers and statuses, ticket keys, file paths, package/type/function names, line-anchored pointers, links between specs. The input branch may have renumbered an ADR, moved a type between layers, or promoted a `proposed` record to `accepted`.
- **Scope and phase statements.** A spec's intro, its "decisions" section, and its requirement rows often state what this phase owns. The input branch may have already delivered part of it, changed what the next phase needs, or moved a type the row's arch-lint/layering edges describe.
- **Stale-by-omission.** A doc can be wrong by having nothing to say: a new variant, failure mode, or config key the input branch added that the current branch's table or failure-direction matrix does not have a row for.

**Fix them in the same reconciliation commits as Step 3**, or in a clearly-labeled doc-only commit alongside them. Where a staleness turns out to be a *product* question rather than an editorial one (the doc and the code disagree and it is not obvious which is right), use AskUserQuestion - do not pick a side silently.

Report the sweep in Step 6 even when it found nothing: list the candidate documents checked and the stale statements fixed. "No docs were stale" is a finding; "docs were not checked" is a gap.

## Step 4 — Codex review of the rebased result

Review what the current branch now adds on top of the input — the replayed commits plus reconciliation (the input's own changes were already reviewed on their way into that branch) — with codex's native reviewer and the input tip as the diff base. The `/codex:*` slash commands have `disable-model-invocation: true`, so neither this loop nor a subagent can call them; drive the companion script they wrap, from the repo root:

```bash
ls -d ~/.claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs 2>/dev/null | sort -V | tail -1   # record the printed path as <companion>: shell variables do not persist between Bash calls
node "<companion>" review --background --base <input-sha>   # launch with run_in_background: true
node "<companion>" status --json               # the new job's id is in .running[]
node "<companion>" status <job-id> --wait --timeout-ms 240000   # bounded 4-minute wait; repeat until finished
node "<companion>" status <job-id> --json      # status, pid, logFile for the liveness check
node "<companion>" result <job-id>             # findings
node "<companion>" cancel <job-id>             # abandon a dead or stalled job
```

Pass flags as separate arguments, not one quoted string; `run_in_background: true` is what detaches the run. The native reviewer **takes no custom focus text**; its built-in prompt already covers correctness, conflict resolutions that dropped one side's intent, code/test/doc inconsistencies, error handling, and concurrency. CLAUDE.md-convention enforcement happens in the adjudication below, not in the review call.

- **Save the output** verbatim to a scratch file (e.g. `"${TMPDIR:-/tmp}/rebase-review-<current>.md"`, with `/` in the branch name replaced by `-`); do not commit it.
- **Deadline and liveness.** The companion has no internal timeout. Enforce a **10-minute** deadline; treat the job as dead if its `pid` is not alive (`ps -p <pid>`) while status says `running`, and as stalled if its `logFile` has been silent for 5+ minutes. On death, stall, deadline, an errored or unreadable result, a missing `codex` or companion script, or a failed launch: `cancel` the job if one exists, do not retry codex, and run the native adversarial fallback — 2–3 adversarial `general-purpose` subagents in a single message, each with a distinct lens (correctness and dropped intent from the conflict resolutions; error handling and silent failures; tests and edge cases) over the `<input-sha>..HEAD` delta, each citing `file:line` and verifying every claim against the code. Say in Step 6 that the review came from the fallback and why.
- **Validate every finding before acting** — review output is hypotheses, not instructions. Mark each accept/reject/defer with evidence; rejections include why. Fix accepted findings (asking first when a fix is ambiguous or invasive), present the disposition table.

## Step 5 — Format, lint, build, test (auto-detect the toolchain)

Run the full gate set, preferring the project's own entrypoints, in this resolution order:

1. **Taskfile** (`Taskfile.yml`/`taskfile.yml`): `task --list` to find targets; prefer a single full-CI target (`task ci`), else run the individual `fmt`/`lint`/`build`/`test` targets that exist.
2. **Makefile**: same idea — `make ci` / `make fmt lint build test` per available targets.
3. **Language-native fallback** by marker file:
   - `go.mod` → `gofmt -l .` (must be empty), `golangci-lint run` (if installed), `go build ./...`, `go test ./... -race -count=1 -timeout 600s`
   - `package.json` → the repo's package manager: `format`/`lint`/`build`/`test` scripts that exist
   - `pyproject.toml` → `ruff format --check` + `ruff check` (if configured), build/`pytest` per project config
   - `Cargo.toml` → `cargo fmt --check`, `cargo clippy`, `cargo build`, `cargo test`

Give each long-running gate an upper bound (`timeout -k 10 900 task ci`, `go test -timeout 600s`) so a hung test cannot stall the run. Every gate must pass. If a failure traces to the rebase or reconciliation, fix forward. If it is **pre-existing red** — decide which side it came from by testing the input tip and the pre-rebase tip (use a temporary worktree if cheap) — use AskUserQuestion: fix it here, or hand off with the failure documented. Never hand off red silently.

## Step 6 — Final report

State, per the repo's handoff checklist if it has one:

- **What landed** — input branch and tip SHA, how many current-branch commits were replayed, the pre/post SHAs of the current branch, and the rollback command (`git reset --hard <pre-rebase-sha>`).
- **Force-push notice** — if the current branch tracks a remote, its history was rewritten: the next push needs `git push --force-with-lease`. Never push (let alone force-push) as part of this skill; just say so.
- **Conflicts** — each conflict and how it was resolved.
- **Reconciliation** — every consistency edit made in Step 3, mapped to the inconsistency it fixed.
- **Doc and spec staleness** - the candidate documents Step 3a checked, every stale statement fixed, and any left standing with the reason. Say so explicitly when the sweep found nothing.
- **Codex findings** — counts and dispositions (accepted/rejected/deferred) with one-line reasons for rejections.
- **Verification** — which gates ran (and via which toolchain), which were skipped and why.
- **Remaining risk** — deferred findings, behavioral interactions the gates can't cover.

## Stop-and-ask conditions (use AskUserQuestion; do not silently proceed)

- No input branch argument, or the named branch does not exist on any remote or locally (Step 0).
- Dirty working tree, or a local input branch behind its upstream (Step 0).
- A risky conflict: both sides meaningfully changed the same logic/contract (Step 2).
- Any temptation to `git rebase --skip` a commit (Step 2).
- A `git stash pop` of pre-existing stashed work conflicts with the rebased tree (Step 2).
- A reconciliation that requires choosing between the two branches' designs (Step 3).
- A doc and the rebased code disagree and which one is wrong is a product question, not an editorial one (Step 3a).
- An accepted codex finding's fix is ambiguous or invasive (Step 4). (Codex unavailable or failing is not a stop: Step 4 runs the native fallback and reports it.)
- A verification gate fails for a pre-existing reason unrelated to the rebase (Step 5).
- Any push to a remote — the skill never pushes; it only reports the force-push requirement (Step 6).
