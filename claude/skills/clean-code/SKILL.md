---
name: clean-code
description: Reviews the current branch against its spec and the repo's architecture - verifies the changed code conforms to the declared architecture style, decides per changed unit whether a refactor is warranted, and writes a codex-reviewed simplification plan (simplify-<branch>.md) covering architecture, clean code, design patterns, idiom, and deduplication in production and test code - then closes the high-priority test-coverage gaps, runs the project's gates, and commits, pushes, and opens or updates the GitHub PR. Plans the refactor; does not apply it. Use when a branch is functionally complete and needs an architecture and cleanup review before merge.
---

# Clean-code skill

Take a branch whose work is functionally complete and make it **reviewable**: understand what the spec asked for, verify that what was built conforms to the repo's architecture, decide whether each changed unit warrants a refactor, and plan the refactors that are warranted - then lay down the test safety net that plan will need. Output is a finalized `simplify-<branch-slug>.md` carrying an architecture-conformance verdict, a per-unit refactor verdict, and the ranked work items; new tests closing the high-priority coverage gaps; a green gate run; and a pushed branch with an open PR.

**"No refactor warranted" is a legitimate verdict.** When the evidence supports it, the plan records it with its reasons and the run continues to coverage and publication. A plan that invents work to look thorough misleads the reviewer as much as one that misses a violation.

## Files in this skill

Read each when its step says so. Subagents are told to read theirs directly; pass them the absolute path.

- `${CLAUDE_SKILL_DIR}/ARCHITECTURE.md` - the architecture-conformance procedure and its result shape (Step 2b).
- `${CLAUDE_SKILL_DIR}/CODEX.md` - driving the codex review: commands, focus text, liveness rules, result shape (Step 5a).
- `${CLAUDE_SKILL_DIR}/COVERAGE.md` - mapping changed files to units and measuring coverage per language (Steps 6 and 7).
- `${CLAUDE_SKILL_DIR}/PUBLISH.md` - the fork case (Step 0), gate-failure attribution, commit, push, and PR (Step 8).

## What this run changes, and what it does not

This skill **plans** the simplification; it does not carry it out. The refactor is a separate, reviewable change - hand the finalized plan to `/implement-plan` for that.

**By default this run writes exactly two things:** the plan file, and **tests** closing the high-priority coverage gaps.

**Three narrow exceptions may extend that write set, each only when explicitly authorized and each recorded in the plan, the commit, and the PR body:**

1. **Minimal testability seams** in production code - extracting a clock, a port, an interface at the consumer - only where Step 4's plan named one, and only to make a gap closable. Anything larger is a stop-and-ask.
2. **A spec edit**, when Step 3's spec-divergence question resolved that the spec (not the code) is what moved on.
3. **A bug fix**, when Step 7's new test reveals a real bug and the user authorizes fixing it now rather than deferring it.

Nothing else is in scope. Maintain the write set as a single accumulating list from Step 3 onward - Step 8 stages from it, so an authorized change missing from it is an authorized change that silently never ships.

Closing coverage gaps *before* refactoring is the ordering that makes the refactor safe: the tests that catch a behavior-changing "simplification" must exist before anyone simplifies. A plan built on uncovered code is a guess.

If the repo has a `CLAUDE.md` (or `AGENTS.md`), read it in the main loop **before Step 0's git actions** - it is authoritative for conventions, architecture and layering rules, testing expectations, commit style, and quality gates, and it overrides anything in this skill or any reviewer suggestion that contradicts it.

## Principal-engineer posture

The plan is only as good as the standards it is written against. These are the axes it judges the branch on - and the bar the tests this skill writes must themselves meet:

- **Architecture conformance.** The changed code fits the repo's declared architecture style: each concern in the component that owns it, dependencies pointing the way the rules allow, interfaces at the consumer, core logic free of transport/DB/framework concerns. **Verified, not assumed:** a passing architecture gate proves imports, never placement, and a gate the branch loosened proves nothing at all. Where the repo declares no style, the standard is the consistent precedent of its own code, labelled as inferred.
- **Clean code.** Small, single-purpose units at one level of abstraction; intention-revealing names; no duplication introduced by the branch; comments that explain the non-obvious *why*, not the *what*. Dead code, commented-out code, and leftover scaffolding go.
- **Standard design patterns.** Name well-known patterns (Ports & Adapters, Strategy, Repository, Functional Options, Decorator, ...) where one would remove real duplication or isolate a dependency - and say so in the plan, not in code identifiers or comments. Plain code wins when it suffices; an abstraction with one implementation and no seam is a finding *against* the code, not for it.
- **Idiomatic style.** Precedence: documented repo rules, then the surrounding code's established idiom, then the language community's conventions (Effective Go, PEP 8, the Rust API guidelines, ...).
- **Deduplication.** Real duplication is repeated *knowledge*, not repeated characters. Two functions that look alike but change for different reasons stay apart; three call sites re-deriving the same rule do not. Deliberate duplication in tests that keeps a case readable is fine and stays unflagged.
- **Behavior-preserving by default.** Most plan items are refactors: same behavior, better structure. An item that changes behavior is a **correctness item** - label it as such, keep it out of the refactor sequencing, and never smuggle it in as "cleanup".
- **Payoff over churn.** A refactor earns its place by what it saves the next reader and the next change. Step 2d weighs that with evidence; a finding whose remedy costs more than it returns is recorded, not planned.
- **Scoped to this branch.** Judge the code the branch added or changed. Pre-existing mess in untouched files is an observation, never a plan item, unless the branch's own changes made it actively harmful. A branch that **copies** a pre-existing bad pattern into new code owns the copy: the new site is the finding, the precedent an observation.

## Subagent delegation

Run the read-heavy analysis and the verbose command runs in **`general-purpose` subagents** (via the `Agent` tool); keep orchestration, judgment, and every gate in the main loop.

