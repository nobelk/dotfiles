---
name: code
description: "Implements a /spec phase (specs/<name>/) as one PR on its specs/<name> branch. Runs plan.md's task groups as a task graph with parallel implementer subagents that follow the tdd skill and the project's engineering standards, asking the user only what the spec left open. Then runs a /simplify refactor pass, measures coverage of the changed code and confirms which gaps to close, finds missing end-to-end tests and confirms which to add, and finishes with /spec-review, /codex-review, and the project's format/lint/build/test gates before marking the roadmap phase done and the PR ready. Also accepts a spec with tickets (GitHub issues, Jira issues, or /to-tickets files). Invoke manually with a spec name, or from inside a specs/* worktree."
disable-model-invocation: true
---

# Code skill

Build one specced phase to done: **one PR on the phase's `specs/<name>` branch**, carrying the spec, the code, and the tests, built test-first and verified end to end.

This is the last of three stages. `/constitution` set the engineering standards and the quality gates. `/spec` settled this phase's scope, decisions, test seams, and task groups with the user, and pushed them on this branch. So this skill asks the user only what the spec left open and what only built code can show: which coverage gaps and end-to-end scenarios are worth closing.

The work is a **task graph**, not a list of steps. Each task group in `plan.md` is a **task**, and its `Depends on` line names its blockers. There is always a **frontier**: the tasks whose blockers are all merged, which can be worked on right now. Work the frontier with as much concurrency as the graph allows; parallel subagents are the default whenever work shares no files.

The **standards** are `specs/tech-stack.md` (its *Architecture and conventions* and *Testing and quality gates* sections), `CLAUDE.md` / `AGENTS.md` with the docs they cite, and the Standards section of `plan.md`. They bind every subagent that writes code or tests, and they are what the refactor pass and both reviews measure against.

Keep communication with subagents sparse. Pass **context pointers** (paths to the spec files, the standards, the notes directory, the tdd skill, and commits) instead of copying their content into prompts.

The argument is a spec name, a `specs/<name>` branch, or a `specs/<name>/` path. With none, it is the current branch when that is a `specs/*` branch; otherwise ask the user which phase to build. An argument that matches no `specs/` branch or directory is a ticket reference (a GitHub issue, a Jira key, or `/to-tickets` files): read `references/trackers.md` first, which maps tickets onto this same task graph and lists what differs.

## Roles

- **Main loop:** every question to the user (`AskUserQuestion`), every Skill invocation (skills run in this conversation, not inside subagents), scheduling, the PR branch, pushes, and the PR.
- **Reader subagents:** explore the code and docs, and later run the coverage and end-to-end surveys. They write notes to the notes directory and return a short summary.
- **Implementer subagents:** one per frontier task, run in the background with `isolation: "worktree"`. Each follows the tdd skill at its task's seam, commits on its own branch, and returns that branch, its worktree path, and a short summary.
- **Test-writer subagents:** the same, for the chosen coverage gaps and end-to-end scenarios.
- **Merger subagent:** merges one finished branch into the PR branch, in the PR worktree, and runs the touched packages' tests there.

Subagents can't ask the user anything. A question they hit comes back as `needs user decision: <question>`, is asked in the main loop, and the work is relaunched with the answer.

## Step 1 - Enter the phase's worktree

`<branch>` is `specs/<name>`, and `<slug>` is `<branch>` with `/` replaced by `-`. `/spec` put the worktree at `<wt-path>` = `<repo-parent>/<repo-dirname>-worktrees/<slug>`, where the repo is the **main** worktree (the first `worktree` line of `git worktree list --porcelain`), not a linked worktree the session may still be in.

