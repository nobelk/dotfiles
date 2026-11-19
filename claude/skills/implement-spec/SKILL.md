---
name: implement-spec
description: "Implements a spec and its tickets (GitHub issues, Jira issues, or /to-tickets local files) as one PR on a single branch. Settles open decisions and each ticket's test seams with the user up front, then runs parallel implementer subagents that follow the tdd skill across the ticket task graph. After implementation it measures coverage of the changed code and confirms with the user which gaps to close, then finds missing end-to-end functional tests and confirms which to add, writing both in parallel. Finishes with /spec-review, /codex-review, and the project's format/lint/build/test gates, and marks the PR ready. Invoke manually with a spec that has tickets."
disable-model-invocation: true
---

# Implement spec

You have been given a spec with tickets that describe how to implement it. The goal is **one PR that implements the entire spec on a single branch**, built test-first and verified end to end.

The tickets are not a list of steps. They are a **task graph** with blocking relationships, so there is always a **frontier**: the tickets whose blockers are all done, which can be worked on right now. Work the frontier with as much concurrency as the graph allows; parallel subagents are the default whenever work shares no files.

Keep communication with subagents sparse. Pass **context pointers** (to the spec, the tickets, the notes directory, the tdd skill, and previous commits) instead of copying their content into prompts.

## Roles

- **Main loop:** every question to the user (`AskUserQuestion`), every Skill invocation (`tdd`, `rebase-branch`, `spec-review`, `codex-review`; skills run in this conversation, not inside subagents), scheduling, merges, the branch, pushes, and the PR.
- **Reader subagents:** exploration of the codebase and docs, and later the coverage run and the end-to-end survey. They write markdown notes to the notes directory and return a short summary.
- **Implementer subagents:** one per frontier ticket (or per part of a split ticket), run in the background with `isolation: "worktree"` so each works on its own branch. They follow the tdd skill at the seams agreed for their ticket, commit on their branch, and return the branch name and a short summary.
- **Test-writer subagents:** like implementers, but they add tests for chosen coverage gaps or end-to-end scenarios.
- **Merger subagent:** merges one finished branch into the PR branch and runs the touched packages' tests there.

Subagents can't ask the user anything. Any question they hit comes back to the main loop as `needs user decision: <question>`, is asked there, and the work is relaunched with the answer.

## Tickets: where they come from

Identify the tracker from the argument, and use the same tracker for the whole run:

| Tracker | Spec and tickets | Blocking edges | Linked in the PR as | Marked done |
|---|---|---|---|---|
| **GitHub** | spec issue and its sub-issues, or issues referencing it (`gh issue view`, `gh issue list`) | native sub-issue/blocking links, else each ticket's "Blocked by" section | `Closes #N` per issue | automatically, when the PR merges |
| **Jira** | spec issue and its child issues or epic children (Atlassian tools: `getJiraIssue`, `searchJiraIssuesUsingJql`) | "is blocked by" issue links, else the ticket's "Blocked by" text | ticket keys (`PROJ-123`) in the PR body, plus the spec key in the title if the repo's convention uses keys | only with the user's OK at the end (Step 10) |
| **Local** (`/to-tickets`) | a spec file plus `.scratch/<feature>/issues/NN-*.md` | each file's `**Blocked by:**` line | the ticket file paths, listed in the PR body | set the file's `**Status:**` to `done` once it is merged |

If the graph has a cycle, or a ticket names a blocker that doesn't exist, ask the user before going further.

## Steps

### 1. Read the spec and tickets (fan out)

Create a **notes directory outside the repo** (`mktemp -d /tmp/implement-spec-XXXX`); every subagent gets a pointer to it. Resolve the **tdd skill path** once, because implementers read it directly:

```bash
ls -d ~/.claude/plugins/cache/claude-plugins-official/mattpocock-skills/*/skills/*/tdd 2>/dev/null | sort -V | tail -1   # -> <tdd-dir>
```

