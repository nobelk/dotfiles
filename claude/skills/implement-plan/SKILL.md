---
name: implement-plan
description: Implement a markdown plan file end to end on the current branch as a principal software engineer — reads the plan plus the repo's conventions, clarifies ambiguity with AskUserQuestion, implements it test-first under clean-code/clean-architecture/design-pattern standards (fanning genuinely independent task groups out to parallel subagents), runs the /simplify skill on the result, reviews the branch's changes with codex (falling back to adversarial subagent review when codex is unavailable, fails, stalls, or times out), adjudicates and fixes the findings, then verifies the whole branch by running the project's format, lint, build, and full test-suite gates before committing and pushing the current branch. Takes the path to a markdown plan file as the argument. Invoke manually when a written plan is ready to build.
---

# Implement-plan skill

Take a written markdown plan and **build it to done** on the **current branch**, acting as a principal software engineer: deliberate, test-first, minimal, and faithful to the repo's own rules.

The argument is `<plan-file>` — the path to a single markdown file describing the work (e.g. `docs/plans/rate-limiter.md`). Unlike `/implement-spec`, there is no spec trio and no worktree juggling: the plan file is the whole contract and the work lands on whatever branch is checked out now.

Output is working, reviewed, verified code committed and pushed to the current branch's remote.