- **Find it.** `git worktree list --porcelain` shows the worktree that has `refs/heads/<branch>` checked out. If none does, attach the branch at `<wt-path>`: `git worktree add <wt-path> <branch>` for a local branch, or, when it is only on `origin`, fetch it (`git fetch origin '+refs/heads/<branch>:refs/remotes/origin/<branch>'`) and run `git worktree add <wt-path> -b <branch> origin/<branch>`. If the branch exists nowhere, the phase hasn't been specced: stop and point the user to `/spec`.
- **Enter it**, unless the session is already there, with the `EnterWorktree` tool (`path: <wt-path>`; it is a deferred tool, so load it with `ToolSearch` first). If the session is inside a different worktree, leave that one first with `ExitWorktree` (`action: "keep"`). Every later command, skill, and subagent then runs in the worktree, and the user's own checkout is never touched. Where the tool isn't available or refuses the path, prefix each command with `cd <wt-path> &&` and give subagents the absolute path.
- **Check the preconditions.** Each failure is a stop:
  - `specs/<name>/plan.md` is on the branch.
  - `gh auth status` passes for `origin`'s host. This skill's output is a PR, so without it there is nothing to deliver.
  - The branch's PR, if it has one, is still open (`gh pr list --head <branch> --state all`). A merged or closed PR means the phase was already delivered or dropped: ask the user what they intend.
  - No tracked file is modified and nothing is staged (`git status --porcelain --untracked-files=no` is empty). Implementers branch from the committed tip and wouldn't see uncommitted edits. Ask the user to commit or discard them; don't stash.
- **Resolve and refresh `<base>`**, the default branch as a remote ref: `git symbolic-ref --short refs/remotes/origin/HEAD` (e.g. `origin/main`), else the `ref: refs/heads/<default>` line of `git ls-remote --symref origin HEAD`. Fetch it with an explicit refspec, because a narrowed clone can otherwise update only `FETCH_HEAD`:
  ```bash
  git fetch origin '+refs/heads/<default>:refs/remotes/origin/<default>'
  git rev-parse --verify refs/remotes/origin/<default>
  ```
  If either fails, stop rather than fall back to a local default branch, which may be stale.
- **Sync with `origin/<branch>`.** `git ls-remote --exit-code origin refs/heads/<branch>` exits 2 when the branch was never pushed; push it now (`git push -u origin <branch>`), because the PR needs it there. Otherwise fetch it with its own explicit refspec and `git merge --ff-only origin/<branch>`, and stop if it can't fast-forward.
- **Check it contains `<base>`.** If `git merge-base --is-ancestor <base> HEAD` fails, the branch is behind the default branch. Its commits are published, so a rebase would need a force-push, which this skill never does. `AskUserQuestion`: **merge `<base>` into the branch** (no history rewrite), **continue as it is**, or **stop**.

## Step 2 - Read the spec and explore (fan out)

Use a **notes directory outside the repo**, `/tmp/code-<slug>`; every subagent gets a pointer to it. If it survives from an earlier run on this branch, keep it: its `decisions.md` holds what the user already answered. Resolve the **tdd skill path** once, because implementers read it directly:

```bash
ls -d ~/.claude/plugins/cache/claude-plugins-official/mattpocock-skills/*/skills/*/tdd 2>/dev/null | sort -V | tail -1   # -> <tdd-dir>
```

If it doesn't resolve, tell the user. Implementers then follow the rules written into Step 5, which are the core of that skill.

Then, in a single message:

