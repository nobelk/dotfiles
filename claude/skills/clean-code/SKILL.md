---
name: clean-code
description: Review the current branch's spec and its implementation, then write a simplification plan to simplify-<branch>.md covering clean code, clean architecture, design patterns, idiomatic style, and deduplication across production code, test code, and code organization — clarifying open questions with AskUserQuestion, codex-reviewing the plan and folding in validated findings, then measuring test coverage and closing the high-priority gaps before running the project's format/lint/build/test gates and committing, pushing, and opening or updating the GitHub PR. Invoke manually when a branch's work is functionally complete and you want it cleaned up before review.
---

# Clean-code skill

Take a branch whose work is functionally complete and make it **reviewable**: understand what the spec asked for, read what was actually built, and produce a validated, concrete plan for simplifying it — then lay down the test safety net that plan will need. Output is a finalized `simplify-<branch-slug>.md`, new tests closing the high-priority coverage gaps, a green gate run, and a pushed branch with an open PR.

## What this run changes, and what it does not

This skill **plans** the simplification; it does not carry it out. The refactor is a separate, reviewable change — hand the finalized plan to `/implement-plan` for that.

**By default this run writes exactly two things:** the plan file, and **tests** closing the high-priority coverage gaps.

**Three narrow exceptions may extend that write set, each only when explicitly authorized and each recorded in the plan, the commit, and the PR body:**

1. **Minimal testability seams** in production code — extracting a clock, a port, an interface at the consumer — only where Step 4's plan named one, and only to make a gap closable. Anything larger is a stop-and-ask.
2. **A spec edit**, when Step 3's spec-divergence question resolved that the spec (not the code) is what moved on.
3. **A bug fix**, when Step 7's new test reveals a real bug and the user authorizes fixing it now rather than deferring it.

Nothing else is in scope. Maintain the write set as a single accumulating list from Step 3 onward — Step 8 stages from it, so an authorized change missing from it is an authorized change that silently never ships.

Closing coverage gaps *before* refactoring is the ordering that makes the refactor safe: the tests that catch a behavior-changing "simplification" must exist before anyone simplifies. A plan built on uncovered code is a guess.

If the repo has a `CLAUDE.md` (or `AGENTS.md`), read it in the main loop **before Step 0's git actions** — it is authoritative for conventions, layering rules, testing expectations, commit style, and quality gates, and it overrides anything in this skill or any reviewer suggestion that contradicts it.

## Principal-engineer posture

The plan is only as good as the standards it is written against. These are the axes it must judge the branch on — and the bar the tests this skill writes must themselves meet:

- **Clean code.** Small, single-purpose units at one level of abstraction; intention-revealing names; no duplication introduced by the branch; comments that explain the non-obvious *why*, not the *what*. Dead code, commented-out code, and leftover scaffolding go.
- **Clean architecture.** Dependencies point inward; interfaces defined at the consumer boundary; domain logic free of transport/DB/framework concerns; each change in the package that owns the concern. Where the repo documents layering rules, those rules are the standard.
- **Standard design patterns.** Name well-known patterns (Ports & Adapters, Strategy, Repository, Functional Options, Decorator, …) where one would remove real duplication or isolate a dependency — and say so in the plan, not in code identifiers or comments. Plain code wins when it suffices; an abstraction with one implementation and no seam is a finding *against* the code, not for it.
- **Idiomatic style.** Precedence: documented repo rules, then the surrounding code's established idiom, then the language community's conventions (Effective Go, PEP 8, the Rust API guidelines, …).
- **Deduplication.** Real duplication is repeated *knowledge*, not repeated characters. Two functions that look alike but change for different reasons should stay apart; three call sites re-deriving the same rule should not. Deliberate duplication in tests that keeps a case readable is fine and must not be flagged.
- **Behavior-preserving by default.** Most plan items are refactors: same behavior, better structure. An item that changes behavior is a **correctness item** — label it as such, keep it out of the refactor sequencing, and never smuggle it in as "cleanup".
- **Scoped to this branch.** Judge the code the branch added or changed. Pre-existing mess in untouched files is out of scope; note it as an observation, never as a plan item, unless the branch's own changes made it actively harmful.

## Subagent delegation

Run the read-heavy analysis and the verbose command runs in **`general-purpose` subagents** (via the `Agent`/`Task` tool); keep orchestration, judgment, and every gate in the main loop:

- **Main loop owns** (never delegate): all of Step 0's scope and git resolution; **every `AskUserQuestion` gate** — subagents cannot prompt the user; **writing and rewriting the plan file** (Step 4, Step 5c's finalization, Step 7's reconciliation); the final accept/reject/defer calls in Step 5c; **invoking other skills**, since the Skill tool runs in this conversation and cannot be launched from inside a subagent; the Step 8 commit, push, and PR; and the Step 9 report.
- **Delegate to a `general-purpose` subagent** (each returns a compact result):
  - **Step 1** — read the spec, the branch diff, the surrounding package code, `CLAUDE.md`/ADRs, and the nearest sibling tests; return a structured brief rather than the file contents.
  - **Step 2** — the review passes. Give each subagent **one axis** (clean code, architecture/organization, patterns, idiom, duplication, test quality) over the same changed-file set, and have it return findings as `file:line — observation — why it violates <named standard>`. One axis per subagent keeps each one's judgment sharp and the results easy to merge.
  - **Step 5a** — the codex review run: launch, poll, and return the raw findings verbatim (also written to the scratch file). The codex transcript stays in the subagent.
  - **Step 5c** — split findings into disjoint batches (~3–5 each; contradictory findings share a batch so one subagent resolves the conflict) and adjudicate them in parallel, each returning its slice of the disposition table with evidence. The main loop makes the final call.
  - **Step 6** — the coverage measurement run, returning the per-unit and total numbers plus the least-covered rows, not the raw profile.
  - **Step 7** — writing the planned tests, one subagent per independent unit-under-test.
  - **Step 8's gate run** — returning pass/fail plus only the failing output.

Give each subagent a self-contained prompt: the exact commands, the changed-file list from Step 0, the repo standards it must judge against, and the precise result shape to return. **A delegated subagent that hits a stop-and-ask condition must return a `needs user decision` status to the main loop rather than guessing** — it cannot prompt, and proceeding on its own assumption is the failure this rule exists to prevent.

**Parallelize by default; never parallelize a write conflict.** Dispatch independent work as multiple `Agent`/`Task` calls in a **single message**. Step 1's reads fan out. Step 2's six review axes fan out — they are read-only over the same files, which is exactly the safe case. Step 5c's adjudication batches fan out. Step 7's test-writing fans out **only after a write-set check**: one subagent per test file, and anything touching a shared surface (a shared fixture or helper, a regenerated mock, a manifest, a production seam extraction) lands first in the main loop or a single upstream subagent before the rest go parallel. Step 5a → Step 5c is a genuine producer→consumer chain and stays serial.