Then, in a single message:
- In the main loop, read the spec, every ticket, and `CLAUDE.md` / `AGENTS.md`, and build the task graph. The repo docs' rules bind every implementer.
- Launch exploration subagents in parallel, one per area the tickets touch (a package, a service, an external API's docs). Each reports the relevant files, existing test patterns and seams, and the gaps between the spec and the code, writing its notes to the notes directory.

If `<tdd-dir>` doesn't resolve, tell the user. Implementers then follow the rules written into Step 4, which are the core of that skill.

### 2. Settle decisions and test seams with the user

Invoke the `mattpocock-skills:tdd` skill with the Skill tool, so its rules on seams shape the questions. It requires every test seam (the public interface a test exercises) to be confirmed with the user before any test is written. Implementers can't ask the user, so that confirmation happens here, for every ticket, before any branch exists.

From the spec, tickets, and exploration notes, draft:
- **Open decisions:** ambiguous acceptance criteria, conflicts between the spec and the code, blocking relationships the tickets imply but don't state, and choices a ticket leaves to the implementer. Each comes with trade-offs and a recommendation.
- **Seams per ticket:** the public interfaces its tests will target, each with a one-line note on what it catches and what it misses.

Finding facts is your job; only decisions go to the user. Ask through `AskUserQuestion` in as few calls as possible. Each call holds up to 4 questions with 2-4 options, so batch:
- One question per open decision, with your recommended option first and marked "(Recommended)".
- One `multiSelect` question per ticket (or per group of small tickets), listing its proposed seams as options. The user can add a seam through "Other".

Write the answers to `decisions.md` in the notes directory: decisions as `D1`, `D2`, ..., then a **Seams** section per ticket. Every implementer and test-writer gets a pointer to it. Then:
- If a decision contradicts the spec or a ticket, ask whether to update that issue's text before the PR links to it.
- If the answers show the spec can't be implemented as written, stop: no branch, no PR.

### 3. Cut the branch from the default branch and open a draft PR

**Preconditions, checked first.** Each failure is a stop:
- `git remote get-url origin` succeeds, and `gh auth status` passes for its host. The skill's output is a PR, so without these there is nothing to deliver.
- Nothing is staged, and no tracked file is modified (`git status --porcelain --untracked-files=no` is empty). The PR branch is checked out in this checkout, and the implementers' worktrees branch from it. Don't stash; ask the user to commit or discard.

**Resolve and refresh the default ref.** Try `git symbolic-ref --short refs/remotes/origin/HEAD`, else parse `ref: refs/heads/<default>` from `git ls-remote --symref origin HEAD`. Then fetch with an explicit refspec, because a narrowed clone can otherwise update only `FETCH_HEAD`:

```bash
git fetch origin '+refs/heads/<default>:refs/remotes/origin/<default>'
git rev-parse --verify refs/remotes/origin/<default>
```

If either fails, stop. Don't fall back to a local `main`, which may be stale. Call the result `<base>` (`origin/<default>`).

**Name the branch** using the repo's convention (`CLAUDE.md`, recent branch names), including a ticket key or issue number if the convention uses one. With no convention, use `implement/<spec-slug>`. If that branch already exists locally or on `origin`, this is a **resume**: go to the section *Resuming an existing branch* below instead.

**Create the branch and the draft PR:**

```bash
git switch --no-track -c <branch> <base>
git commit --allow-empty -m "<subject>"      # GitHub refuses a PR with no commits beyond its base
git push -u origin <branch>
gh pr create --draft --base <default> --head <branch> --title "<title>" --body-file <body-file>
```

The precondition check already guarantees nothing is staged, so the empty commit really is empty. The PR body links the spec and the tickets the way the tracker table says, follows the repo's PR template if there is one, and ends with any trailers the environment requires.

A branch cut from the freshly fetched `<base>` is already current, so no rebase is needed.

#### Resuming an existing branch

Check it out (`git switch <branch>`, which must be clean per the preconditions). Find its PR (`gh pr list --head <branch> --state all`), and note which tickets are already merged on it (from its commit log, or the tickets' status). Then:
- **`git merge-base --is-ancestor <base> HEAD` succeeds:** the branch is current; continue.
- **It's behind, and none of its commits above `<base>` are published** (`git rev-list <base>..origin/<branch>` is empty, or the branch isn't on `origin`): invoke the `rebase-branch` skill with `<base>`. Let its conflict handling and questions run; if it aborts, stop.
- **It's behind, and it has published commits above `<base>`** (the usual case once the draft PR exists): a rebase would need a force-push, which this skill never does. `AskUserQuestion`: **merge `<base>` into the branch** (no history rewrite), **continue as is**, or **stop**.

After any rebase or merge, re-read the spec, tickets, and notes against the updated tree, and fix stale paths or APIs in the notes. Notes live outside the repo, so nothing updates them for you. If a recorded decision or seam no longer holds, ask the user again with `AskUserQuestion` before any implementer starts.

### 4. Work the frontier with parallel implementers

Repeat until every ticket is merged:

1. **Split large tickets.** Before launching a frontier ticket, check whether its work falls into parts that touch disjoint files (separate packages or services) and don't need each other's code. If it does, give each part its own implementer and merge the parts like tickets; the ticket is done when all its parts are merged. If the parts share a file, or one needs another's code, keep the ticket whole. A race over a shared file costs more than the time saved.
2. **Launch** one implementer per frontier ticket or part, in the background, all in a single message. Each gets pointers to: its ticket (and which part, if split), the spec, `decisions.md` (including its seams), the notes directory, `<tdd-dir>/SKILL.md` with its `tests.md` and `mocking.md`, and the PR branch tip it starts from. Instruct each to:
   - First check that its worktree contains that tip (`git merge-base --is-ancestor <tip> HEAD`). If it doesn't, stop and report rather than building on the wrong base.
   - Follow the tdd skill: test through public interfaces at the agreed seams only; red before green; one seam, one failing test, and one minimal implementation per cycle (vertical slices, never all tests first); no tautological or implementation-coupled tests.
   - Return `needs user decision` for anything `decisions.md` doesn't settle, including a seam that isn't listed.
   - Run the touched packages' tests, commit on its branch, and report the red-then-green evidence for each slice.
3. **Answer what comes back.** For a `needs user decision`, ask with `AskUserQuestion`, record the answer in `decisions.md` (marking anything superseded), rework tickets already built on a superseded decision, and relaunch.
4. **Merge** each finished branch with a merger subagent, **one merge at a time**, because concurrent merges into one branch race. The merger runs `git merge --no-ff <ticket-branch>` on the PR branch, resolves conflicts in line with both tickets' intent, and runs the touched packages' tests. If they fail, send the ticket back to an implementer with the failure output.
5. **Mark local tickets done** after their merge (set `**Status:** done`). GitHub and Jira tickets are handled in Steps 3 and 10.
6. **Recompute the frontier** after each merge and launch whatever it unblocked right away, without waiting for the rest of the batch.

### 5. Close coverage gaps in the changed code

Once every ticket is merged, run two reader subagents in parallel, in one message: the coverage run below, and Step 6's end-to-end survey. Both only read, so they don't conflict, and the user can answer both question rounds back to back.

The **coverage subagent**:
- Finds the repo's coverage command (a `coverage` target in its task file or CI, else the language's standard tool: `go test -coverprofile`, `pytest --cov`, `vitest`/`jest --coverage`, `cargo llvm-cov`, ...) and runs it on the PR branch. It also runs it on `<base>` in a throwaway worktree (`git worktree add --detach <tmp> <base>`, removed afterwards) for comparison. Every run gets a timeout.
- Intersects the uncovered lines and branches with the lines this PR changed (`git diff <base>...HEAD`), and groups them by **behavior**, for example "the expired-token path in `auth.Refresh`" rather than "lines 88-94".
- Returns: total coverage and changed-line coverage for the PR vs `<base>`, and each gap with its files, the behavior, the agreed seam that could reach it (or "no agreed seam"), and a recommendation. Code that is genuinely not worth testing (generated, trivially delegating, unreachable defensive branches) is listed as such rather than dropped.

