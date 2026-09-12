---
name: rebase-branch
description: Rebase the current branch onto an input branch so the input's changes land here with linear history (the input branch is never modified), then reconcile the current branch's code and tests with the incoming changes and sweep its documentation, specs, and ADRs for staleness the rebase introduced, codex-review the result, and verify with the project's format/lint/build/test gates. Takes a local branch name or remote ref (e.g. origin/main) as the argument; resolves conflicts itself, confirming risky resolutions first. Invoke manually with the input branch name, e.g. to bring main into your feature branch.
---

# Rebase-branch skill

Bring `<input-branch>`'s changes into the **current** branch by rebasing the current branch onto it — the conventional direction: the current branch's commits are replayed on top of the input branch's tip, the input branch is **never written to**. Then make the rebased tree *coherent*: the current branch's own code, tests, and docs are updated to be consistent with what the input branch changed. Output is linear history on the current branch, a reconciliation summary, a documentation and spec staleness sweep, a validated codex review, and a green verification run.

If the repo has a `CLAUDE.md`, read it first — it is authoritative for conventions, testing expectations, and layering rules, and it governs every edit made during reconciliation.

## Subagent delegation

Run the read-heavy analysis and verification in a **`general-purpose` subagent** (via the `Agent`/`Task` tool), but keep every git **state change** and interactive gate in the main loop. The split is fixed and load-bearing — a subagent must never drive the rebase, because conflict resolution needs the `AskUserQuestion` gate:

- **Main loop owns** (never delegate): all of Step 0 preflight and SHA recording, **the entire rebase in Step 2** (the replay, conflict resolution, and every risky-conflict `AskUserQuestion`), applying reconciliation **edits** and the design-choice gate in Step 3, the Step 4 fix-and-ask cycle, and the Step 6 report. Subagents cannot prompt the user — anything that might stop-and-ask stays here.
- **Delegate to a `general-purpose` subagent** (each returns a compact result):
  - **Step 1** — run the survey git commands and read the overlapping file diffs, returning a summary of which files changed on both sides and the likely conflict/inconsistency sites. Read-only; no state change.
  - **Step 3 (analysis only)** — hand the `<base>..<pre-rebase-sha>` delta and the input's changes to a subagent that hunts semantic inconsistencies (stale calls, contradicting tests/docs, duplicated helpers) and returns a list of sites to fix. The main loop makes the edits and owns any design-choice question.
  - **Step 3a (analysis only)** - hand the same delta to a second subagent that runs the documentation and spec staleness sweep and returns the candidate set plus each stale statement with its file, line, and the rebased-tree evidence that contradicts it. Read-only; the main loop makes the edits. Dispatch it in the same message as the Step 3 hunter - they share no data dependency.
  - **Step 4** — launch `/codex:review --background --base <input-sha>`, poll `/codex:status` to completion, fetch `/codex:result <job-id>`, and return the raw findings verbatim (also written to the scratch file); then split the findings into disjoint batches (~3–5 each, contradictory findings sharing a batch) and adjudicate them in parallel subagents launched **in a single message**, each returning its slice of the disposition table. The main loop merges the slices, applies accepted fixes, and owns the ambiguous/invasive gate.
  - **Step 5** — run the auto-detected format/lint/build/test gate and return pass/fail plus only the failing output.

Give each subagent a self-contained prompt: the exact commands, the SHAs/branch names, and the precise result shape to return.

**Parallelize by default — but never parallelize a state change.** When delegated *read-only* tasks have no data dependency, dispatch them as multiple `Agent`/`Task` calls in a **single message** so they run concurrently rather than one at a time. The hard constraint overrides this wherever they collide: **every git state change (the rebase replay, conflict resolution, and reconciliation edits) is strictly sequential and stays in the main loop** — never fan out work that mutates the working tree or index. That leaves the read-only analysis to parallelize: within Step 1's survey and within Step 3's semantic-inconsistency hunt, fan out independent readers in one message. The Step 4 review → adjudication path is a serial chain between steps, but the adjudication batches within it fan out in parallel.

## Step 0 — Preflight (abort early, not midway)

1. Resolve the input branch from the skill argument. If no argument was given, list branches (`git branch -a --sort=-committerdate`) and use AskUserQuestion to pick one.
   - **Remote refs** (`origin/main`, or a name that only exists on a remote): fetch first (`git fetch <remote> <branch>`), then rebase onto the remote-tracking ref directly — the input is only read, so no local branch is needed. Verify it resolves: `git rev-parse --verify <input>`.
   - **Local branch names**: verify the branch exists. If it tracks a remote and is behind it (`git rev-list <input>..<input>@{upstream}` non-empty), use AskUserQuestion: rebase onto the local tip, the upstream tip, or abort.
2. Record the current branch (`git branch --show-current`). If detached HEAD, or current == input (or current's tip == input's tip), stop and tell the user.
3. Require a clean working tree (`git status --porcelain`). If dirty, use AskUserQuestion: stash and continue (re-applied after the rebase), or abort. **If they choose stash, run `git stash push -u -m "rebase-branch <current>"` and record in the conversation that a stash was created** — it is reapplied in Step 2 after the rebase completes, and must not be left hidden.
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

**Reapply stashed work, if any.** If Step 0.3 created a stash, restore it now so the user's
pre-existing uncommitted changes aren't left buried: `git stash pop`. Resolve any pop conflicts the
same way as rebase conflicts — mechanical ones directly, risky ones via AskUserQuestion — before
moving on. Confirm `git stash list` no longer shows the entry. (If no stash was created, skip this.)

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

## Step 4 — Codex review of the rebased result via `/codex:review --background`

Review what the current branch now adds on top of the input — the replayed commits plus reconciliation (the input's own changes were already reviewed on their way into that branch). Use the **`/codex:review --background`** flow with the input tip as the diff base; `--background` detaches the run, so recover it with `/codex:status` (progress) and `/codex:result <job-id>` (findings):

```bash
/codex:review --background --base <input-sha>
```

`/codex:review` is native-review only and **takes no custom focus text** — its built-in review prompt already covers correctness, conflict resolutions that dropped one side's intent, code/test/doc inconsistencies, error-handling, and concurrency. CLAUDE.md-convention enforcement happens in the adjudication below, not in the review call. Concretely, this launches the codex-companion runtime detached (`node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" review "--background --base <input-sha>"` with `run_in_background: true`, where `${CLAUDE_PLUGIN_ROOT}` is the codex plugin root).

- **Do not block the launching turn.** After launching, poll `/codex:status` until the job finishes, then read `/codex:result <job-id>`. Save that output verbatim to a scratch file (e.g. `/tmp/rebase-review-<current>.md`); do not commit it.
- **Enforce a 10-minute deadline.** The companion has no internal timeout, so a stalled native review hangs forever. If the job exceeds 10 minutes, or its `logFile` goes silent for 5+ minutes while status still says running, run `/codex:cancel <job-id>` and retry once with `--model gpt-5.4-mini` (must be a model the account supports; `gpt-5.x-codex` models are rejected on ChatGPT-account logins). If the retry breaches the deadline too, cancel it and treat it as a codex failure below.
- If codex is not installed, the launch fails, or `/codex:status` reports the job errored, do not silently skip — tell the user and use AskUserQuestion (retry, self-review pass, or continue without).
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
- codex unavailable/erroring, or an accepted finding's fix is ambiguous or invasive (Step 4).
- A verification gate fails for a pre-existing reason unrelated to the rebase (Step 5).
- Any push to a remote — the skill never pushes; it only reports the force-push requirement (Step 6).