If the repo has a `CLAUDE.md`, read it in the main loop **before Step 0's git actions** — it is authoritative, and its branch/commit/stash conventions can change what Step 0 does. Its conventions, layering rules, and testing expectations win over anything in this skill or any reviewer suggestion that contradicts it. Step 1's parallel reads then cover everything else (ADRs, sibling code, the plan's citations).

## Principal-engineer posture

This is the bar for every step below — not decoration:

- **Faithful to the plan, skeptical of it.** Implement what the plan actually asks. If the plan contradicts itself or the repo's documented constraints, stop and surface it — do not paper over it in code.
- **Test-first (TDD) whenever possible.** Write the failing test that fails for the right reason before the implementation — by default, not only where the project mandates it. Skip TDD only for changes with no testable behavior (docs; generated output whose generator inputs are what get tested), and name each skipped case and its reason in the final report. Behavior changes ship with tests in the same change, and tests meet the same clean-code bar as production code.
- **Clean code.** Small, single-purpose functions at one level of abstraction; intention-revealing names; no duplication *introduced by the change* — extract logic you would otherwise copy (deliberate test duplication that keeps a case readable is fine); comments only for the non-obvious *why*.
- **Clean architecture.** Preserve the repo's established dependency structure; where it defines layering rules, keep dependencies pointing inward, define interfaces at the consumer boundary, and keep domain logic free of transport/DB/framework concerns; new code lands in the package that owns the concern.
- **Standard design patterns.** Prefer well-known patterns (Ports & Adapters, Strategy, Repository, Functional Options, …) over bespoke abstractions — but only where an abstraction removes real duplication or isolates a dependency. Name the pattern in the report/PR so reviewers recognize it; never contort code identifiers or comments to carry the pattern name.
- **Idiomatic style.** Precedence: documented repo rules, then the surrounding code's established idiom, then the language community's conventions (Effective Go, PEP 8, …) — in production code and tests alike, without cleaning up unrelated legacy code.
- **Minimal and local.** Smallest change that satisfies the plan; no speculative abstraction, no scope creep beyond the plan. If meeting a documented repo constraint would force a refactor wider than the plan's scope, stop and ask — neither creep the scope silently nor ship structure you know is wrong.
- **Safety and correctness over convenience** when the domain is safety-critical — follow the repo's failure-direction and error-handling rules exactly.

## Subagent delegation

Run expensive, self-contained work in **`general-purpose` subagents** (via the `Agent`/`Task` tool) and keep orchestration in the main loop. The split is fixed:

- **Main loop owns** (never delegate):
  - Every `AskUserQuestion` gate (subagents cannot prompt the user): a missing/unreadable plan file, a detached/default-branch `HEAD`, or a dirty tree with unrelated changes (Step 0), an ambiguous or self-contradicting plan (Step 2), an implementation fork with real trade-offs (Step 3), an ambiguous or invasive review fix (Step 5c), a failing gate unrelated to the change (Step 6), and the pre-push confirmation (Step 7).
  - **Invoking skills** (`/simplify` in Step 4, `/codex-review` in Step 5) — the Skill tool runs in this conversation and cannot be launched from inside a subagent.
  - The task-group dependency analysis and the decision of what may run in parallel (Step 3).
  - Merging subagent results and resolving conflicts between them. In Step 5 the adjudication batches run in subagents that gather evidence and *recommend* a disposition; the main loop makes the final accept/reject/defer call.
  - The final commit/push (Step 7) and the Step 8 report.
- **Delegate to `general-purpose` subagents** (each returns a compact result):
  - **Step 1** — read the plan, `CLAUDE.md`, the nearest existing package code/tests, and any docs the plan cites; return a structured brief. Keeps the bulky reading out of the main context.
  - **Step 3** — implementation of independent task groups (see the parallelism rules below).
  - **Step 5** — the codex review run, and the adjudication batches.
  - **Step 6** — the gate run (`task ci`, etc.), returning pass/fail plus only the failing output.

Give each subagent a self-contained prompt: the plan file path, the exact scope limits, the commands to run, the principal-engineer posture standards, the TDD requirement, and the precise result shape to return (changed files, red-then-green test evidence, anything it deliberately left out).

**Parallelize by default where there is no data dependency**, dispatching the concurrent calls as multiple `Agent`/`Task` calls in a **single message**. Step 1's reads are independent — fan them out. Step 5's adjudication batches are independent — fan them out. Step 3's parallelism is conditional and is decided explicitly in that step.

## Step 0 — Resolve the plan file and the working state

1. **Resolve `<plan-file>`.** If the argument is omitted or the path does not exist, stop and ask via `AskUserQuestion` which plan to implement (offer the markdown files you can find under likely plan locations — `specs/`, `docs/plans/`, `plans/`, repo root). Never guess between candidates.
2. **Resolve the remote, the default branch, and `<base>`.** Pick the remote first — prefer the one Step 7 will push to (`branch.<current-branch>.pushRemote` → `remote.pushDefault` → the current branch's upstream remote → `origin` → the sole remote), and ask when more than one plausibly applies. Resolving a different remote here than Step 7 pushes to would guard the wrong branch.

   Ask the remote itself for its default branch rather than trusting a possibly-stale local ref:
   ```bash
   git fetch --quiet "<remote>"                      # refresh remote-tracking refs first
   git ls-remote --symref "<remote>" HEAD            # authoritative: "ref: refs/heads/<default> HEAD"
   git symbolic-ref --short "refs/remotes/<remote>/HEAD"   # local mirror; may be stale or unset
   ```
   Take `<default-branch>` from `ls-remote --symref`, and set `<base>` to the **remote-tracking ref** `<remote>/<default-branch>` (freshly fetched) — never a local `main`, which can sit far behind. If the remote is unreachable, fall back to a local `main`/`master` only after saying so, and treat `<base>` as possibly stale; if nothing resolves at all, stop and ask which branch is the base rather than falling through with an empty `<base>`.

   When you do derive `<default-branch>` from a `<remote>/…` ref, strip **only** the exact `<remote>/` prefix — keep every remaining slash, so `origin/release/stable` yields `release/stable`, not `stable`. A wrong `<default-branch>` silently disables the default-branch push safeguard.

   Every `<placeholder>` in this skill's commands is a value you substitute, not a shell variable. **Quote each one in every command you actually run** — the snippets below show quotes where the value is substituted, and ref names legitimately contain `$`, backticks, and `;`, so an unquoted substitution turns a branch name into shell code. Use `--` before pathspecs.
3. **Confirm the branch and pin the starting point.** Run `git branch --show-current` and record the result as `<current-branch>`, and `git rev-parse HEAD` as `<starting-commit>` — the branch and tip this skill is bound to for the whole run. `<starting-commit>` is what Step 6 reproduces pre-existing failures against, and the expected tip for every drift check: a commit, reset, or rebase on the same branch keeps the name identical, so the branch name alone proves nothing. Advance the expected tip only for commits this skill makes. It never creates a branch or worktree without explicit user approval; it may create one only when the user selects that option below.
   - Empty output means detached `HEAD`: stop and ask via `AskUserQuestion` whether to create a branch here or abort. Never implement on a detached `HEAD` — there is nothing to push.
   - If it equals `<default-branch>`, stop and ask whether to create a feature branch first, proceed on the default branch anyway, or abort. Pushing straight to the default branch is almost never intended.
4. **Check the tree.** Record every dirty path — staged, unstaged, and untracked — as the **pre-existing dirty set**; Step 7 must not commit it by accident:
   ```bash
   git status --porcelain=v1 -z -uall
   ```
   Parse the `-z` stream by record, not by "one path per NUL": an ordinary record is `XY <path>\0`, but a rename or copy (`R`/`C`) is `XY <new-path>\0<old-path>\0` — two fields. Keep **both** paths of a rename in the dirty set; treating the source path as a separate record corrupts the set and every allowlist derived from it.

   Then gate on it before writing any code:
   - **Any pre-existing dirty path that the plan will touch → stop.** Ask to commit it, stash it, or abort. Once your edits interleave with someone else's hunks in one file, path-based staging can no longer separate them.
   - **Anything staged in the index → stop.** Ask to commit or stash it. Working around a pre-loaded index means silently rewriting the user's staging state, and this skill will not restore it.
   - **Dirty paths disjoint from the plan's targets, unstaged only** → recommend commit or stash, and offer "keep them and proceed" only with the full consequences stated: they stay out of the commit, the codex working-tree review will see them, and **Step 6's whole-branch gates run over them too** — a repo-wide formatter will rewrite them, and a lint/build/test failure they cause is not yours to fix. If the user keeps them, scope the format gate to the allowlisted paths rather than the whole tree, and attribute any failure in those files to the retained changes instead of to the plan.

   **Re-run `git status --porcelain=v1 -z -uall` after any remediation and record the pre-existing dirty set from that result**, immediately before Step 3's first edit. A path that was committed or stashed is clean now and must not stay on the exclusion list — otherwise Step 7 would drop this plan's own changes to that file.

## Step 1 — Build the implementation brief (parallel subagents)

Delegate a read-only pass that returns everything needed to implement without re-reading mid-flight:

- Read `<plan-file>` in full.
- Read `CLAUDE.md` and any ADRs, specs, tickets, or sibling docs the plan cites.
- For each task group in the plan, identify the package(s) and files it will touch and the nearest existing code and test patterns to mirror.

Fan these reads out across parallel reader subagents in one message; they share no state.

The subagents return, and the main loop assembles: the **ordered task-group list**, the per-group target files, the conventions that bind (layering rules, TDD requirement, logging/observability gates, safety rules), and — since a plan file has no `validation.md` — an explicit **acceptance checklist** derived from the plan (what must be true and how each item is proven). That brief is the plan of record.

## Step 2 — Reconcile the plan with the repo's rules before writing code

With the brief in hand, sanity-check it as a principal engineer would:

- Is every task group actually specified well enough to implement, or does it hand-wave a decision?
- Does the plan contradict itself, or a documented constraint (layering, dependency policy, safety direction)?
- Is the acceptance checklist sufficient to prove the plan is done, and is each item testable as written?

If you find a genuine contradiction, a missing decision, or an underspecified group, **stop and surface it via `AskUserQuestion`** before writing code. Never offer "violate the documented repo rule" as an option — the repo's rules are authoritative. The real options are: amend the plan to a compliant approach, pick among compliant implementations, narrow or defer the conflicting group, or abort. Batch related questions into a single `AskUserQuestion` call rather than interrogating the user one item at a time. Implementing through a known contradiction is the one thing a principal engineer does not do silently.

## Step 3 — Implement the plan, with parallel subagents where safe

First, in the main loop, classify the task groups from the brief:

- **Dependent groups** — a group that builds on an earlier group's code, or that shares a mutable artifact with another group (lockfiles, codegen output, migrations, golden files, a public API surface, the same source file). These run **serially, in plan order**.
- **Independent groups** — disjoint files, disjoint packages, no shared mutable artifact, no ordering requirement. These may run **concurrently**, each in its own `general-purpose` subagent, dispatched in a single message.

When in doubt, treat a group as dependent — a race through shared artifacts costs far more than the wall-clock it saves. Never parallelize two groups that touch the same file.

For each group, whether run in the main loop or in a subagent, the loop is the same:

1. **Test first (TDD)** whenever the group changes behavior a test can express: write the failing test(s) that fail for the right reason, asserting against the plan's acceptance checklist. Verify they fail before implementing — and that the failure is the new test, not a pre-existing red in the package. Follow the repo's test idioms (e.g. table-driven cases named for the boundary they exercise).
2. **Implement** the smallest change that makes the tests pass and satisfies the plan. Stay inside the package that owns the concern; obey the layering/import rules from the brief.
3. **Refactor** locally once green, applying the posture's clean-code, pattern, and idiom standards to the changed code. Add the doc comments the repo requires on new exported identifiers.
4. **Run the touched package's tests** (e.g. `go test ./that/pkg -race -count=1`, or the repo's equivalent) before reporting done, so no group is stacked on a red one. This is a fast local check, not verification — the full format/lint/build/test sweep in Step 6 still runs over the whole branch.

After a parallel batch returns, the main loop **integrates**: read each subagent's diff summary, resolve any overlap or duplicated helper the subagents each introduced, and run the tests for all touched packages together before starting the next batch. Concurrent subagents share one working tree, so they *can* see each other's half-written files — which is exactly why none of them may depend on another's in-flight edits, and why the disjoint-file rule above is absolute. Integrate only once every worker in the batch has finished; that reconciliation is the main loop's job, not an optional cleanup.

Because that tree is shared, **re-check both the branch name and the tip** — `git branch --show-current` against `<current-branch>`, and `git rev-parse HEAD` against the expected tip (`<starting-commit>`, plus any commit this skill has made since) — after each batch, and again before review, verification, staging, each commit, and the push. A subagent, a hook, or the user in another terminal can move `HEAD` without changing the branch name; if either differs, stop and ask rather than building on top of it.

When a single implementation choice is genuinely ambiguous and the alternatives trade off (an API shape, sync vs async, where a seam goes), stop and ask via `AskUserQuestion` rather than guessing — but only for real forks, not routine decisions a principal engineer just makes. A subagent that hits such a fork must **stop and return the question** rather than guessing; the main loop asks the user and re-dispatches with the answer.

Keep edits minimal and traceable to a task group. Do not implement beyond the plan's scope; note any out-of-scope idea for later instead of building it.

## Step 4 — Simplify the changed code (`/simplify`)

Once the implementation is functionally complete and the touched-package tests pass, invoke the **`/simplify`** skill (via the Skill tool, in the main loop — the Skill tool cannot be launched from inside a subagent) to clean up the new and modified code for reuse, simplification, efficiency, and altitude. `/simplify` is a quality pass only — it does not hunt for bugs (that's Step 5) — and it applies its cleanups directly to the working tree. Let it finish before reviewing.

This pass matters more here than in a serial implementation: parallel subagents cannot see each other's work, so the most likely defect is duplicated helpers or two near-identical shapes introduced by different batches. Give `/simplify` the full list of changed files, not just one batch's.

Then read your own diff once (`git diff`, plus untracked files) for what `/simplify` does not target: dead code, debug prints, stray TODOs, inconsistent naming. Fix what you find — a reviewer's time is better spent on substance.

If `/simplify` is unavailable in this environment, say so in the Step 8 report and do the reuse/simplification pass yourself against the posture's clean-code standards; do not silently skip it.

## Step 5 — Independent review: codex first, adversarial subagents as fallback

**Record the review file list first** — everything below refers to it. It is the union of the working-tree changes and the branch delta, minus the Step 0 pre-existing dirty set:

```bash
git status --porcelain=v1 -z -uall                            # staged + unstaged + untracked
git diff --name-status -z --find-renames "<base>"...HEAD      # branch delta, with status letters
```

Use the NUL-delimited forms — plain `--name-only` drops the status letter and reports only a rename's destination, and default status output collapses untracked directories and mangles unusual filenames. Keep renames as **both** paths and mark deletions explicitly; a reviewer needs to know a file went away. Do not silently drop generated files, vendored code, or lockfiles that the plan itself changed — if you exclude anything, say which and why in the Step 8 report.

If Step 0 left disjoint unstaged dirt in the tree, codex's working-tree review will include it (that mode reviews the whole tree and takes no allowlist). Say so when presenting findings, and reject any finding that lands on a pre-existing dirty path rather than on this plan's work.

### 5a — Try codex

Check availability first: `command -v codex`.

**If the repo/user has the `/codex-review` skill installed, prefer it** — it already owns the launch, liveness, adjudication, fix, and verification contract end to end. Invoke it via the Skill tool in the main loop, tell it the scope you need (the union above; answer its scope question with "union" rather than letting it pick), then **skip Steps 5b and 5c entirely and go to Step 6** — re-adjudicating and re-fixing findings it already handled would duplicate its work. Carry its disposition table into the Step 8 report. If it reports codex unavailable and hands back, run 5b here.

Otherwise drive codex yourself from the repo root, in a subagent so the transcript stays out of the main context. The `/codex:*` entries are Claude Code slash commands with `disable-model-invocation: true` — **you cannot call them, and they are not shell commands**. Run the companion script the plugin wraps:

```bash
# Resolve the script once (version dir varies; sort -V so 1.0.10 beats 1.0.9):
COMPANION=$(ls -d ~/.claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs 2>/dev/null | sort -V | tail -1)

node "$COMPANION" review "--background --scope working-tree"   # uncommitted changes
node "$COMPANION" review "--background --base <base>"          # branch delta
node "$COMPANION" status <job-id> --wait                       # poll (4-min bounded waits)
node "$COMPANION" result <job-id>                              # findings
node "$COMPANION" cancel <job-id>                              # abandon
```

Launch with `run_in_background: true`. If `$COMPANION` does not resolve (plugin not installed), fall back to a direct one-shot run in the subagent — `codex exec --sandbox read-only "<review prompt naming the file list>"` — and if `codex` itself is absent, go straight to 5b.

**When both scopes are non-empty, launch both jobs in the same message** (they are independent), give each its **own** scratch file so the parallel writes don't clobber one path, await both job IDs, then merge the findings and dedupe overlaps by `file:line`. Save every result verbatim to its scratch file (e.g. `/tmp/implement-plan-review-<slug>-working-tree.md`, where `<slug>` is the branch with `/` replaced by `-`, or just use `mktemp`) so the adjudication is auditable. Do not commit those files.

**Enforce a deadline and a liveness check** — codex is the second opinion, never the critical path:

- Hard deadline: **10 minutes**.
- Treat the job as **dead now** if its recorded `pid` is not alive (`ps -p <pid>`) while status still says `running`.
- Treat it as **stalled** if its log file has been silent for **5+ minutes**.

On death, stall, or deadline: run the companion's own `cancel <job-id>` and go to 5b. Do not hand-delete files under the plugin's state directory — the companion owns that index, and a stray `rm` there breaks later jobs. Do not retry codex and do not ask whether to retry — the fallback is deterministic and costs less than a second stall.

### 5b — Fallback: adversarial subagent review

If codex is not installed, its launch fails, or the liveness check fires, **do not skip the review** — run it natively, without asking. Fan out **2–3 adversarial `general-purpose` subagents in a single message**, each with a distinct lens over the review file list recorded above and the Step 1 project rules:

- **correctness / invariants** — does the code do what the plan says, at every boundary?
- **error handling / silent failure / fallback behavior** — what failure gets swallowed?
- **test coverage / edge cases** — what does the plan require that no test proves?

Instruct each to cite `file:line` and to *verify* every claim against the actual code — no hypotheticals, no style opinions that contradict the repo's conventions. If the repo ships specialized review agents (e.g. `pr-review-toolkit`'s `silent-failure-hunter`, `type-design-analyzer`, `pr-test-analyzer`), prefer the ones that fit the diff and dispatch them concurrently.

Proceed with the fallback without asking, and record in the Step 8 report that the review came from the native fallback and why (codex absent / launch failed / dead pid / stalled / deadline).

### 5c — Validate every finding, then fix (the load-bearing step)

Do **not** apply review comments blindly — they are hypotheses to adjudicate, whatever their source. Split the findings into disjoint batches (~3–5 each; contradictory findings share a batch so one subagent resolves the conflict) and fan out one adjudication subagent per batch in a single message. Each subagent gathers the evidence and **recommends** a disposition; the main loop merges the slices and makes the final call. For each finding:

1. Open the actual code at the cited location and confirm the issue is real.
2. Check it against the project rules from Step 1 and the plan's scope.
3. Mark a disposition:
   - **accept** — real issue, fix warranted; note the evidence.
   - **reject** — factually wrong, already handled elsewhere, or contradicts a documented project rule; note why with a file/line citation.
   - **defer** — real but out of scope for this plan (pre-existing issue, needs a wider refactor); note where it should go instead.

Scrutinize the classic external-reviewer failure modes: findings about code that doesn't exist, style opinions that contradict the repo's conventions, suggestions to add dependencies the project gates behind a decision record, and "fixes" that would break a documented invariant.

Present the merged disposition table to the user, then fix every **accepted** finding — with two exceptions that require `AskUserQuestion` first: **ambiguous** findings (more than one reasonable fix, trading off differently) and **invasive** fixes (touch files outside the scope, change a public API, add a dependency). Rejected and deferred findings get no code changes — they live only in the table.

## Step 6 — Verify: format, lint, build, test

**Run all four gates, in this order, over the whole branch** — the combined result of implementation + `/simplify` + review fixes. Not the touched packages, not a subset: the branch as the project itself builds and tests it.

| # | Gate | Must do | Typical commands |
|---|------|---------|------------------|
| 1 | **Format** | Apply the repo's formatter, **then** run its check mode and confirm nothing is left unformatted | apply: `task fmt` · `gofmt -w .` · `npm run format` · `cargo fmt` · `ruff format` — then check: `gofmt -l .` · `cargo fmt --check` · `ruff format --check` |
| 2 | **Lint** | Static analysis clean, at the repo's configured strictness | `task lint` · `golangci-lint run` · `npm run lint` · `ruff check` |
| 3 | **Build** | The whole project compiles/bundles, not just changed packages | `task build` · `go build ./...` · `npm run build` · `cargo build` |
| 4 | **Test** | The **full** suite, every package, with the repo's standard flags | `task test` · `go test ./... -race -count=1` · `npm test` · `pytest` |

Find the real commands in the repo — its `CLAUDE.md`/README, CI config, task file, and the package manager its lockfile implies — and prefer those over the generic examples above. Run format **before** lint and build: a formatter that rewrites files after a green lint invalidates the run.

An aggregate target (`task ci`, `make ci`) is a shortcut only once you have **read its definition and confirmed it covers all four**. `make test`, `npm test`, and friends are *test* targets — they usually do not format, lint, or build; a green `npm test` is not a green branch. When no aggregate target covers everything, run the four individually.

Delegate the gate run to a subagent that returns, per gate, pass/fail plus only the failing output.

**Each gate ends in exactly one of three states**, and Step 8 reports which:

- **pass** — the command ran and was clean.
- **fail** — the command ran and was not clean.
- **not configured** — the repo genuinely has no such gate (no formatter, no linter, no build step for an interpreted project). Search before concluding this; then report `command: N/A — not configured`. A not-configured gate does **not** block Step 7, but it is never described as green.

If a gate fails because of the change, fix forward (looping back through the relevant step) and **re-run all four** — a fix for a lint failure can break a test. Never hand off or commit red.

If a gate looks like a **pre-existing red**, prove it before believing it: reproduce the exact failing command against the branch's starting commit in a throwaway worktree, so your own changes are absent —

```bash
git worktree add --detach "<tmp-path>" "<starting-commit>"   # <starting-commit> pinned in Step 0
# run the same gate command there, then:
git worktree remove "<tmp-path>"
```

If it fails there too, it is pre-existing: stop and ask via `AskUserQuestion` whether to **fix it**, **abort**, or **commit with a documented waiver**. If it passes there, the failure is yours — fix it. If you cannot reproduce either way, treat causation as unresolved and say so; do not offer the waiver as though the failure were proven pre-existing. The waiver is the only path that commits on a red gate: it needs the user's explicit choice, and Step 8 must then name the failing gate instead of claiming the result is green.

Then walk the Step 1 acceptance checklist against what now exists: each item present, each named test passing, each behavior demonstrable. If any item is unmet, the plan is not done — return to Step 3 for the gap. Only proceed when every item is satisfied or the user has explicitly accepted a documented deferral.

## Step 7 — Commit and push

Enter this step only when Step 6 has closed out: every gate green and every checklist item satisfied, or the user has explicitly waived a specific red gate / accepted a documented deferral. Either way, what was waived or deferred is named in the Step 8 report and never implied to be green.

0. **Re-check the branch** — `git branch --show-current` must still equal the Step 0 `<current-branch>`. If it moved, stop and ask.
1. **Build an explicit path allowlist per commit.** The full allowlist is the files this plan's work touched, minus the Step 0 pre-existing dirty set and any review scratch file. If the plan landed as distinct slices you intend to commit separately, split that allowlist into **disjoint per-commit lists** first and run this staging/commit cycle once per slice — staging everything and then committing repeatedly does not produce separate commits. Never `git add -A`:
   ```bash
   git --literal-pathspecs add -- "<path>" "<path>"…
   git status --porcelain     # confirm nothing unintended is staged
   git diff --cached          # the commit's actual content (plain `git diff` omits staged work)
   git diff --cached --check  # whitespace/conflict-marker errors
   ```
   Quote every path and pass `--literal-pathspecs`: a filename containing `*`, `:`, or a leading `!` is a pathspec pattern to git and can pull in files outside the allowlist. Read the staged diff before committing; if anything unintended is in the index, unstage it (`git --literal-pathspecs restore --staged -- "<path>"`) and re-check. If the index is empty, stop — there is nothing to commit and something upstream went wrong. After the last slice, confirm the union of the commits equals the intended change and nothing is left behind.
2. Commit following the **repo's own commit conventions** — match the recent `git log` message style (ticket-key prefixes, Conventional Commits, whatever the log shows) and include any trailers the environment or repo requires.

   **After each commit, check what the hooks did**: `git show --stat HEAD` and `git status --porcelain`. A `pre-commit` hook can reformat or re-stage files, so the committed tree may not be the tree Step 6 verified. If a hook changed content, re-run the four gates over the new state before committing anything further or pushing.
3. **Resolve the push target, then confirm it before pushing.** Pushing is outward-facing and hard to walk back, so always show the destination and get explicit confirmation via `AskUserQuestion` — not only when something looks ambiguous:
   ```bash
   git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null   # empty = no upstream
   git config --get "branch.<current-branch>.pushRemote"                       # overrides the fetch remote
   git config --get remote.pushDefault                                         # repo-wide override
   git remote get-url --push --all "<remote>"                                  # every URL it will hit (pushurl can be multi-valued)
   ```
   A bare `git push` is not self-explanatory — `branch.<name>.pushRemote`, `remote.pushDefault`, and `push.default` can all redirect it. Resolve one concrete `<remote>` (pushRemote → pushDefault → upstream's remote → the sole remote → ask). If that remote differs from the one Step 0 resolved, **re-resolve its default branch, recompute `<base>` against it, and repeat the default-branch confirmation** — the earlier safeguard and every base-relative figure below were computed against a different remote.

   Then fix `<dest-branch>`, the branch name on the remote: the existing upstream's branch when one is set (it need not match the local name), otherwise `<current-branch>`.

   **Show what will actually travel** before asking. Probe the destination explicitly rather than trusting a possibly-stale tracking ref:
   ```bash
   git ls-remote --exit-code --heads "<remote>" "refs/heads/<dest-branch>"
   #   exit 0  → destination exists
   #   exit 2  → destination absent (new branch will be created)
   #   other   → transport/auth error: stop, do not guess
   git fetch "<remote>" "<dest-branch>"                 # required when it exists; do not silence errors
   git log --oneline "<remote>/<dest-branch>..HEAD"     # exact outgoing commits; empty = nothing to push
   ```
   Never suppress the fetch's exit status — a failed fetch leaves a stale ref and turns the outgoing-commit list into fiction. On any transport error, stop and ask instead of confirming a destination you could not read.

   Present the remote, the destination ref, the push URL(s), and that commit list — a branch can carry local commits the user forgot about, and confirming "push this branch" is not consent to publish those unseen. **Redact credentials before displaying a URL**: an HTTPS remote may embed `user:token@`, so show `https://***@host/path`, never the raw userinfo. If the destination does not exist, say plainly that a **new remote branch will be created** and list the commits relative to `<base>`. If the push would not be a fast-forward, stop and ask — never reach for `--force` on your own.

   Then push with an explicit refspec:
   ```bash
   # No upstream yet — set it:
   git push -u "<remote>" "HEAD:refs/heads/<current-branch>"
   # Upstream already exists — push to ITS destination branch, and omit -u so it is not silently repointed:
   git push "<remote>" "HEAD:refs/heads/<dest-branch>"
   ```
   Only use `-u` when no upstream exists, or when the user explicitly approves repointing an existing one.

   For the default branch, or a branch the repo's rules mark protected, require a second explicit confirmation on top of the Step 0 one — git cannot read remote protection rules locally, so the user's answer is the only gate. Do not open a PR unless the user asks — pushing the branch is where this skill stops.
4. **Verify the push landed on the server**, then report exactly what happened. Compare against the remote itself, not a local tracking ref that a custom fetch refspec may never update:
   ```bash
   git ls-remote --exit-code --heads "<remote>" "refs/heads/<dest-branch>"   # server's OID
   git rev-parse HEAD                                                        # must equal it
   git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}'
   ```
   When the remote has multiple push URLs, check each one — a push can succeed on the first and fail on the second.
   If the user declines the push confirmation, or the push fails, the work is **committed locally, not pushed** — say that in Step 8 and never claim an upstream was set.

## Step 8 — Report

State, per the repo's handoff checklist if it has one:

- **What changed** — the task groups implemented, in the user's terms, and the files touched.
- **Plan coverage** — each acceptance-checklist item, marked satisfied / deferred (with reason), plus any TDD skips and why.
- **Parallelism** — which groups ran concurrently and which were serialized, and why.
- **Review** — source (codex or the adversarial fallback, with the reason if it fell back), finding count, and the accept/reject/defer breakdown with one-line reasons for rejections.
- **Simplify** — what `/simplify` cleaned up, or that it was unavailable and you did the pass manually.
- **Checks** — each of the four gates by name with the exact command run and its state: **format**, **lint**, **build**, **full test suite** — each `pass` / `fail` / `not configured (N/A)`. Name any waived failure rather than implying green.
- **Commit & push** — the commit(s); then either the remote, destination ref, and upstream verified after a successful push, or plainly "committed locally, not pushed" with the reason.
- **Remaining risk** — deferred items and anything review/verification could not cover, especially around safety, ordering, concurrency, performance, or architecture boundaries.

## Stop-and-ask conditions (use AskUserQuestion; never silently proceed)

- `<plan-file>` is missing, unreadable, or ambiguous between candidates (Step 0).
- `HEAD` is detached, or the current branch is the default branch (Step 0).
- The tree carries uncommitted changes unrelated to the plan (Step 0).
- The plan contradicts itself, a repo constraint, or leaves a decision unmade (Step 2).
- A real implementation fork with trade-offs — including one a subagent returns (Step 3).
- An accepted finding's fix is ambiguous or invasive (Step 5c).
- A verification gate fails for a pre-existing reason unrelated to the change (Step 6).
- Before every push, to confirm the resolved remote and branch (Step 7).

Codex being unavailable, dead, or stalled is **not** a stop-and-ask: fall back to the adversarial subagent review automatically and report it (Step 5).