Show the user the summary numbers, then ask which gaps to close with `multiSelect` `AskUserQuestion` questions. Each option is one gap; mark the recommended ones "(Recommended)". With more than 16 gaps, ask about the highest-value ones first and offer the rest in a follow-up call. A gap with no agreed seam comes with a proposed seam to confirm in the same question, because the tdd rule still applies.

Close the chosen gaps with test-writer subagents in parallel, one per group of gaps whose test files don't overlap. Each writes tests at the agreed seam, and then **proves each test can fail**: it temporarily breaks the behavior under test, confirms the test goes red, and restores the code. A test that can't fail adds coverage numbers without protection. If a new test exposes a real bug, the subagent reports it rather than bending the test to fit; fix it with an implementer, test-first. Merge serially as in Step 4, re-run coverage, and keep the before/after numbers for the report.

### 6. Add end-to-end functional tests

The **end-to-end survey subagent** (launched alongside the coverage run):
- Finds the repo's end-to-end or functional suites: `e2e/` or `tests/e2e/` directories, integration build tags or markers, Playwright/Cypress configs, CI jobs that run against a deployed or composed system.
- Maps each user-facing behavior and acceptance criterion in the spec to the existing end-to-end tests that exercise it through the real entry point (CLI, HTTP API, UI, message bus).
- Returns: the behaviors already verified (citing the tests), the behaviors no end-to-end test covers, and for each of those a proposed scenario (name, steps, expected outcome, which suite it belongs in, and any infrastructure it needs).