- In the main loop, read `requirements.md`, `plan.md`, `validation.md`, and the standards, and build the task graph. A plan whose groups carry no `Depends on` lines predates them: read it as a chain, each group depending on the one before. If the graph has a cycle, or a task depends on one that doesn't exist, ask the user before going further.
- Launch exploration subagents in parallel, one per area the tasks touch (a package, a service, an external API's docs). Each writes to the notes directory: the relevant files, the existing test patterns, whether each task's seam exists as the plan describes it, and any gap between the spec and the code.

## Step 3 - Settle what the spec left open

Start `decisions.md` in the notes directory from the spec: the decisions in `requirements.md` under their own `D` numbers, then a **Seams** section holding each task's seam from `plan.md`. `/spec` confirmed all of these with the user, so they are settled. On a rerun the file already exists: keep the answers recorded there, and ask again only where the code has since moved under one. Every implementer and test-writer gets a pointer to this file.

From the exploration notes, draft only what is still open:

- **Open decisions:** conflicts between the spec and the code as it stands, ambiguous success criteria, a blocker the plan implies but doesn't state, and choices a task leaves to its implementer. Each comes with trade-offs and a recommendation.
- **Unsettled seams:** a task with no seam, or a seam the exploration shows doesn't exist or can't observe the behavior. Propose a replacement, with a one-line note on what it catches and what it misses.

If nothing is open, say so and go on. Otherwise ask through `AskUserQuestion` in as few calls as possible. Each call holds up to 4 questions with 2-4 options, so batch:

- One question per open decision, with your recommended option first and marked "(Recommended)".
- One `multiSelect` question per task whose seams are unsettled, listing the proposed seams. The user can add one through "Other".

When seams are in question, invoke the `mattpocock-skills:tdd` skill first, so its rules on seams shape what you propose.

Record the answers in `decisions.md`. Then:

- If an answer changes what the spec says, edit the spec file to match and commit it on the branch, so the PR's spec and code agree.
- If the answers show the spec can't be built as written, stop before any code is written and send the user back to `/spec` on this branch.

## Step 4 - Open the draft PR

`/spec` already pushed the branch with the spec commit, so the PR can open before any code exists and show reviewers the spec while the work is in flight. If Step 1 found no PR, create it:

```bash
gh pr create --draft --base <default> --head <branch> --title "<title>" --body-file <body-file>
```

The title and body follow the repo's convention and PR template. The body names the roadmap phase, links `specs/<name>/`, and ends with any trailers the environment requires.

An open PR means this is a rerun. The tasks already done are the ones whose merge commit is on the branch (`git log --merges --format=%s <base>..HEAD` names their task branches), and the frontier starts after them.

## Step 5 - Work the frontier with parallel implementers

Repeat until every task is merged:

1. **Split large tasks.** If a frontier task falls into parts that touch disjoint files and don't need each other's code, give each part its own implementer and merge the parts like tasks. Parts that share a file, or that need one another's code, stay together: a race over a shared file costs more than the time saved. Record a split in `decisions.md`, so a rerun knows which parts make up the task.
2. **Launch** one implementer per frontier task or part, in the background, all in a single message. Each gets pointers to its task in `plan.md`, `requirements.md`, `decisions.md`, the standards, the notes directory, `<tdd-dir>/SKILL.md` with its `tests.md` and `mocking.md`, and the PR branch tip `<tip>` (`git rev-parse HEAD`). Instruct each to:
   - Start on its own branch at the tip: `git switch -c <slug>-<unit> <tip>`, where `<unit>` names the work (`g2` for task group 2, `g2a` for a part of it; later `cov1`, `e2e1`, and `fix1` for test-writers and review fixes). An isolated worktree can be cut from the default branch rather than from the PR branch, so it may not contain the tip until this runs.
   - Follow the tdd skill: test through the public interface at the agreed seam only; red before green; one failing test and one minimal implementation per cycle (vertical slices, never all the tests first); no tautological or implementation-coupled tests.
   - Work to the standards and stay inside the task. A change the task doesn't need belongs to another task or to the refactor pass.
   - Return `needs user decision` for anything `decisions.md` doesn't settle, including a seam that isn't listed.
   - Run the touched packages' tests, commit on its branch, and report the branch, the worktree path, and the red-then-green evidence for each slice.
3. **Answer what comes back.** For a `needs user decision`, ask with `AskUserQuestion`, record the answer in `decisions.md` (marking anything superseded), rework tasks already built on a superseded decision, and relaunch. A relaunched or reworked task takes a fresh branch name (`g2-r2`), because the first attempt's branch still exists.
4. **Merge** each finished branch with a merger subagent, **one merge at a time**, because concurrent merges into one branch race. The merger runs `git merge --no-ff --no-commit <task-branch>` on the PR branch, resolves conflicts in line with both tasks' intent, and runs the touched packages' tests. On green it commits with `git commit --no-edit`, keeping git's default merge subject: it names the task branch, which is how a rerun knows the task is done. On red it runs `git merge --abort`, so the PR branch never holds a failing merge, and the task goes back to an implementer with the failure output.
5. **Recompute the frontier** after each merge and launch whatever it unblocked right away, without waiting for the rest of the batch.

## Step 6 - Refactor pass (`simplify`)

The tdd loop is red → green only. It leaves refactoring to this point, when every task is merged and the tests pin the behavior. Invoke the `simplify` skill with the **branch delta** as its target (`<base>...HEAD`, production code and tests) and the standards named as its measure. Tasks built in parallel are where to look hardest: logic two of them each wrote, names that disagree, an abstraction nothing needs yet, code that landed in the wrong layer.

A refactor preserves behavior, and the suite proves it: the tests pass with no assertion or expected value edited. A cleanup that needs one changed is a behavior change, so leave it out and list it in the report. Run the touched packages' tests, then commit on the PR branch, staging by explicit path and following the repo's commit convention.

## Step 7 - Close coverage gaps in the changed code

After the refactor pass, run two reader subagents in parallel, in one message: the coverage run below, and Step 8's end-to-end survey. Both only read, so they don't conflict, and the user can answer both question rounds back to back.

The **coverage subagent**:

- Finds the repo's coverage command (a `coverage` target in its task file or CI, else the language's standard tool: `go test -coverprofile`, `pytest --cov`, `vitest`/`jest --coverage`, `cargo llvm-cov`, ...) and runs it on the PR branch. It also runs it on `<base>` in a throwaway worktree (`git worktree add --detach <tmp> <base>`, removed afterwards) for comparison. Every run gets a timeout.
- Intersects the uncovered lines and branches with the lines this PR changed (`git diff <base>...HEAD`), and groups them by **behavior**: "the expired-token path in `auth.Refresh`" rather than "lines 88-94".
- Returns total coverage and changed-line coverage for the PR vs `<base>`, and each gap with its files, the behavior, the agreed seam that could reach it (or "no agreed seam"), and a recommendation. Code that is genuinely not worth testing (generated, trivially delegating, unreachable defensive branches) is listed as such rather than dropped.