## Conventions for every command in this skill

- **Never paste a resolved value into shell source.** Branch names, paths, and remotes can contain `$( )`, backticks, spaces, or a leading `-`. Bind each to a shell variable and use it quoted (`"$current_branch"`), or pass it as an argument — never splice the literal text into a double-quoted command line. Build multi-package/module argument lists as arrays (`"${pkgs[@]}"`), not as a space-joined string.
- **`--` means different things to different tools — do not apply one habit everywhere.**
  - *Git commands that take pathspecs* (`add`, `diff`, `log`, `restore`, `checkout`): `--` separates **pathspecs and nothing else**. Put it before a list of file paths (`git add -- "${paths[@]}"`), and **never put a revision, revision range, remote, or ref after it** — git then reads that argument as a path, which typically "succeeds" with empty output and silently analyzes the wrong thing. Range first, terminator last: `git diff "$base...HEAD" --`, `git log "$oid..HEAD" --`.
  - *Git commands that take no pathspec* (`fetch`, `ls-remote`, `merge-base`, `rev-parse`, `remote`, `worktree`, `push`): no `--` at all. Protect a leading-dash value with `--end-of-options` where the git version supports it, or reject the name outright.
  - *`go test`*: `--` and everything after it are arguments **for the test binary**, so package patterns must come before it — a terminator there silently tests the current directory instead of the named packages.
  - *Non-git tools*: `--` is an ordinary end-of-options marker and is sometimes **required** — notably the codex companion in Step 5a, where the focus text must follow it. Follow each tool's own contract; this bullet is about git and `go test`, not a blanket ban.
- **Check exit status before interpreting output.** Empty stdout from a command that failed means nothing. Every "if this is empty, then …" rule below applies only after the command exited zero.
- **Keep every artifact out of the working tree.** Scratch files, coverage profiles, review output, PR bodies, and temporary worktrees live in a `mktemp -d` directory (`"$tmp"`). Pass each tool's output and cache path explicitly rather than relying on defaults that drop files into the repo. Remove temporary worktrees when done (`git worktree remove --force "$tmp_wt"`).
- **Re-verify the branch and tip before every write, gate, commit, and push.** The tree is shared with subagents, hooks, and the user's other terminals. Compare `git branch --show-current` against `<current-branch>` and `git rev-parse HEAD` against the expected tip (`<starting-commit>`, plus commits this skill has itself made). A checkout, reset, rebase, or outside commit keeps the branch name identical, so the name alone proves nothing. On any unexpected movement, stop and ask — never build on top of it, and advance the expected tip only for this skill's own commits.
- **Check write-target overlap the moment a target becomes known**, not on a fixed schedule — see Step 0.7. The write set grows in Steps 3, 4, 6, and 7, and each new target must be cleared against the pre-existing dirty set (Step 0.7) *before its first edit*.

## Step 0 — Resolve scope: the branch, its base, and what it changed

1. **Resolve the identities separately.** Conflating them is how work lands on the wrong branch or in the wrong repository. Resolve and record each:
   - `<current-branch>` — the local branch (`git branch --show-current`). Empty means detached `HEAD`: stop and ask; there is nothing to push.
   - `<push-remote>` — where Step 8 pushes: `branch.<current-branch>.pushRemote` → `remote.pushDefault` → the current branch's upstream remote → `origin` → the sole remote. Ask when more than one plausibly applies.
   - `<dest-branch>` — the branch name **on `<push-remote>`**. Default to `<current-branch>`. Adopt an upstream's branch name only when that upstream is on `<push-remote>` itself: an upstream pointing at a *different* remote says nothing about where this push lands, and inheriting its name is how a push ends up on the wrong branch. Show the resolved destination and confirm it.
   - `<default-branch-name>` and `<base>` — below.
   - `<pr-repo>`, `<pr-head>`, `<pr-base>` — resolved in Step 8, because a push remote can be a fork and `gh` can select a different repository than git does. When `<push-remote>` is a fork, resolve `<pr-base>` **before** computing `<base>` below and use the PR base for both: reviewing against the fork's default branch while the PR targets upstream's would review the wrong delta.
2. **Resolve two distinct refs, and do not let one stand in for the other.** `<default-branch-name>` on `<push-remote>` is what Step 0.4 guards the destination against. The **review base** — what the branch's changes are diffed against, and what the PR will merge into — is `<pr-base>` in `<pr-repo>`, which for a fork is *not* the fork's default branch. Resolve both; when `<push-remote>` is a fork, fetch and pin the base from `<pr-repo>`'s default branch (adding it as a remote, or fetching by URL, if no remote points there), and say which repository the base came from. The commands below show the common non-fork case, where the two coincide; substitute the PR repository's remote and branch for the base when they do not.
   ```bash
   git ls-remote --symref "$push_remote" HEAD   # "ref: refs/heads/<default-branch-name>	HEAD"
   git fetch "$push_remote" "+refs/heads/$default_branch_name:refs/remotes/$push_remote/$default_branch_name"
   base_oid=$(git rev-parse --verify "refs/remotes/$push_remote/$default_branch_name^{commit}") || stop
   git merge-base "$base_oid" HEAD || stop
   ```
   Fetch the **exact ref with an explicit refspec**: a plain `git fetch` honours the configured refspec, which in a single-branch or narrowed clone may not cover the default branch at all — so a bare fetch succeeding, and even the ref existing, is no proof it is current. Pin `<base>` to `$base_oid` and use that OID everywhere downstream, so a concurrent fetch cannot move the base mid-run. In the fork case `$base_oid` must come from `<pr-base>` in `<pr-repo>`; the push remote's own default branch is then used **only** for the Step 0.4 destination guard. If `rev-parse` or `merge-base` fails, stop and ask which branch is the base; an unresolved base makes the diff below fail, and a failed diff is **not** "nothing changed". When deriving `<default-branch-name>` from a `<remote>/…` string, strip **only** the exact `<remote>/` prefix, keeping every remaining slash (`origin/release/stable` → `release/stable`). If the remote is unreachable, fall back to a local `main`/`master` only after saying so and treating the base as possibly stale.