If the repo has no end-to-end harness at all, say so, and offer adding a minimal one as its own option, with what it would involve.

Ask which scenarios to add with `multiSelect` `AskUserQuestion` questions, one option per scenario, recommended ones first. Write the chosen scenarios with test-writer subagents in parallel, one per scenario or group of scenarios whose files don't overlap, following the suite's existing conventions. Run each new test. If one needs infrastructure that isn't available locally (a database, cloud credentials), report it as **not run** with the reason, never as passing. Merge serially.

### 7. Review against the spec (`spec-review`)

Invoke `spec-review` with `<base>` as its fixed point, so it doesn't stop to ask for one. It now also reviews the tests from Steps 5 and 6. Fix everything it raises with implementer subagents (in parallel when the fixes touch disjoint files, test-first for behavior changes), and merge them as in Step 4. The fixes aren't done until they're on the PR branch.

### 8. Codex review (`codex-review`)

Invoke `codex-review` on the PR branch, naming its scope as the **branch delta against `<base>`**, so it doesn't stop to ask. It adjudicates each finding, fixes the accepted ones, and runs the project's gates. Its questions are the user's to answer; let them through. When it finishes, commit its fixes on the PR branch, staging by explicit path (never `git add -A`) and following the repo's commit convention.

### 9. Verify and publish

**Gates.** The PR goes ready only on green. If `codex-review`'s final verification ran all four gates green and nothing has changed since, that result counts. Otherwise run them now, in order, over the whole branch: **format** (apply, then check), **lint**, **build**, and the **full test suite**, including the end-to-end suites CI runs. Use the repo's own commands from `CLAUDE.md`, the README, CI config, or the task file, and give each one a timeout.
- **A failure caused by this work:** fix it, commit, and re-run all four.
- **A failure that looks pre-existing:** prove it by running the same command on `<base>` in a throwaway worktree. If it fails there too, `AskUserQuestion`: fix it, stop, or mark the PR ready with the failure named in the PR body. If it passes there, the failure is yours.
- **A gate the repo genuinely doesn't have:** report it as `not configured`, never as green.

**Publish:**

```bash
git push origin <branch>                                 # fast-forward only; never --force
git ls-remote --exit-code origin refs/heads/<branch>     # its SHA must equal: git rev-parse HEAD
gh pr ready <branch>
```

Compare against the remote itself, not the local `origin/<branch>` ref, which a narrowed fetch can leave stale. A rejected push, a non-zero exit, or a SHA mismatch is a stop. Marking a PR ready while its commits are local shows reviewers an empty or stale diff.

Update the PR body with: the tickets delivered, the decisions and seams, coverage before and after (total and changed lines), the end-to-end tests added or already covering the spec, the `spec-review` and `codex-review` outcomes, and each gate's state.

### 10. Wrap up

- **Jira:** `AskUserQuestion` whether to transition the delivered tickets (for example to "In Review"), and name the tickets and the target status. Transitioning is visible to the whole team, so it needs an explicit yes.
- **Worktrees:** remove each subagent worktree whose branch is merged (`git worktree remove <path>`, then `git branch -d <branch>`). `-d` refuses to delete an unmerged branch; if it does, report that branch instead of forcing it. Finish with `git worktree prune`.
- **Report:**
  - the PR URL and state, and the tickets delivered with how each was marked;
  - the decisions and seams;
  - parallelism: how many batches, the widest frontier, which tickets were split;
  - coverage: PR vs `<base>`, the gaps closed and the gaps the user left open;
  - end-to-end tests: added, already covering, and not run (with the reason);
  - the `spec-review` and `codex-review` outcomes (accept / reject / defer counts);
  - each gate with its command and state;
  - anything not done, with its reason.