Show the user the summary numbers, then ask which gaps to close with `multiSelect` `AskUserQuestion` questions. Each option is one gap; mark the recommended ones "(Recommended)". With more than 16 gaps, ask about the highest-value ones first and offer the rest in a follow-up call. A gap with no agreed seam comes with a proposed seam to confirm in the same question, because the tdd rule still applies.

Close the chosen gaps with test-writer subagents in parallel, one per group of gaps whose test files don't overlap. Each writes tests at the agreed seam and then **proves each test can fail**: it temporarily breaks the behavior under test, confirms the test goes red, and restores the code. A test that can't fail adds coverage numbers without protection. If a new test exposes a real bug, the subagent reports it rather than bending the test to fit; fix it with an implementer, test-first. Merge serially as in Step 5, re-run coverage, and keep the before/after numbers for the report.

## Step 8 - Add end-to-end functional tests

The **end-to-end survey subagent**:

- Finds the repo's end-to-end or functional suites: `e2e/` or `tests/e2e/` directories, integration build tags or markers, Playwright/Cypress configs, CI jobs that run against a deployed or composed system.
- Maps each user-facing behavior in `requirements.md` and each success criterion in `validation.md` to the existing end-to-end tests that exercise it through the real entry point (CLI, HTTP API, UI, message bus).
- Returns the behaviors already verified (citing the tests), the behaviors no end-to-end test covers, and for each of those a proposed scenario: name, steps, expected outcome, which suite it belongs in, and any infrastructure it needs.

If the repo has no end-to-end harness at all, say so, and offer adding a minimal one as its own option, with what it would involve.

Ask which scenarios to add with `multiSelect` `AskUserQuestion` questions, one option per scenario, recommended ones first. Write the chosen scenarios with test-writer subagents in parallel, one per scenario or group of scenarios whose files don't overlap, following the suite's existing conventions. Run each new test. If one needs infrastructure that isn't available locally (a database, cloud credentials), report it as **not run** with the reason, never as passing. Merge serially.

## Step 9 - Review against the spec (`spec-review`)