- **Main loop owns** (never delegate): all of Step 0's scope and git resolution; launching the Step 2a mechanical runs; the Step 2d refactor verdict; **every user gate** - the Step 3 grilling session and every `AskUserQuestion`, since subagents cannot prompt the user; **writing and rewriting the plan file** (Step 4, Step 5c's finalization, Step 7's reconciliation); the final accept/reject/defer calls in Step 5c; **invoking other skills**, since the Skill tool runs in this conversation and cannot be launched from inside a subagent; the Step 8 commit, push, and PR; and the Step 9 report.
- **Delegate** (each returns a compact result in the shape its step names):
  - **Step 1** - the spec brief.
  - **Step 2b** - architecture conformance, following `ARCHITECTURE.md`.
  - **Step 2c** - the code-review passes, sized to the change per the 2c table.
  - **Step 5a** - the codex run, following `CODEX.md`; its transcript stays in the subagent.
  - **Step 5b** - the fallback reviewers, when 5a fails.
  - **Step 5c** - adjudicate about five findings or fewer in the main loop; for more, split them into disjoint batches of about 3-5 (contradictory findings share a batch, so one subagent resolves the conflict) and adjudicate them in parallel, each returning its slice of the disposition table with evidence. The main loop makes the final call.
  - **Step 6** - the coverage measurement, following `COVERAGE.md`.
  - **Step 7** - writing the planned tests, one subagent per independent unit-under-test.
  - **Step 8's gate run** - returning pass/fail plus only the failing output.

Give each subagent a self-contained prompt: the exact commands, the resolved values from Step 0 (base OID, merge-base OID, changed-file list, `$tmp`), the procedure file to follow if it has one, and the precise result shape to return. **A delegated subagent that hits a stop-and-ask condition returns a `needs user decision` status to the main loop** - it cannot prompt, and proceeding on its own assumption is the failure this rule exists to prevent.

**Parallelize reads, serialize writes.** Where this skill names a fan-out, dispatch it as multiple `Agent` calls in a **single message**. Step 1's spec brief runs alongside Step 2a's mechanical runs. Steps 2b and 2c go out together - they are read-only over the same files, which is exactly the safe case. Step 5c's adjudication batches fan out. Step 7's test-writing fans out **only after a write-set check**: one subagent per test file, and anything touching a shared surface (a shared fixture or helper, a regenerated mock, a manifest, a production seam extraction) lands first in the main loop or a single upstream subagent before the rest go parallel. Step 5a -> Step 5c is a genuine producer -> consumer chain and stays serial.

## Conventions for every command in this skill

- **Bind resolved values to quoted variables.** Branch names, paths, and remotes can contain `$( )`, backticks, spaces, or a leading `-`. Bind each to a shell variable and use it quoted (`"$current_branch"`), or pass it as an argument; never splice the literal text into a double-quoted command line. Build multi-package/module argument lists as arrays (`"${pkgs[@]}"`), not as a space-joined string.
- **Shell state does not survive between Bash tool calls.** Record every resolved value (`<current-branch>`, `$tmp`, `$base_oid`, `$merge_base`, `$job_id`, ...) in the conversation and re-bind the variables a command needs at its start, single-quoted (`tmp='/tmp/tmp.abc'`). Write snippets that run in both bash and zsh - the tool may run either - so no `mapfile`/`readarray`; read lines into an array with `while IFS= read -r line; do arr+=("$line"); done <<< "$raw"`.
- **`--` means different things to different tools.**
  - *Git commands that take pathspecs* (`add`, `diff`, `log`, `restore`, `checkout`): `--` separates **pathspecs and nothing else**. Put it before a list of file paths (`git add -- "${paths[@]}"`) and keep every revision, range, remote, or ref before it - git reads anything after it as a path, which typically "succeeds" with empty output and silently analyzes the wrong thing. Range first, terminator last: `git diff "$base_oid...HEAD" --`.
  - *Git commands that take no pathspec* (`fetch`, `ls-remote`, `merge-base`, `rev-parse`, `remote`, `worktree`, `push`): no `--` at all. Protect a leading-dash value with `--end-of-options` where the git version supports it, or reject the name outright.
  - *`go test`*: `--` and everything after it are arguments **for the test binary**, so package patterns come before it - a terminator there silently tests the current directory instead of the named packages.
  - *Non-git tools*: `--` is an ordinary end-of-options marker and is sometimes **required** - notably the codex companion, where the focus text must follow it. Follow each tool's own contract.
- **Check exit status before interpreting output.** Empty stdout from a command that failed means nothing. Every "if this is empty, then ..." rule below applies only after the command exited zero.
- **Keep every artifact out of the working tree.** Scratch files, mechanical-run output, coverage profiles, review output, PR bodies, and temporary worktrees live in a `mktemp -d` directory (`"$tmp"`). Pass each tool's output and cache path explicitly rather than relying on defaults that drop files into the repo. Remove temporary worktrees when done (`git worktree remove --force "$tmp_wt"`).
- **Re-verify the branch and tip before every write, gate, commit, and push.** The tree is shared with subagents, hooks, and the user's other terminals. Compare `git branch --show-current` against `<current-branch>` and `git rev-parse HEAD` against the expected tip (`<starting-commit>`, plus commits this skill has itself made). A checkout, reset, rebase, or outside commit keeps the branch name identical, so the name alone proves nothing. On any unexpected movement, stop and ask, and advance the expected tip only for this skill's own commits.
- **Clear each write target against the dirty set the moment it becomes known** - see Step 0.7. The write set grows in Steps 3, 4, 6, and 7, and each new target is checked *before its first edit*.

## Step 0 - Resolve scope: the branch, its base, and what it changed