3. **Pin the starting point.** Record `<starting-commit>` (`git rev-parse HEAD`).
4. **Guard the destination, not just the local name.** Stop and ask if `<dest-branch>` is the default or a protected branch **of the repository being pushed to** — a local branch named `feature` whose destination resolves to `main` passes a local-name check and still publishes to the default branch. Check the resolved destination against `<default-branch-name>` (and the repo's protected-branch list where `gh` can report it) before any commit or push. A local branch equal to `<default-branch-name>` is likewise a stop: this skill commits and opens a PR, and neither belongs on the default branch.
5. **Derive `<branch-slug>`** — `<current-branch>` with every `/` replaced by `-` (so `feat/auth-revamp` → `feat-auth-revamp`). The plan file is `simplify-<branch-slug>.md`; the raw branch name would make `simplify-feat/auth-revamp.md` a path into a directory that does not exist. This normalization is **lossy**: `feat/auth` and `feat-auth` collapse to the same filename, so Step 4 checks for an existing file and records the exact original branch name inside the plan.
6. **Compute the changed set** — the entire review scope:
   ```bash
   git diff --name-status -z --find-renames "$base_oid...HEAD" -- > "$tmp/changed.z" || stop
   git diff --stat "$base_oid...HEAD" --
   ```
   Three dots (diffing against the merge-base), never two — the two-dot form also reports everything the base gained since the branch diverged, which this branch did not write and this skill must not plan to change. The range goes **before** the `--`; after it, git reads it as a path and returns a successful empty result, which would look exactly like "nothing to simplify". Parse the **NUL-delimited** output, not the default: plain `--name-status` escapes unusual filenames and would silently mangle them. Handle every status explicitly — `A`/`M`/`T` are in scope (a type change still changes behavior); `D` removes that *file* from the coverage denominator in Step 6, though its unit survives if other production files remain; `R` carries **two** paths — record both, since the old path is what existing tests and docs still reference. An unrecognized status is a stop, not something to skip. If the diff fails, stop; if it succeeds and is empty, report that there is nothing to simplify and stop.
7. **Check the tree, and keep checking it.** Record every dirty path — staged, unstaged, untracked — as the **pre-existing dirty set**:
   ```bash
   git status --porcelain=v1 -z -uall
   ```
   - **Anything staged** → stop and ask to commit or stash it. Working around a pre-loaded index silently rewrites the user's staging state, and this skill will not restore it.
   - **A dirty path that this run will write to** → stop and ask to commit, stash, or otherwise resolve it. Do **not** offer "keep and proceed" here: Step 8 stages the write set *minus* the pre-existing dirty set, so a retained dirty write target would have this skill's own work silently dropped from the commit. The write set is not known all at once — it grows as the plan path is chosen (Step 4), a spec edit is authorized (Step 3), gaps map to test files (Step 6), and seams or bug fixes are authorized (Step 7) — so **run this check against each new target the moment it is known, before its first edit**, not once at a fixed point.
   - **Dirty paths disjoint from the write set, unstaged only** → recommend commit or stash; offer "keep and proceed" only with the consequence stated: they stay out of the commit, but **Step 8's gates run over them too**, so a repo-wide formatter will rewrite them and any lint/build/test failure they cause is not this branch's to fix. If the user keeps them, scope the format gate to the write set rather than the whole tree, and record the retained paths — Step 8 needs them to attribute failures correctly.
   Re-run the status command after any remediation and re-record the set — a path since committed or stashed is clean now and must not stay on the exclusion list.

## Step 1 — Read the spec and the implementation

Fan these reads out in a single message; they have no data dependency.

**The spec** — what the branch was *supposed* to do. Look, in order, for: `specs/<current-branch>/` or `specs/<branch-slug>/` (the `requirements.md` / `plan.md` / `validation.md` trio this repo's `/feature-spec` writes), a plan file named in the branch's commit messages, a linked issue or PR body. A roadmap entry is context, **not** an acceptance spec — do not substitute one for a missing spec.

If no spec is found, **stop and ask** via `AskUserQuestion` before proceeding: the user may know where it lives, or may confirm there is none. Offer: point me at it (free-text path), review against the linked issue/PR instead, or proceed on repo standards alone. Only the last option drops the spec axis, and choosing it is an explicit acknowledgment that this part of the review cannot be completed — the Step 9 report and the PR body must both say so. Never invent a spec to review against.

**The implementation** — the changed files in full, not just the diff hunks: a function is hard to judge through a keyhole. Read the surrounding package too, since "is this idiomatic here" and "does this duplicate something" are both questions about context.

**The standards** — `CLAUDE.md` / `AGENTS.md` and every architecture, convention, or ADR document they cite; the nearest existing tests, to learn the repo's test idiom (table-driven? generated mocks? which assertion style?) before proposing any test.

Produce a brief: what the spec asked for, what was built, and where the two visibly diverge. **Spec divergence is a finding in its own right** — code that cleanly implements the wrong thing is not clean code — but it is a *correctness* finding, so label it as such and keep it out of the behavior-preserving refactor items.

## Step 2 — Review across all six axes

Run one review pass per axis over the changed set (fan them out; see the delegation rules). Every finding is `file:line — what — which standard it violates — why it matters here`. A finding with no named standard behind it is a preference, and preferences do not go in the plan.

1. **Clean code** — unit size and single responsibility, mixed abstraction levels, naming, magic values, dead or commented-out code, comment rot, error handling that swallows or obscures, boolean/positional parameters that should be a type.
2. **Clean architecture** — layering or dependency-direction violations, domain logic leaking transport/DB/framework concerns, interfaces defined at the implementer instead of the consumer, a concern landing in the wrong package.
3. **Design patterns** — where a named pattern would remove real duplication or isolate a dependency, **and** the reverse: speculative abstractions, one-implementation interfaces with no seam, indirection that costs more than it saves.
4. **Idiomatic style** — deviations from documented repo rules first, then from the surrounding code's idiom, then from the language community's conventions. Include the language's own traps (unchecked type assertions, ignored errors, misused concurrency primitives, mutable default arguments).
5. **Deduplication** — repeated *knowledge*: the same rule re-derived at several call sites, copy-pasted blocks that must change together, parallel switch statements over the same type. Distinguish this explicitly from code that merely looks similar and changes for different reasons.
6. **Test code and code organization** — tests are held to the same bar as production code. Unclear or misleading test names, assertions that cannot fail, tests coupled to implementation detail rather than behavior, missing boundary cases, non-hermetic or non-deterministic tests (wall-clock reads, real network, ordering dependence, shared mutable state), fixture duplication that should be a helper. Then the organization: file and package layout, whether names describe the concern they own, public surface that should be internal, and files that have become junk drawers.

Merge the per-axis results and rank by payoff: correctness and architecture risk first, then duplication and organization, then local readability. **Merge two findings only when they are the same underlying issue with the same remedy** — a shared `file:line` is not enough on its own, since one line can carry both a swallowed error and a layering violation, and those need different changes. When findings genuinely coincide, keep the strongest framing and note the other axes it also trips.

## Step 3 — Clarify the open questions (one grouped AskUserQuestion)

Before writing the plan, batch every genuine judgment call into a **single** `AskUserQuestion` call — do not interrogate the user item by item, and do not ask about anything the repo's own documented rules already settle. Ask only where the answer changes the plan. The recurring ones:

- **Depth.** How aggressive should this pass be — surgical (naming, dead code, local extraction only), moderate (plus deduplication and pattern introduction), or structural (plus package moves and boundary changes)? Lead with a recommendation based on what Step 2 actually found and label it `(Recommended)`.
- **A genuine design fork.** Where two compliant approaches exist and the repo does not pick one, give the trade-off in each option's `description` — never present violating a documented rule as an option.
- **Spec divergence found in Step 1.** Make the execution semantics explicit in the option text, because this run's default write set is only the plan and tests: **"record it as a correctness item in the plan"** (the code is wrong; the fix is follow-up work for `/implement-plan`), **"update the spec"** (the spec moved on — this edits a spec file, so add it to the write set and re-run the Step 0.7 overlap check on that path now), or **"accepted drift, note only"**. A general bug fix is not on the default menu; if the user wants one now, that is a scope expansion to authorize explicitly, add to the write set, and verify — or to decline and defer.
- **Coverage ambition** (feeds Step 6): a target percentage, or "cover the high-risk paths the plan touches" — the latter is usually the better answer and the one to recommend. Whatever is chosen is checked explicitly in Step 7 **after** the re-measurement.
- **Out-of-scope rot** that the branch's changes made actively harmful: pull it into scope, or leave it and note it.

If Step 2 surfaced nothing that needs a decision, skip this step and say so — an unnecessary question is not diligence.

## Step 4 — Write the plan to `simplify-<branch-slug>.md`

Write it to the repo's conventional plan location if one exists (`specs/<current-branch>/`, `docs/plans/`, `plans/`), otherwise the repo root. State the path chosen, add it to the write set, and clear it through the Step 0.7 overlap check before writing. **Check first whether that file already exists**: if it does, read it and establish whose it is — a plan for *this* branch from an earlier run is yours to update in place; one whose recorded branch differs (the slug collision from Step 0.5) must not be overwritten. Ask for a different filename in that case.

Structure:

- **Scope** — the **exact original branch name** (not just the slug, so a collision is detectable), the base OID, the changed-file set, and the spec it was reviewed against — or explicitly that none was found and which Step 1 option the user chose.
- **Summary** — what is good and worth keeping (say this honestly; a plan that only lists faults misrepresents the branch), then the themes of what needs simplifying.
- **Findings and items** — the ranked work list. Each item:
  - a stable ID (`S1`, `S2`, …) so the review and the disposition table can cite it;
  - the site(s) as `file:line`;
  - the standard it violates, **named**;
  - the concrete change proposed — the actual extraction, rename, move, or pattern, not "clean this up";
  - **behavior-preserving: yes/no** — a `no` makes it a correctness item, sequenced separately and never bundled into a refactor commit;
  - the tests that pin the current behavior, and whether they already exist (this feeds Step 6 directly);
  - effort and risk, one line each.
- **Sequencing** — the order to apply the items, grouped so each group lands as its own reviewable commit, with dependencies between groups called out. Put the items that need a test safety net after the tests that provide it.
- **Test-gap register** — every item whose current behavior is **not** pinned by an existing test, each with the seam (if any) that closing it will need. This is the input to Step 6 and the reason the plan comes before the coverage work.
- **Status** — reserved for Step 7's reconciliation: which gaps this run closed, which seams it extracted, which correctness items it discovered, and which prerequisites are therefore already satisfied when `/implement-plan` picks the file up.
- **Non-goals** — what this pass deliberately leaves alone, and why: pre-existing rot in untouched files, deferred structural work, anything the user ruled out in Step 3.

Keep it a work list, not an essay. Follow the repo's rules for in-tree documents (many forbid ticket keys or issue IDs in committed files).

## Step 5 — Independent review of the plan, then validate and finalize

The plan **must** be independently reviewed before it is finalized, committed, or published. Codex is the preferred reviewer; 5b is the deterministic substitute; a plan that reached neither is unreviewed and this skill does not finalize it.

### 5a — Run the codex review

**If the repo/user has the `/codex-review` skill installed, prefer it** — invoke it via the Skill tool in the main loop, giving it the plan path and the focus below. Otherwise drive codex yourself from the repo root, in a subagent so the transcript stays out of the main context.

The `/codex:*` entries are Claude Code slash commands with `disable-model-invocation: true` — **you cannot call them, and they are not shell commands.** Check availability with `command -v codex`, then run the companion script the plugin wraps:

```bash
# Resolve the script once (version dir varies; sort -V so 1.0.10 beats 1.0.9):
COMPANION=$(ls -d ~/.claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs 2>/dev/null | sort -V | tail -1)

node "$COMPANION" adversarial-review --background -- "$focus"   # launch with run_in_background: true
node "$COMPANION" status "$job_id" --wait                       # poll (4-min bounded waits)
node "$COMPANION" result "$job_id"                              # findings
node "$COMPANION" cancel "$job_id"                              # abandon
```

Pass the focus as its **own argument after `--`**, never bundled into a single `"--background <focus>"` string: the companion re-parses a combined string with its own option parser, so quotes get rewritten and focus text containing `--base` or `--scope` turns into options. Use `adversarial-review` rather than `review` — this needs custom focus text, which plain `review` cannot carry. If `$COMPANION` does not resolve (plugin not installed), fall back to a direct one-shot run in the subagent — `codex exec --sandbox read-only "$focus"` — and if `codex` itself is absent, go straight to 5b.

`$focus`:

> Review the simplification plan in <plan-path> against the actual code it describes (the branch's changes vs <base-oid>), the spec at <spec-path> (or note that none was found), and the repo's standards in CLAUDE.md / AGENTS.md and any convention or architecture docs they cite. The user's decisions for this pass were: <Step 3 answers>. For each numbered item in the plan, check: does the cited code actually have the problem claimed; is the named standard really what it violates; is the proposed change genuinely behavior-preserving, or would it alter behavior in an edge case; would it introduce a speculative abstraction, over-engineer a simple path, or trade duplication for coupling; is the sequencing sound, and are the dependencies between groups right. Check the correctness items and any accepted spec drift against the spec's acceptance criteria specifically. Then look for what the plan missed: duplication, layering violations, non-idiomatic constructs, untestable or non-hermetic tests, and organization problems in the changed files that no item covers. Also check the test-gap register against the real tests — items claimed to be pinned by existing tests that are not. Output findings only, numbered, each citing the plan item ID or the file:line it concerns — and if you find nothing, say exactly "No findings" rather than returning an empty response. Do not rewrite the plan.

Save the result verbatim to a scratch file under `"$tmp"` so the adjudication is auditable.

**Enforce a deadline and a liveness check** — the review is the second opinion, never the critical path:

- Hard deadline: **10 minutes** for the whole review, not per attempt.
- Treat the job as **dead now** if its recorded `pid` is not alive (`ps -p "$pid"`) while status still says `running`.
- Treat it as **stalled** if its log file has been silent for **5+ minutes**.
- A job that reports **completed but errored**, or whose result is **absent, truncated, or unreadable**, counts as a failed review. A review that completes successfully and reports **no findings** is a *passing* review, not a failed one — require the result to say so explicitly ("No findings") rather than inferring it from an empty file, and the focus text below asks the reviewer for exactly that.

On death, stall, deadline, or an unusable result: run the companion's own `cancel` and go to 5b. Do not hand-delete files under the plugin's state directory — the companion owns that index. **Do not retry codex and do not ask whether to retry**: the fallback is deterministic and costs less than a second stall.

### 5b — Fallback: adversarial subagent review

If codex is absent, its launch fails, the liveness check fires, or its result is unusable, **do not skip the review** — run it natively, without asking. Fan out **2–3 adversarial `general-purpose` subagents in a single message**, each with a distinct lens over the plan, the spec, and the code it cites: (i) are the claimed problems real at the cited lines; (ii) is each proposed change actually behavior-preserving, and do the correctness items match the spec's acceptance criteria; (iii) what did the plan miss, and is the test-gap register accurate? Instruct each to cite plan item IDs or `file:line` and to verify every claim against the real code — no hypotheticals, no style opinions that contradict the repo's conventions.

Record in the Step 9 report that the review came from the native fallback and why (codex absent / launch failed / dead pid / stalled / deadline / unusable result). The plan is still reviewed, so this is not a waiver — but it is a **substitution**, and the report must not claim the codex review itself ran.

**If the fallback also fails to complete usably, stop** (a fallback that completes and reports no findings has succeeded — that is not a failure). Do not finalize, commit, or push an unreviewed plan, and never describe one as validated; report what failed and end the run.

### 5c — Validate every finding, then finalize

Do **not** apply review comments blindly — they are hypotheses to adjudicate, whatever their source. For each: re-read the cited code and plan item, check it against the repo's documented rules and the user's Step 3 answers, and mark **accept** (real — fold it in), **reject** (wrong, or it contradicts a rule or a user decision — record why), or **defer** (valid but belongs to a later pass — move it to Non-goals). Scrutinize the usual tendencies: proposing an abstraction where plain code is correct, flagging deliberate test duplication, and recommending changes that would alter behavior under the banner of simplification.

Rewrite the plan from the accepted dispositions, then present the disposition table to the user. If an accepted finding would overturn a Step 3 decision, do not just apply it — surface it via `AskUserQuestion` first.

The plan's **review-derived content** is settled here. Steps 6 and 7 do not reopen the adjudicated findings; they may only add what this run itself discovers — the Status section, corrected citations, and any correctness item a new test uncovers (Step 7).

## Step 6 — Measure coverage and identify the high-priority gaps

Measure over the branch's changed units, not the whole repo — the number that matters is whether *this branch's* code is pinned.

**Map changed files to source units first**, from the Step 0.6 set, and state the mapping:
- **Go** — the directory of each changed non-test `.go` file, deduped. Drop a directory only when it contains **no non-test `.go` files at all** in the current tree: a deleted file does not delete its package, and dropping the unit because one file went away hides the surviving code's coverage.
- **JS/TS, Python, Rust** — the module/package/crate that owns each changed source file, per the repo's own layout. Keep the *unit* mapping and the *instrumentation* scope consistent: if the unit is a module, instrument the whole module, not only the changed files inside it, or the denominators will not match between runs.
- Note `_test`-only changes separately: they affect coverage but add no production lines to cover.
- If **no production source changed at all** (a docs- or test-only branch), there is nothing to measure. Say so and record it, but do **not** jump the plan work: a test-only branch can still have test-quality findings and gaps in behavioral protection. Finish the plan's Status reconciliation in Step 7, then continue to Step 8. Do not fabricate a coverage number.

Prefer the project's own coverage entrypoint (`task cover`, `make coverage`, a package script) so local and CI agree; otherwise the language-native form, with **identical settings for the before and after runs** — a lift measured with different flags is not a lift:

- **Go** — `go test -race -count=1 -coverprofile="$tmp/cover.before.out" "${pkgs[@]}"`, then `go tool cover -func="$tmp/cover.before.out"`. Package patterns go **before** any `--`; `go test` treats `--` and everything after it as arguments for the test binary, so a terminator here silently tests the current directory instead of the package list. Name the changed packages explicitly rather than `./...`: a changed package with no test file still reports `0.0%`, exactly the gap worth catching, and `-coverpkg` would drop it. For per-package totals, **aggregate the covered/total statement counts from the profile** (each non-header line ends in `<numStmt> <count>`; sum `numStmt` where `count > 0` over `numStmt` per package) — averaging the rounded percentages `cover -func` prints does not give a statement-weighted total. Note also that this measures **in-package self-coverage**: a package covered deliberately by a sibling/consumer package's tests reads low here. Record that rather than chasing it, and only for such a package re-measure by naming the **consumer packages** as the test targets with `-coverpkg` pointed at the package under measurement (`go test -coverprofile="$tmp/consumer.out" -coverpkg=<pkg> "${consumer_pkgs[@]}"`). State which semantic each number is.
- **JavaScript/TypeScript** — the repo's runner with coverage on (`vitest run --coverage`, `jest --coverage`), writing to `"$tmp"` (`--coverage.reportsDirectory` / `--coverageDirectory`). Restricting the *test* selection does not restrict *instrumentation*: set the coverage `include`/`collectCoverageFrom` to the mapped units, and make sure untested files are still reported — otherwise a source file no test imports vanishes instead of showing 0%. **Check the installed runner's version for how**: Jest uses `collectCoverageFrom`; Vitest used `coverage.all` in older versions and drops it in v4, where an explicit `coverage.include` glob supplies the same inclusion. Read the runner's own config docs rather than assuming a flag exists. `skipFull` is a *reporter display* option — it hides fully-covered files from the table and does not change what is instrumented; do not use it for inclusion.
- **Python** — one `--cov=<module>` per module (the flag is repeatable, not comma-joined): `pytest "--cov=$m1" "--cov=$m2" --cov-report=term-missing "--cov-report=xml:$tmp/coverage.xml"`.
- **Rust** — `cargo llvm-cov` (or `cargo tarpaulin`) restricted to the changed crates, with its output directed into `"$tmp"`.

Report the **before** numbers per unit and in total (say which metric — statement, line, or branch — and how the total is weighted), then rank the gaps. **High-priority** means, in order:

1. **Every item in the plan's test-gap register** — code the plan proposes to change whose behavior nothing currently pins. These are the point of this step: without them the refactor is unverifiable.
2. **Safety-critical or irreversible paths** the branch touched, per the repo's own definition.
3. **Uncovered error and boundary paths** in changed code — the zero/empty/nil case, the overflow case, the invalid input, cancellation and deadline, concurrency.
4. **Changed code at 0% coverage**, whatever it does.

Everything else is a low-priority gap: list it in the Step 9 report and do not close it here. If the measurement itself fails — a changed unit will not compile, or its tests are already red — stop and ask rather than planning around an unmeasurable unit.

## Step 7 — Close the high-priority gaps, then reconcile the plan

Add each test file to the write set and clear it through the Step 0.7 overlap check before its first edit, and re-verify branch and tip.

Write the tests, test-first in spirit: each new test must **fail for the right reason** against the current code if it is pinning a bug, and pass if it is pinning existing correct behavior — run it and confirm which, rather than assuming. Follow the repo's test idiom exactly as learned in Step 1 (table-driven structure, generated mocks at the port boundary, the project's assertion style, `t.Parallel()` or its equivalent) and hold these tests to the Step 2 test-quality bar — hermetic, deterministic, behavior-focused, diagnostic on failure.

These tests pin **current** behavior. That is the whole point: they are the safety net that will catch a "simplification" that quietly changes what the code does. Do not adjust a test to match what the plan thinks the code *should* do.

**If a new test reveals a real bug**, stop and ask — there is no silent path through this. Two options, each with a defined disposition for the failing reproducer:

- **Fix it now** (a scope expansion): add the fix to the write set, clear the overlap check on those paths, fix the bug, and keep the test as its regression test — green, and committed with the fix.
- **Defer it**: the bug stays unfixed, so the reproducer must not remain red in the committed tree. Convert it to a test that pins the **current, buggy** behavior with an explicit comment naming the defect, or lift it out of the tree entirely — save the reproducer to `"$tmp"`, record that path in the plan and the report, and remove its hunks from the active test file. Do **not** merely leave it unstaged: an unstaged failing test still runs in Step 8's full-suite gate and is still eligible for later path-based staging. Never weaken the assertion to hide the defect, and never delete the evidence without recording where it went. Record it as a **new correctness item** in the plan (this is one of the two additions Step 5c permits after finalization, the other being Status), mark the gap **open, not closed**, and surface it in the Step 9 report and the PR body.

If a gap cannot be closed without a production change, make only the **minimal seam** the plan named (extracting a clock, a port, an interface at the consumer). Anything larger is a stop-and-ask: it is no longer a test change.

**Re-measure first, then apply the acceptance gate.** Re-run coverage with the **same settings** as the before run and record the after numbers; state before → after honestly per unit and in total. Then:

- Keep a gap-by-gap checklist: every high-priority gap from Step 6, each marked `closed` (naming the test that pins it, and confirming the assertion is meaningful — it must be able to fail) or `deferred` with the user's explicit agreement. Advance only when every high-priority gap is in one of those two states.
- If Step 3 set a **numeric target**, compare the re-measured number against it. Missing the target is a stop-and-ask, and the options must be concrete, because Step 6 deliberately excluded the low-priority gaps: **authorize specific additional gaps** — name them, and they join the checklist and the write set under the same acceptance rules — or **waive the target explicitly**. An unwaived miss means the plan is **not ready** for handoff in Step 9, and the PR must say so.

**Reconcile the plan.** Update the plan's **Status** section, plus any item whose cited locations the new tests moved, plus any correctness item added above: mark which test-gap-register entries are now closed and by which tests, which seams were extracted, which gaps remain open and why. `/implement-plan` reads this file as its contract, and a plan that still claims work this run already did would have it repeated. If the coverage work surfaced a genuinely new *design* decision (a seam the plan never named, a gap that needs a structural change), that is not a Status edit: route it through Step 3's clarification and note it for the next review pass rather than quietly adding an unreviewed item.

## Step 8 — Format, lint, build, test, then commit, push, and open or update the PR

Re-verify branch and tip before starting, and again before staging, each commit, and the push.

### Gates

Run all four — **format, lint, build, test** — preferring the project's own entrypoints: a Taskfile (`task --list` first), a Makefile, then the language-native fallback. An aggregate target (`task ci`, `make ci`) is a convenience, not a guarantee: **inspect what it actually runs**, and run any of the four it omits separately. Report each gate as pass / fail / **not configured**. Add any check the repo's own rules make mandatory (architecture lint, mutation testing on safety-critical paths). Tests run over the **whole project**, not just the changed units — that is what catches a seam extraction breaking a distant consumer.

**"Not configured" is an honest outcome, and it does not block.** A repo with no build step has no build gate to fail. Report it as N/A — never as green, never as passed — and name it in both the Step 9 report and the PR body. What blocks is a gate that exists and fails. Silently counting a missing gate as passed is the failure this rule prevents.

**Format means format, then verify.** Apply the formatter and then check that nothing remains:
- Go — `gofmt -w` over the write set (or `task fmt`), then `gofmt -l .` must exit zero **and print nothing**; `-l` only *lists* files needing formatting and exits zero whether or not the list is empty, so an unchecked `-l` passes a tree it should have failed.
- JS/TS — the repo's `format` script, then its check mode.
- Python — `ruff format` then `ruff format --check` and `ruff check`.
- Rust — `cargo fmt` then `cargo fmt --check`, plus `cargo clippy`.

**Keep formatter writes inside the write set.** A repo-wide format entrypoint will happily reformat files this run never touched — which are neither authorized targets nor pre-existing dirt, and which Step 8 will not commit, leaving the tree dirty and the verified state unreproducible. Scope the formatter to the write set where the tool allows it; where it does not, diff the tree afterwards and resolve every file it touched outside the write set (revert it, or get authorization to include it) before staging.

Every gate that exists must pass. If one fails because of this run's changes, fix forward and **re-run all four** — a lint fix can break a test.

**Attributing a failure takes two comparisons, in order, and neither one alone is conclusive.** A filename is weak evidence: a new seam can break an unchanged assertion inside a dirty test file, and a dirty config file can break a perfectly clean source file.

**First, rule out the retained dirt** (skip this when the Step 0.7 retained set is empty — there is nothing to rule out):

```bash
stash_before=$(git rev-parse --verify --quiet refs/stash)    # may be empty: no stash ref yet
git --literal-pathspecs stash push -u -- "${retained[@]}"
stash_after=$(git rev-parse --verify --quiet refs/stash)
[ -n "$stash_after" ] && [ "$stash_after" != "$stash_before" ] || stop   # this run created no stash
# … re-run the failing command …
git stash pop stash@{0}                                      # verify it restored cleanly before continuing
```

`--literal-pathspecs` is required, not decorative: `--` marks the arguments as pathspecs but does not make them literal, so a retained filename containing `*` or `[` would match extra files — and an **empty** array drops the path restriction entirely and stashes this run's own work, destroying the very comparison you are making.

Identify the stash by **object id**, not by existence: `refs/stash` resolving proves only that *some* stash exists, and a `stash push` that matched nothing still exits zero, leaving an unrelated older entry at `stash@{0}` that a bare `git stash pop` would then restore and drop. Compare `refs/stash` before and after, require a genuinely new value, and pop that entry by explicit selector. If no new stash was created, the comparison cannot be made — treat causation as unresolved rather than re-running against an unchanged tree.

- **Passes without the dirt** → the failure is the user's retained work. Report it, do not fix it, and ask whether to remediate or re-verify against a clean state.
- **Still fails without the dirt** → this is **"not explained by retained dirt"**, which is *not* the same as "caused by this run": a pre-existing failure also survives dirt removal. Go on to the second comparison.
- **Comparison impossible or inconclusive** → classify causation as **unresolved** and say so rather than guessing an owner.

**Second, rule out a pre-existing failure** by reproducing the exact command against `<starting-commit>` in a throwaway worktree, where both your changes and the retained dirt are absent:

```bash
tmp_wt=$(mktemp -d)
git worktree add --detach "$tmp_wt" "$starting_commit"
# … run the failing command there …
git worktree remove --force "$tmp_wt"
```

Failing there too makes it pre-existing — stop and ask whether to fix it, abort, or proceed with a documented waiver. Passing there makes it yours to fix. If you cannot reproduce it either way, say causation is unresolved rather than offering the waiver as though it were proven.

### Commit

Take the accumulated write set — the plan file, the test files, any authorized seam, spec edit, or bug fix — **minus** the Step 0.7 pre-existing dirty set and every scratch file. Split it into **disjoint per-commit slices**: the tests and seams; the bug fix with its regression test; any authorized spec edit (with the plan, since both record intent, unless the repo's convention separates them); the plan document. Slices are by **file**, so a file cannot appear in two: if one test file holds both ordinary coverage tests and a bug's regression test, put the whole file in the slice that best describes it — the bug-fix slice, since that is the commit a reviewer will bisect to — and say so in the message. Do not attempt partial-hunk staging to force a split. **Create a commit only for a slice that is actually non-empty** — a run whose coverage was already adequate legitimately has no test slice, and that is not an error. Run this cycle once per non-empty slice; staging everything and committing twice does not produce two commits. Never `git add -A`:

```bash
git --literal-pathspecs add -- "${slice[@]}"
git --literal-pathspecs diff --cached --name-only -z --no-renames   # compare set-equal to this slice
git diff --cached --check                                           # whitespace errors / conflict markers
git diff --cached                                                   # read the content before committing
```

Quote every path and pass `--literal-pathspecs`: a filename containing `*`, `:`, or a leading `!` is a pathspec pattern to git and can pull in files outside the slice. Pass `--no-renames` on the verification listing — rename detection reports one path where two are staged, so the set comparison would miss the deleted source path. **Compare the staged list against the slice as sets**; listing paths is not verifying them. Unstage anything unintended (`git --literal-pathspecs restore --staged -- "$path"`) and re-check. An unexpectedly empty index for a slice you believed non-empty is a stop — check whether this is a re-run where that commit already exists before concluding either way.

Commit in the repo's own convention — match the recent `git log` subject style (ticket-key prefix, Conventional Commits, whatever the log shows) and include any trailers the repo or environment requires. **After each commit check what the hooks did** (`git show --stat HEAD`, `git status --porcelain`): a `pre-commit` hook can reformat or re-stage files, so the committed tree may not be the tree the gates verified. If content changed, re-run the gates over the new state before committing anything further or pushing. When the last commit is in, confirm the union of the commits equals the intended write set and that the committed state — not just the working tree — is the state that tested green.

### Push

Pushing is outward-facing and hard to walk back, so show the destination and get explicit `AskUserQuestion` confirmation every time. First establish what is actually out there, distinguishing "no such branch" from "could not reach the server":

```bash
push_urls_raw=$(git remote get-url --push --all "$push_remote") || stop   # capture status, don't hide it
mapfile -t push_urls <<< "$push_urls_raw"                                 # pushurl is multi-valued
[ "${#push_urls[@]}" -gt 0 ] || stop
```

Do not run `git remote get-url` inside a process substitution: `mapfile` reports its *own* success, so a failing git call yields an empty array and every endpoint check below then silently passes over nothing. Capture the output, check the exit status, and require a non-empty array before continuing.

**Probe the push URLs themselves, always — not the remote name, and not only when there are several.** A remote's `pushurl` can differ from its fetch URL even when there is exactly one, so `git ls-remote "$push_remote"` can report the state of an endpoint this push will never touch:

```bash
for url in "${push_urls[@]}"; do
  git ls-remote --exit-code "$url" "refs/heads/$dest_branch"   # 0 = exists, 2 = absent, other = failure
done
```

Record each endpoint's exit status and OID as its own row; they are not interchangeable. If there is more than one push URL, say so before confirming — a push fans out to all of them and they can diverge.

**Exit 2 everywhere** means the destination does not exist: say plainly that a **new remote branch will be created**, and list the commits relative to the base OID. **Exit 0** on an endpoint gives you its OID: **fetch that object from that URL** so the local repo actually has it (a narrowed clone will not), then compute the outgoing commits against it — not against a local tracking ref, which a narrowed refspec can leave stale or absent even after a successful fetch. Where endpoints hold different OIDs, evaluate the range against the one furthest behind, since that is what the push must fast-forward:

```bash
git fetch "$url" "$remote_oid" || git fetch "$url" "refs/heads/$dest_branch"
git rev-parse --verify "$remote_oid^{commit}" || stop     # object present locally?
git log --oneline "$remote_oid..HEAD" --
git merge-base --is-ancestor "$remote_oid" HEAD; echo "$?"   # 0 = fast-forward, 1 = not, >1 = command error
```

Ranges before the `--`, never after. Distinguish `is-ancestor` exit 1 (genuinely not a fast-forward) from exit >1 (the command itself failed) — treat the latter as unknown and stop. Any other `ls-remote` exit is a transport or auth failure — stop and ask rather than confirming a destination you could not read.

Present the remote, the destination ref, the push URL(s) — **credentials redacted**, since an HTTPS remote can embed `user:token@`; show `https://***@host/path` — and the outgoing commit list: a branch can carry local commits the user forgot about, and "push this branch" is not consent to publish those unseen. If the push would not be a fast-forward, stop and ask; never reach for `--force` on your own.

On confirmation, push explicitly and verify the server took it:

```bash
git push "$push_remote" "HEAD:refs/heads/$dest_branch"   # add -u only if no upstream is set
push_status=$?
head_oid=$(git rev-parse HEAD)
for url in "${push_urls[@]}"; do
  git ls-remote --exit-code "$url" "refs/heads/$dest_branch"   # re-probe every endpoint
done
```

**Re-probe every push URL afterwards, whatever the push exit was** — a fan-out can partially succeed, so a non-zero status does not mean nothing landed. Then classify from the **endpoint OIDs against `$head_oid`** first, and use the push's exit status only to explain the result:

- **Every endpoint at `$head_oid`** → **succeeded** (report the push's own non-zero exit as an anomaly worth naming, but the refs are where they should be).
- **Some at `$head_oid`, some not** → **partial publication**. Name which URL holds which OID, and say which endpoints still need the push. Note that endpoint disagreement is only evidence of a *partial* push when at least one endpoint moved to `$head_oid`; pre-existing divergence with none of them advanced is a wholly failed push, not a partial one.
- **No endpoint at `$head_oid`** → **failed**. Stop and report the exact push error.
- **The user declined** → **declined**: nothing was pushed and the PR step does not run.

If any endpoint cannot be re-probed, the outcome is **unverified** — report it as such rather than assuming either way, and do not proceed to the PR step on an unverified push.

### PR

Only after a verified successful push. Resolve the PR identities explicitly — they are not the git ones: `<pr-repo>` (the repository the PR lives in — pass `--repo` on every `gh` call rather than trusting `gh`'s own inference, which can differ from git's), `<pr-head>` — the head as the **create** call needs it: `<dest-branch>` when the PR is opened in the same repository, and the qualified `<owner>:<dest-branch>` when `<push-remote>` is a fork (`<owner>` being the fork's owner). Keep `<dest-branch>` unqualified for the listing call below, which does not accept the qualified form, and `<pr-base>` (the default branch **of `<pr-repo>`**, which for a fork is not the fork's default — this is the value Step 0.1 also uses for the review base).

```bash
gh pr list --repo "$pr_repo" --head "$dest_branch" --base "$pr_base" --state all --limit 100 \
  --json number,url,state,isDraft,headRefName,baseRefName,headRepository,headRepositoryOwner
```

Use `gh pr list`, not `gh pr view --head` — `gh pr view` has no `--head` flag, takes the branch positionally, and would fail even when a PR exists. Pass `--head` the **unqualified** branch name: it does not accept `owner:branch`. Because several forks can offer the same branch name, select the match by `headRepositoryOwner`/`headRepository` **and** `baseRefName`, not by branch name alone. Narrow with `--base` and raise `--limit` (the default is 30): post-filtering a truncated page can hide an older matching open PR behind newer same-named ones, so if the result comes back at the limit, page further before concluding there is no match. A successful call returning `[]` means no PR; a **non-zero exit** means a syntax, auth, or transport failure and is a stop, not an absence.

- **No PR** → `gh pr create --repo "$pr_repo" --base "$pr_base" --head "$pr_head" --title "$title" --body-file "$tmp/pr-body.md"`. The qualified `owner:branch` form belongs here, on creation, where it is supported. Always `--body-file` from outside the repo; a long body through `--body` gets mangled by shell quoting.
- **An open PR whose head repo/owner and base match** → `gh pr edit "$number" --repo "$pr_repo" --body-file "$tmp/pr-body.md"`. Preserve anything a human added — append or amend a clearly-marked section rather than overwriting someone else's text.
- **Only closed or merged matches**, or a match whose head/base is not what you resolved → stop and ask. Never reopen a closed or merged PR.

The body states: what the branch does (from the spec, or that no spec was found); that a simplification plan was produced, where it lives, and that **the simplification itself is not implemented** — the plan's items are pending follow-up for `/implement-plan`; what this run *did* deliver (the tests, plus any authorized seam, spec edit, or bug fix, each named); coverage before → after with the high-priority gaps closed and any deferred or left open; whether the plan's review was codex or the native fallback; the gates that ran, including any N/A or waived; and the plan's Non-goals as explicit follow-up. Include any trailers the environment requires for PR descriptions. If `gh` is unavailable or unauthenticated (`gh auth status`), do not fail the run — the branch is pushed: report the exact command the user should run, and say the PR step was not completed.

## Step 9 — Report

State, per the repo's handoff checklist if it has one:

- **The plan** — its path, item count, and themes; the spec it was reviewed against, or that none was found and which Step 1 option was chosen.
- **Review** — codex, or the native fallback **as a substitution** (naming why codex did not run); total findings and the accept/reject/defer breakdown with one-line reasons for every rejection. A clean review reports "no findings", which is a result, not a skip.
- **Coverage** — before → after per unit and in total, which metric and weighting, the high-priority gaps closed (with the test that pins each), those deferred or left open and why, and the low-priority gaps untouched. If no production code changed, say that instead of a number. If a numeric target was set, state met / waived / missed.
- **Verification** — each gate as pass / fail / not configured, via which toolchain, and any waiver the user granted.
- **Published** — the commits, the push outcome (declined / failed / partial / unverified / succeeded), and the PR URL created or updated — or the exact command left for the user. An unverified push blocks the PR step; say what could not be re-probed.
- **Remaining risk** — deferred findings, Non-goals, correctness items including any bug found and deferred in Step 7, and behavior the new tests still do not pin.
- **Next step** — the refactor is not done. Name the plan file and say whether it is ready for `/implement-plan`: **ready** only when the review ran (codex or fallback), every high-priority gap is closed or explicitly deferred, any numeric target is met or waived, and every configured gate is green. Otherwise name exactly what is outstanding.

## Stop-and-ask conditions (use `AskUserQuestion`; never silently proceed)

- Detached `HEAD`; the local branch is the default branch; or `<dest-branch>` resolves to a default or protected branch of the destination repository (Step 0).
- Ambiguous push remote; the base will not resolve or has no merge-base with `HEAD`; an unrecognized diff status (Step 0).
- Anything already staged in the index; a dirty path that this run will write to — checked again as each new write target appears; dirty unstaged/untracked paths the user must decide about (Step 0, Steps 3/4/6/7).
- The branch has no changes against the base — report and stop (Step 0).
- No spec found for the branch (Step 1).
- The judgment calls batched in Step 3: depth, a genuine design fork, spec divergence, coverage ambition, out-of-scope rot.
- An accepted review finding would overturn a Step 3 decision (Step 5c).
- A changed unit will not compile or its tests are already red, blocking measurement (Step 6).
- A new test reveals a real bug — fix now or defer (Step 7).
- Closing a gap needs a production change larger than the minimal seam the plan named (Step 7).
- A numeric coverage target is missed (Step 7).
- The coverage work surfaces a design decision the plan never named (Step 7).
- A gate fails in retained dirty files, fails for a reason proven pre-existing, or causation cannot be established (Step 8).
- A repo-wide formatter modified files outside the write set (Step 8).
- Every push — always confirm the destination, and disclose multiple push URLs (Step 8).
- An unreadable `ls-remote`/`gh` response; `merge-base --is-ancestor` exiting >1; the only PR matching the branch is closed, merged, or has a head/base you did not resolve (Step 8).

**Hard stops (report and end the run; not an AskUserQuestion):** neither codex nor the fallback completed a usable review (Step 5b) — a review that completes with no findings is a success, not this condition — an unreviewed plan is never finalized, committed, or pushed.