Invoke `spec-review` with `<base>` as its fixed point, `specs/<name>/` as the spec, and the standards named as its standards sources. Given the first two it doesn't stop to ask; the third matters because on its own it looks for `CLAUDE.md`-style docs and would miss `specs/tech-stack.md`. It reviews the whole branch, including the tests from Steps 7 and 8. Fix everything it raises with implementer subagents (in parallel when the fixes touch disjoint files, test-first for behavior changes), and merge them as in Step 5. A fix isn't done until it is on the PR branch.

## Step 10 - Codex review (`codex-review`)

Invoke `codex-review` on the PR branch, naming its scope as the **branch delta against `<base>`** so it doesn't stop to ask, and the standards as project rules its adjudication has to respect. It adjudicates each finding, fixes the accepted ones, and runs the project's gates. Its questions are the user's to answer; let them through. When it finishes, commit its fixes on the PR branch, staging by explicit path and following the repo's commit convention.

## Step 11 - Verify and publish

**Gates.** The PR goes ready only on green. If `codex-review`'s final verification ran all four gates green and no code has changed since, that result counts. Otherwise run them now, in order, over the whole branch: **format** (apply, then check), **lint**, **build**, and the **full test suite**, including the end-to-end suites CI runs. Use the repo's own commands, from `specs/tech-stack.md`, `CLAUDE.md`, the README, CI config, or the task file, and give each one a timeout.

- **A failure caused by this work:** fix it, commit, and re-run all four.
- **A failure that looks pre-existing:** prove it by running the same command on `<base>` in a throwaway worktree. If it fails there too, `AskUserQuestion`: fix it, stop, or mark the PR ready with the failure named in the PR body. If it passes there, the failure is yours.
- **A gate the repo genuinely doesn't have:** report it as `not configured`, never as green.

**Close out the spec**, in one docs-only commit after the gates:

- In `validation.md`, tick each checklist box this run verified, noting the test or gate that proves it. Leave manual checks and metrics unticked; they go in the PR body for the reviewer.
- Decide whether `Done when` holds. If only a manual check can show it, ask the user. If it doesn't hold, still push the branch, but leave the PR a draft and the roadmap alone, and say in the report what is missing.
- When it holds, set the phase's `Status:` to `done` in `specs/roadmap.md` (the phase is the one `requirements.md` names in its Context), and change nothing else. It rides in this PR, so the default branch shows `done` exactly when the work merges. Skip it if the roadmap has no status fields.

Re-run the format or lint gate afterwards only if it covers markdown.

**Publish:**

```bash
git push origin <branch>                                 # fast-forward only; never --force
git ls-remote --exit-code origin refs/heads/<branch>     # its SHA must equal: git rev-parse HEAD
gh pr ready <branch>                                     # only when `Done when` holds
```

Compare against the remote itself, not the local `origin/<branch>` ref, which a narrowed fetch can leave stale. A rejected push, a non-zero exit, or a SHA mismatch is a stop: marking a PR ready while its commits are local shows reviewers an empty or stale diff.

Update the PR body with: the tasks delivered, the decisions and seams, what the refactor pass changed, coverage before and after (total and changed lines), the end-to-end tests added or already covering the spec, the `spec-review` and `codex-review` outcomes, each gate's state, and the manual checks left for the reviewer.

## Step 12 - Wrap up

- **Worktrees:** for each subagent worktree, `git worktree remove <path>`, then `git branch -d` its task branch and any branch the harness created for that worktree. Leftover untracked files (build or coverage output) make the removal refuse; when the task branch is merged, `--force` is right. `-d` refuses to delete a branch with unmerged commits; report such a branch instead of forcing it. Finish with `git worktree prune`. The PR worktree stays until the PR has merged.
- **Report:**
  - the PR URL and state, the tasks delivered, and the roadmap phase's status;
  - the decisions and seams settled here, as distinct from the ones the spec already held;
  - parallelism: how many batches, the widest frontier, which tasks were split;
  - the refactor pass: what it changed, and what it left out and why;
  - coverage: PR vs `<base>`, the gaps closed, and the gaps the user left open;
  - end-to-end tests: added, already covering, and not run (with the reason);
  - the `spec-review` and `codex-review` outcomes (accept / reject / defer counts);
  - each gate with its command and state, and the `validation.md` boxes still unticked;
  - anything not done, with its reason.