1. **Resolve the identities separately.** Conflating them is how work lands on the wrong branch or in the wrong repository. Resolve and record each:
   - `<current-branch>` - the local branch (`git branch --show-current`). Empty means detached `HEAD`: stop and ask; there is nothing to push.
   - `<push-remote>` - where Step 8 pushes: `branch.<current-branch>.pushRemote` -> `remote.pushDefault` -> the current branch's upstream remote -> `origin` -> the sole remote. Ask when more than one plausibly applies.
   - `<dest-branch>` - the branch name **on `<push-remote>`**. Default to `<current-branch>`. Adopt an upstream's branch name only when that upstream is on `<push-remote>` itself: an upstream pointing at a *different* remote says nothing about where this push lands. Show the resolved destination and confirm it.
   - `<default-branch-name>` and `<base>` - below.
   - `<pr-repo>`, `<pr-head>`, `<pr-base>` - resolved in Step 8. **When `<push-remote>` is a fork**, resolve `<pr-repo>` and `<pr-base>` now, following `PUBLISH.md` section "Fork case", and use the PR base as the review base: reviewing against the fork's default branch while the PR targets upstream's would review the wrong delta.
2. **Resolve the base.** In the common non-fork case, `<default-branch-name>` on `<push-remote>` is both what Step 0.4 guards the destination against and the review base:
   ```bash
   git ls-remote --symref "$push_remote" HEAD   # "ref: refs/heads/<default-branch-name>	HEAD"
   git fetch "$push_remote" "+refs/heads/$default_branch_name:refs/remotes/$push_remote/$default_branch_name"
   base_oid=$(git rev-parse --verify "refs/remotes/$push_remote/$default_branch_name^{commit}") || stop
   merge_base=$(git merge-base "$base_oid" HEAD) || stop
   ```
   Fetch the **exact ref with an explicit refspec**: a plain `git fetch` honours the configured refspec, which in a single-branch or narrowed clone may not cover the default branch at all. Pin `<base>` to `$base_oid` and `<merge-base>` to `$merge_base`, and use those OIDs everywhere downstream, so a concurrent fetch cannot move them mid-run. If `rev-parse` or `merge-base` fails, stop and ask which branch is the base; an unresolved base makes the diff below fail, and a failed diff is **not** "nothing changed". When deriving `<default-branch-name>` from a `<remote>/...` string, strip **only** the exact `<remote>/` prefix, keeping every remaining slash (`origin/release/stable` -> `release/stable`). If the remote is unreachable, fall back to a local `main`/`master` only after saying so and treating the base as possibly stale.
3. **Pin the starting point.** Record `<starting-commit>` (`git rev-parse HEAD`).
4. **Guard the destination, not just the local name.** Stop and ask if `<dest-branch>` is the default or a protected branch **of the repository being pushed to** - a local branch named `feature` whose destination resolves to `main` passes a local-name check and still publishes to the default branch. Check the resolved destination against `<default-branch-name>` (and the repo's protected-branch list where `gh` can report it) before any commit or push. A local branch equal to `<default-branch-name>` is likewise a stop: this skill commits and opens a PR, and neither belongs on the default branch.
5. **Derive `<branch-slug>`** - `<current-branch>` with every `/` replaced by `-` (`feat/auth-revamp` -> `feat-auth-revamp`). The plan file is `simplify-<branch-slug>.md`. This normalization is **lossy**: `feat/auth` and `feat-auth` collapse to the same filename, so Step 4 checks for an existing file and records the exact original branch name inside the plan.
6. **Compute the changed set and its size** - the entire review scope:
   ```bash
   git diff --name-status -z --find-renames "$base_oid...HEAD" -- > "$tmp/changed.z" || stop
   git diff --shortstat "$base_oid...HEAD" --
   ```
   Three dots (diffing against the merge-base), never two - the two-dot form also reports everything the base gained since the branch diverged. Parse the **NUL-delimited** output: plain `--name-status` escapes unusual filenames and would silently mangle them. Handle every status explicitly - `A`/`M`/`T` are in scope (a type change still changes behavior); `D` removes that *file* from the coverage denominator in Step 6, though its unit survives if other production files remain; `R` carries **two** paths - record both, since the old path is what existing tests and docs still reference. An unrecognized status is a stop. If the diff fails, stop; if it succeeds and is empty, report that there is nothing to simplify and stop. Record `<changed-lines>` (insertions plus deletions from `--shortstat`): Step 2c sizes its fan-out from it.
7. **Check the tree, and keep checking it.** Record every dirty path - staged, unstaged, untracked - as the **pre-existing dirty set** (`git status --porcelain=v1 -z -uall`):
   - **Anything staged** -> stop and ask to commit or stash it. Working around a pre-loaded index silently rewrites the user's staging state, and this skill will not restore it.
   - **A dirty path that this run will write to** -> stop and ask to commit, stash, or otherwise resolve it. "Keep and proceed" is not an option here: Step 8 stages the write set *minus* the pre-existing dirty set, so a retained dirty write target would have this skill's own work silently dropped from the commit. The write set grows as the plan path is chosen (Step 4), a spec edit is authorized (Step 3), gaps map to test files (Step 6), and seams or bug fixes are authorized (Step 7), so **run this check against each new target the moment it is known, before its first edit**.
   - **Dirty paths disjoint from the write set, unstaged only** -> recommend commit or stash; offer "keep and proceed" only with the consequence stated: they stay out of the commit, but **Step 8's gates run over them too**, so a repo-wide formatter will rewrite them and any lint/build/test failure they cause is not this branch's to fix. If the user keeps them, record them as the **retained set** (Step 2 then reviews a clean worktree of the committed branch, and Step 8 attributes failures with `PUBLISH.md`'s comparisons) and scope the format gate to the write set.
   Re-run the status command after any remediation and re-record the set - a path since committed or stashed is clean now and comes off the exclusion list.

## Step 1 - Read the spec

Dispatch the spec-brief subagent as soon as Step 0 is done, in the same message as Step 2a's background runs - nothing in Step 2 waits for it.

**The spec** - what the branch was *supposed* to do. Look, in order, for: `specs/<current-branch>/` or `specs/<branch-slug>/` (the `requirements.md` / `plan.md` / `validation.md` trio this repo's `/feature-spec` writes), a plan file named in the branch's commit messages, a linked issue or PR body. A roadmap entry is context, **not** an acceptance spec.

If no spec is found, **stop and ask** via `AskUserQuestion`: the user may know where it lives, or may confirm there is none. Offer: point me at it (free-text path), review against the linked issue/PR instead, or proceed on repo standards alone. Only the last option drops the spec axis, and choosing it is an explicit acknowledgment that this part of the review cannot be completed - the Step 9 report and the PR body must both say so. Review only against a spec that exists.

The subagent reads the spec and enough of the changed code to compare them, plus the nearest existing tests to learn the repo's test idiom (table-driven? generated mocks? which assertion style?) for Step 7. It returns: what the spec asked for, what was built, every visible divergence as `spec section - code file:line - divergence`, and the test idiom in a few lines.

**Spec divergence is a finding in its own right** - code that cleanly implements the wrong thing is not clean code - but it is a *correctness* finding, so label it as such and keep it out of the behavior-preserving refactor items.

## Step 2 - Review: architecture conformance, code quality, and the refactor verdict

### 2a - Mechanical evidence first (main loop, background)

Tools find the mechanical problems cheaply and exactly, which leaves the reviewers' judgment for what no tool sees.

**Run against the committed branch.** When the retained set is empty, the working tree is the committed branch: run there. Otherwise create a throwaway worktree at `<starting-commit>` (`git worktree add --detach "$tmp/head-wt" "$starting_commit"`), run there, and hand the same worktree to 2b and 2c as the tree to read, so retained edits shape neither the evidence nor the review; remove it once Step 2 is done.

As soon as Step 0 is done, launch these as **one** `run_in_background: true` command that runs them one after another - golangci-lint holds a global lock, and a second concurrent instance exits with an error instead of waiting - each writing to its own file in `"$tmp"` with its exit status recorded:

- **The architecture gate** - the repo's own entrypoint (`task arch-lint`, `make arch`, or the command its `CLAUDE.md` or CI names), else the tool its config implies (`ARCHITECTURE.md` lists the common ones by ecosystem) -> `"$tmp/arch-gate.txt"`. No gate configured is recorded as `not configured`; a configured gate whose tool is missing is `unavailable`, never a pass.
- **The linter, new issues only** - the repo's lint configuration over the changed code, restricted to issues the branch introduced where the tool supports it (golangci-lint: `--new-from-rev "$merge_base"`; run every pass the repo's lint entrypoint runs, such as one per build-tag set), else the full entrypoint with its output filtered to the changed files -> `"$tmp/lint.txt"`.
- **Optional complexity and duplication signals**, when the repo's lint config does not already enable them - for Go, `golangci-lint run --enable-only=gocognit,dupl,funlen --new-from-rev "$merge_base" "${pkg_patterns[@]}"`, where `pkg_patterns` holds each changed package directory as `./<dir>` -> `"$tmp/signals.txt"`. These are **signals** that point the reviewers at code to read; an ad-hoc metric is never itself the named standard behind a finding.

None of these runs uses `--fix` or writes outside `"$tmp"`. In the main loop, show only each run's exit status and finding count.

**Attribute findings by comparison, not by filename.** A branch's config or dependency change can break a file it never touched, and a file the branch changed can carry an old violation on a line it did not. When a run fails, re-run that same command in a throwaway worktree at `<merge-base>` (`git worktree add --detach "$tmp/base-wt" "$merge_base"`, removed afterwards) and save its output beside the first: a finding present there is pre-existing; one absent there is the branch's, wherever it sits. **A gate already red at `<merge-base>`** is reported to the user now - Step 8 will hit it, and this is the cheapest point to decide whether to fix it first, waive it, or stop.

### 2b - Architecture conformance (subagent)

Dispatch one subagent that follows `${CLAUDE_SKILL_DIR}/ARCHITECTURE.md` (pass the absolute path), with the tree to read (the repo root, or 2a's head worktree), `$base_oid`, `$merge_base`, the changed-file list with statuses, `"$tmp"`, and `"$tmp/arch-gate.txt"` with its exit status and, when 2a ran one, its `<merge-base>` comparison output. It builds the architecture model from the repo's own documents and gate config, maps every changed file to its component, dispositions every dependency edge and gate-config change the branch adds, reviews placement and boundaries, and returns the conformance table and a branch verdict: `conforms`, `conforms with drift`, or `violates`.

**Read the cited code and the cited rule yourself before any `violation` enters the plan** - it is the plan's highest-stakes claim, and the cheapest to check now.

### 2c - Code review (subagents)

Review the changed set on five axes, in the tree 2a ran in. Reviewers read each changed file in full, not just its hunks, plus the surrounding package: "is this idiomatic here" and "does this duplicate something" are both questions about context. Every finding is `file:line - what - which standard it violates (with its source) - why it matters here - the remedy, as a named refactoring where one applies`. A finding with no named standard behind it is a preference, and preferences do not go in the plan. Reviewers read `"$tmp/lint.txt"` and `"$tmp/signals.txt"` and confirm or reject each mechanical finding in their files rather than re-running the tools.

1. **Clean code** - unit size and single responsibility, mixed abstraction levels, naming, magic values, dead or commented-out code, comment rot, error handling that swallows or obscures, boolean/positional parameters that should be a type.
2. **Design patterns** - where a named pattern would remove real duplication or isolate a dependency, **and** the reverse: speculative abstractions, one-implementation interfaces with no seam, indirection that costs more than it saves.
3. **Idiomatic style** - deviations from documented repo rules first, then from the surrounding code's idiom, then from the language community's conventions. Include the language's own traps (unchecked type assertions, ignored errors, misused concurrency primitives, mutable default arguments).
4. **Deduplication** - repeated *knowledge*: the same rule re-derived at several call sites, copy-pasted blocks that must change together, parallel switch statements over the same type - including duplication of something that already exists elsewhere in the repo. Distinguish this explicitly from code that merely looks similar and changes for different reasons.
5. **Tests and file organization** - tests meet the same bar as production code. Unclear or misleading test names, assertions that cannot fail, tests coupled to implementation detail rather than behavior, missing boundary cases, non-hermetic or non-deterministic tests (wall-clock reads, real network, ordering dependence, shared mutable state), fixture duplication that should be a helper. Then file-level organization: whether file names describe the concern they own, public surface that should be internal, and files that have become junk drawers. (Component-level placement belongs to 2b.)

Size the fan-out to the change - one reviewer per axis spends five subagents re-reading the same files:

| `<changed-lines>` | Review shape |
| --- | --- |
| under ~150 | the main loop reviews all five axes itself |
| ~150 to ~800 | one subagent, all five axes |
| ~800 to ~2,500 | two subagents: **design** (clean code, patterns, duplication) and **craft** (idiom, tests and organization) |
| over ~2,500 | exactly **one** duplication subagent over the whole changed set, since cross-file repetition is what it hunts; then design (clean code, patterns) and craft subagents per component partition, each confined to its slice |

Dispatch the 2c subagents in the same message as 2b, once the 2a runs have finished.

### 2d - Decide whether each changed unit warrants a refactor (main loop)

**Merge first.** Combine 2b and 2c and rank by payoff: correctness and architecture risk first, then duplication and organization, then local readability. **Merge two findings only when they are the same underlying issue with the same remedy** - a shared `file:line` is not enough, since one line can carry both a swallowed error and a layering violation, and those need different changes. When findings genuinely coincide, keep the strongest framing and note the other axes it also trips.

**Then weigh each finding's remedy, payoff against cost, with evidence:**

- **Payoff rises with** fan-in (callers that inherit the problem), change frequency (`git --literal-pathspecs log --oneline -- "$path"`), a spec or roadmap that extends this unit next (a refactor before an extension pays back at once), and a safety-critical path.
- **Cost rises with** callers outside the branch that the change would ripple into, a unit the spec or roadmap replaces soon, and behavior no test pins and this run cannot pin.

A remedy whose payoff exceeds its cost is **warranted**.

**Then give each changed unit** (the package, module, or crate that owns each changed source file) **exactly one verdict, from its warranted remedies:**

- **Refactor** - at least one warranted *structural* remedy: fixing an architecture `violation` or `drift`, moving a responsibility to the unit that owns it, collapsing duplicated knowledge that must change in lockstep, or splitting a unit that misses the repo's documented size or readability bar. Each becomes a plan item naming the refactoring that applies it (Extract Function, Move Function, Split Phase, Introduce Parameter Object, Replace Conditional with Polymorphism, Inline Function, ...), so the plan states a concrete change rather than a wish.
- **Polish** - only warranted local remedies (a name, a magic value, a small extraction, comment rot): one small commit's worth, never a restructure.
- **Leave** - no warranted remedy.

A finding whose remedy is not warranted is recorded as a Non-goal with its reason, not planned. An architecture `violation` is always recorded - a planned item when its remedy is warranted and in scope, otherwise a Non-goal naming the violation and why its fix is deferred - and the Step 9 report repeats it.

The **branch verdict** is the strongest unit verdict. **Done when** every changed unit has exactly one verdict with its driving finding IDs and a one-line reason. When every unit is **Leave**, 2b returned `conforms`, and Step 1 found no spec divergence, the plan is short - the verdicts and their evidence - and Step 3 is a single confirmation round.

## Step 3 - Clarify the open questions (`grilling` skill)

Before writing the plan, invoke the **`mattpocock-skills:grilling`** skill with the Skill tool and run its session to completion. It is the skill `/grill-me` loads; call it by that name, because `/grill-me` sets `disable-model-invocation` and the Skill tool refuses it.

Seed the design tree with every genuine judgment call Step 2 surfaced. Ask only where the answer changes the plan; anything the repo's own documented rules already settle is a fact, not a question. Open each question with its recommended answer and the evidence behind it. The recurring branches:

- **Depth.** How aggressive should this pass be - surgical (naming, dead code, local extraction only), moderate (plus deduplication and pattern introduction), or structural (plus package moves and boundary changes)? Recommend from the Step 2d verdicts: all Leave or Polish points to surgical; any architecture violation or cross-unit duplication points higher.
- **Architecture remedies.** For each violation or drift whose fix is structural (a package move, a new port, a split component), fix it in this plan or record it as a deferred Non-goal - with the cost of deferring stated.
- **A genuine design fork.** Where two compliant approaches exist and the repo does not pick one, give the trade-off of each - every option offered complies with the documented rules.
- **Spec divergence found in Step 1.** Make the execution semantics explicit in the options, because this run's default write set is only the plan and tests: **"record it as a correctness item in the plan"** (the code is wrong; the fix is follow-up work for `/implement-plan`), **"update the spec"** (the spec moved on - this edits a spec file, so add it to the write set and re-run the Step 0.7 overlap check on that path now), or **"accepted drift, note only"**. A general bug fix is not on the default menu; if the user wants one now, that is a scope expansion to authorize explicitly, add to the write set, and verify - or to decline and defer.
- **Coverage ambition** (feeds Step 6): a target percentage, or "cover the high-risk paths the plan touches" - the latter is usually the better answer and the one to recommend. Whatever is chosen is checked explicitly in Step 7 **after** the re-measurement.
- **Out-of-scope rot** that the branch's changes made actively harmful: pull it into scope, or leave it and note it.

Depth and coverage ambition are always open, so the session always runs; when Step 2 found little, it is one short round.

**Done when** the frontier is empty (every branch of the design tree visited) and the user has confirmed shared understanding. Then list the **settled decisions** as a numbered list (`D1`, `D2`, ...) in the conversation: Step 4 writes the plan from it, Step 5a hands it to the reviewer, and Step 5c checks findings against it.

## Step 4 - Write the plan to `simplify-<branch-slug>.md`

Write it to the repo's conventional plan location if one exists (`specs/<current-branch>/`, `docs/plans/`, `plans/`), otherwise the repo root. State the path chosen, add it to the write set, and clear it through the Step 0.7 overlap check before writing. **Check first whether that file already exists**: if it does, read it and establish whose it is - a plan for *this* branch from an earlier run is yours to update in place; one whose recorded branch differs (the slug collision from Step 0.5) stays untouched, and you ask for a different filename.

Structure:

- **Scope** - the **exact original branch name** (not just the slug, so a collision is detectable), the base OID, the changed-file set, and the spec it was reviewed against - or explicitly that none was found and which Step 1 option the user chose.
- **Summary** - what is good and worth keeping (say this honestly; a plan that only lists faults misrepresents the branch), then the themes of what needs simplifying, and the branch verdicts from 2b and 2d in one line each.
- **Architecture conformance** - the style and where it is declared (or that it is inferred, and from what), the gate result, gate-coverage gaps, gate-config changes and their rationale records, the branch verdict, and every non-conforming row (`file - component - verdict - rule and source - evidence`). Conforming files go on one line.
- **Refactor verdict** - one row per changed unit: `unit - Refactor | Polish | Leave - driving item IDs - one-line reason`.
- **Findings and items** - the ranked work list. Each item:
  - a stable ID (`S1`, `S2`, ...) so the review and the disposition table can cite it;
  - the site(s) as `file:line`;
  - the standard it violates, **named**, with its source;
  - the concrete change proposed - the named refactoring and exactly what it extracts, renames, moves, or introduces;
  - **behavior-preserving: yes/no** - a `no` makes it a correctness item, sequenced separately and never bundled into a refactor commit;
  - the tests that pin the current behavior, and whether they already exist (this feeds Step 6 directly);
  - effort and risk, one line each.
- **Sequencing** - the order to apply the items, grouped so each group lands as its own reviewable commit, with dependencies between groups called out. Put the items that need a test safety net after the tests that provide it.
- **Test-gap register** - every item whose current behavior is **not** pinned by an existing test, each with the seam (if any) that closing it will need. This is the input to Step 6 and the reason the plan comes before the coverage work.
- **Status** - reserved for Step 7's reconciliation: which gaps this run closed, which seams it extracted, which correctness items it discovered, and which prerequisites are therefore already satisfied when `/implement-plan` picks the file up.
- **Non-goals** - what this pass deliberately leaves alone, and why: pre-existing rot in untouched files, deferred structural work and deferred architecture remedies, anything the user ruled out in Step 3.

Keep it a work list, not an essay. Follow the repo's rules for in-tree documents (many forbid ticket keys or issue IDs in committed files).

## Step 5 - Independent review of the plan, then validate and finalize

The plan **must** be independently reviewed before it is finalized, committed, or published. Codex is the preferred reviewer; 5b is the deterministic substitute; a plan that reached neither is unreviewed and this skill does not finalize it.

### 5a - Codex review (subagent)

Dispatch one subagent that follows `${CLAUDE_SKILL_DIR}/CODEX.md` (pass the absolute path), with the plan path, `$base_oid`, the spec path (or "none found"), the settled decisions `D1...Dn` verbatim, and `"$tmp"`. It drives codex directly - not through the `/codex-review` skill, which runs codex's native code review that cannot carry this focus text and which fixes production code outside this run's write set - enforces a **10-minute** deadline and the liveness rules, saves the raw result to `"$tmp"`, and returns `completed` with the findings verbatim (or exactly "No findings"), or `failed` with the reason. A completed review with no findings is a *passing* review. On `failed`, go to 5b at once: do not retry codex and do not ask whether to retry.

### 5b - Fallback: adversarial subagent review

If 5a returns `failed`, **run the review natively, without asking**. Fan out **2-3 adversarial `general-purpose` subagents in a single message**, each with a distinct lens over the plan, the spec, and the code it cites: (i) are the claimed problems real at the cited lines, and do the architecture verdicts hold against the rules they cite; (ii) is each proposed change actually behavior-preserving, do the correctness items match the spec's acceptance criteria, and does each Leave verdict survive a look for structural findings it ignored; (iii) what did the plan miss - a dependency edge, gate-config change, or misplaced responsibility, duplication, untestable tests - and is the test-gap register accurate? Instruct each to cite plan item IDs or `file:line`, to check every claim against the real code, and to give each finding a confidence, uncertain ones included; style opinions that contradict the repo's conventions are out.

Record in the Step 9 report that the review came from the native fallback and why (codex absent / launch failed / dead pid / stalled / deadline / unusable result). The plan is still reviewed, so this is not a waiver - but it is a **substitution**, and the report must not claim the codex review itself ran.

**If the fallback also fails to complete usably, stop** (a fallback that completes and reports no findings has succeeded). An unreviewed plan is never finalized, committed, pushed, or described as validated; report what failed and end the run.

### 5c - Validate every finding, then finalize

Treat review comments as hypotheses to adjudicate, whatever their source. For each: re-read the cited code and plan item, check it against the repo's documented rules and the Step 3 settled decisions, and mark **accept** (real - fold it in), **reject** (wrong, or it contradicts a rule or a user decision - record why), or **defer** (valid but belongs to a later pass - move it to Non-goals). Scrutinize the usual tendencies: proposing an abstraction where plain code is correct, flagging deliberate test duplication, recommending changes that would alter behavior under the banner of simplification, and calling a sanctioned exception a violation.

Rewrite the plan from the accepted dispositions, then present the disposition table to the user. If an accepted finding would overturn a settled decision, reopen that branch of the design tree and run grilling on it until its frontier is empty again and the user confirms, then update the settled decisions first. A finding showing a settled decision rests on a wrong fact or is unsafe takes the same route before it gets a disposition; only a finding that merely disputes a user choice is rejected.

The plan's **review-derived content** is settled here. Steps 6 and 7 do not reopen the adjudicated findings; they may only add what this run itself discovers - the Status section, corrected citations, and any correctness item a new test uncovers (Step 7).

## Step 6 - Measure coverage and identify the high-priority gaps

Measure over the branch's changed units, not the whole repo - the number that matters is whether *this branch's* code is pinned. Dispatch one subagent that follows `${CLAUDE_SKILL_DIR}/COVERAGE.md` (pass the absolute path) with the changed-file list with statuses and `"$tmp"`. It maps changed files to units, runs the measurement with settings it records for the Step 7 re-run, and returns per-unit and total numbers with the metric and weighting named, plus the least-covered rows. If **no production source changed at all**, there is nothing to measure: record that, finish the plan's Status reconciliation in Step 7, and continue to Step 8 without fabricating a number.

Report the **before** numbers per unit and in total, then rank the gaps. **High-priority** means, in order:

1. **Every item in the plan's test-gap register** - code the plan proposes to change whose behavior nothing currently pins. These are the point of this step: without them the refactor is unverifiable.
2. **Safety-critical or irreversible paths** the branch touched, per the repo's own definition.
3. **Uncovered error and boundary paths** in changed code - the zero/empty/nil case, the overflow case, the invalid input, cancellation and deadline, concurrency.
4. **Changed code at 0% coverage**, whatever it does.

A gap marked `default-tier only` that a tagged tier's tests already pin is not a gap: record which tier pins it and leave it. Everything else is a low-priority gap: list it in the Step 9 report and leave it for later. If the measurement itself fails - a changed unit will not compile, or its tests are already red - stop and ask rather than planning around an unmeasurable unit.

## Step 7 - Close the high-priority gaps, then reconcile the plan

Add each test file to the write set and clear it through the Step 0.7 overlap check before its first edit, and re-verify branch and tip.

Write the tests, test-first in spirit: each new test must **fail for the right reason** against the current code if it is pinning a bug, and pass if it is pinning existing correct behavior - run it and confirm which, rather than assuming. Follow the repo's test idiom as learned in Step 1 (table-driven structure, generated mocks at the port boundary, the project's assertion style, `t.Parallel()` or its equivalent) and hold these tests to the Step 2c test bar - hermetic, deterministic, behavior-focused, diagnostic on failure.

These tests pin **current** behavior. That is the whole point: they are the safety net that will catch a "simplification" that quietly changes what the code does. Each assertion states what the code does today, never what the plan thinks it *should* do.

**If a new test reveals a real bug**, stop and ask - there is no silent path through this. Two options, each with a defined disposition for the failing reproducer:

- **Fix it now** (a scope expansion): add the fix to the write set, clear the overlap check on those paths, fix the bug, and keep the test as its regression test - green, and committed with the fix.
- **Defer it**: the bug stays unfixed, so the committed tree carries no red reproducer. Convert it to a test that pins the **current, buggy** behavior with an explicit comment naming the defect, or lift it out of the tree entirely - save the reproducer to `"$tmp"`, record that path in the plan and the report, and remove its hunks from the active test file. Leaving it merely unstaged is not enough: an unstaged failing test still runs in Step 8's full-suite gate and is still eligible for later path-based staging. Keep the assertion at full strength, and record where any removed evidence went. Record it as a **new correctness item** in the plan (one of the two additions Step 5c permits after finalization, the other being Status), mark the gap **open, not closed**, and surface it in the Step 9 report and the PR body.

If a gap cannot be closed without a production change, make only the **minimal seam** the plan named (extracting a clock, a port, an interface at the consumer). Anything larger is a stop-and-ask: it is no longer a test change.

**Re-measure first, then apply the acceptance gate.** Dispatch the `COVERAGE.md` subagent again with the `SETTINGS` the Step 6 run returned, so the after run uses the **same settings** as the before run, and record the after numbers; state before -> after honestly per unit and in total. Then:

- Keep a gap-by-gap checklist: every high-priority gap from Step 6, each marked `closed` (naming the test that pins it, and confirming the assertion is meaningful - it must be able to fail) or `deferred` with the user's explicit agreement. Advance only when every high-priority gap is in one of those two states.
- If Step 3 set a **numeric target**, compare the re-measured number against it. Missing the target is a stop-and-ask with concrete options, because Step 6 deliberately excluded the low-priority gaps: **authorize specific additional gaps** - name them, and they join the checklist and the write set under the same acceptance rules - or **waive the target explicitly**. An unwaived miss means the plan is **not ready** for handoff in Step 9, and the PR must say so.

**Reconcile the plan.** Update the plan's **Status** section, plus any item whose cited locations the new tests moved, plus any correctness item added above: mark which test-gap-register entries are now closed and by which tests, which seams were extracted, which gaps remain open and why. `/implement-plan` reads this file as its contract, and a plan that still claims work this run already did would have it repeated. If the coverage work surfaced a genuinely new *design* decision (a seam the plan never named, a gap that needs a structural change), route it through Step 3's clarification and note it for the next review pass rather than adding an unreviewed item.

## Step 8 - Format, lint, build, test, then commit, push, and open or update the PR

Re-verify branch and tip before starting, and again before staging, each commit, and the push.

### Gates

Run all four - **format, lint, build, test** - preferring the project's own entrypoints: a Taskfile (`task --list` first), a Makefile, then the language-native fallback. An aggregate target (`task ci`, `make ci`) is a convenience, not a guarantee: **inspect what it actually runs**, and run any of the four it omits separately. Report each gate as pass / fail / **not configured**. Add any check the repo's own rules make mandatory (the architecture gate, mutation testing on safety-critical paths). Tests run over the **whole project**, not just the changed units - that is what catches a seam extraction breaking a distant consumer.

**"Not configured" is an honest outcome, and it does not block.** A repo with no build step has no build gate to fail. Report it as N/A - never as green, never as passed - and name it in both the Step 9 report and the PR body. What blocks is a gate that exists and fails.

**Format means format, then verify.** Apply the formatter and then check that nothing remains:
- Go - `gofmt -w` over the write set (or `task fmt`), then `gofmt -l .` must exit zero **and print nothing**; `-l` only *lists* files needing formatting and exits zero whether or not the list is empty.
- JS/TS - the repo's `format` script, then its check mode.
- Python - `ruff format` then `ruff format --check` and `ruff check`.
- Rust - `cargo fmt` then `cargo fmt --check`, plus `cargo clippy`.

**Keep formatter writes inside the write set.** A repo-wide format entrypoint will reformat files this run never touched, which Step 8 will not commit, leaving the tree dirty and the verified state unreproducible. Scope the formatter to the write set where the tool allows it; otherwise diff the tree afterwards and resolve every file it touched outside the write set (revert it, or get authorization to include it) before staging.

Every gate that exists must pass. If one fails because of this run's changes, fix forward and **re-run all four** - a lint fix can break a test. When a failure's cause is unclear, attribute it with the two comparisons in `PUBLISH.md` section "Attributing a gate failure" before fixing anything.

### Commit, push, PR

Read `${CLAUDE_SKILL_DIR}/PUBLISH.md` and follow its "Commit", "Push", and "PR" sections in order: disjoint per-commit slices staged by literal path and verified as sets; every push and PR action confirmed with the user, showing the destination, the outgoing commits, and the PR decision; the push verified against every push URL; the PR created or updated only after a verified push.

## Step 9 - Report

State, per the repo's handoff checklist if it has one:

- **The plan** - its path, item count, and themes; the spec it was reviewed against, or that none was found and which Step 1 option was chosen.
- **Architecture** - the style and its source, the gate result (pass / fail / not configured / unavailable), the branch verdict (conforms / conforms with drift / violates), and every violation with its disposition (planned item or deferred Non-goal).
- **Refactor verdict** - per unit (Refactor / Polish / Leave) with the one-line reason, and the branch verdict.
- **Review** - codex, or the native fallback **as a substitution** (naming why codex did not run); total findings and the accept/reject/defer breakdown with one-line reasons for every rejection. A clean review reports "no findings", which is a result, not a skip.
- **Coverage** - before -> after per unit and in total, which metric and weighting, the high-priority gaps closed (with the test that pins each), those deferred or left open and why, and the low-priority gaps untouched. If no production code changed, say that instead of a number. If a numeric target was set, state met / waived / missed.
- **Verification** - each gate as pass / fail / not configured, via which toolchain, and any waiver the user granted.
- **Published** - the commits, the push outcome (declined / failed / partial / unverified / succeeded), and the PR URL created or updated - or the exact command left for the user. An unverified push blocks the PR step; say what could not be re-probed.
- **Remaining risk** - deferred findings, Non-goals, correctness items including any bug found and deferred in Step 7, and behavior the new tests still do not pin.
- **Next step** - the refactor is not done. Name the plan file and say whether it is ready for `/implement-plan`: **ready** only when the review ran (codex or fallback), every high-priority gap is closed or explicitly deferred, any numeric target is met or waived, and every configured gate is green. When every unit is Leave and the plan holds no correctness items, say no refactor is warranted and there is nothing for `/implement-plan` to do; correctness items alone still make the plan actionable. Otherwise name exactly what is outstanding.

## Stop-and-ask conditions (use `AskUserQuestion`; never silently proceed)

- Detached `HEAD`; the local branch is the default branch; or `<dest-branch>` resolves to a default or protected branch of the destination repository (Step 0).
- Ambiguous push remote; the base will not resolve or has no merge-base with `HEAD`; an unrecognized diff status (Step 0).
- Anything already staged in the index; a dirty path that this run will write to - checked again as each new write target appears; dirty unstaged/untracked paths the user must decide about (Step 0, Steps 3/4/6/7).
- The branch has no changes against the base - report and stop (Step 0).
- No spec found for the branch (Step 1).
- A gate already red at `<merge-base>` (Step 2a).
- A delegated subagent returns `needs user decision` (any step).
- The judgment calls settled in the Step 3 grilling session (asked as grilling rounds, not `AskUserQuestion`): depth, architecture remedies, a genuine design fork, spec divergence, coverage ambition, out-of-scope rot.
- An accepted review finding would overturn a settled decision (Step 5c; reopen that branch of the grilling session).
- A changed unit will not compile or its tests are already red, blocking measurement (Step 6).
- A new test reveals a real bug - fix now or defer (Step 7).
- Closing a gap needs a production change larger than the minimal seam the plan named (Step 7).
- A numeric coverage target is missed (Step 7).
- The coverage work surfaces a design decision the plan never named (Step 7).
- A gate fails in retained dirty files, fails for a reason proven pre-existing, or causation cannot be established (Step 8).
- A repo-wide formatter modified files outside the write set (Step 8).
- Every push and PR create/update, and each publication stop `PUBLISH.md` names in its "Commit", "Push", and "PR" sections (Step 8).

**Hard stops (report and end the run; not an AskUserQuestion):** neither codex nor the fallback completed a usable review (Step 5b) - a review that completes with no findings is a success, not this condition - and an unreviewed plan is never finalized, committed, or pushed.
