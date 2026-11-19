---
name: implement-spec
description: "Implements a spec and its tickets (GitHub issues, Jira issues, or /to-tickets local files) as one PR on a single branch, with parallel implementer subagents working the ticket task graph. Grills the user on open decisions first, cuts the branch from a freshly fetched default branch and opens a draft PR, then implements, merges, runs /spec-review and /codex-review plus the project's format/lint/build/test gates, and marks the PR ready. Invoke manually with a spec that has tickets."
disable-model-invocation: true
---

# Implement spec

You have been given a spec with tickets that describe how to implement it. The goal is **one PR that implements the entire spec on a single branch**.

The tickets are not a list of steps. They are a **task graph** with blocking relationships, so there is always a **frontier**: the tickets whose blockers are all done, which can be worked on right now. Work the frontier with as much concurrency as the graph allows.

Keep communication with subagents sparse. Pass **context pointers** (to the spec, the tickets, the notes directory, and previous commits) instead of copying their content into prompts.

## Roles

- **Main loop:** the grilling session, every `AskUserQuestion`, every Skill invocation (`rebase-branch`, `spec-review`, `codex-review`; the Skill tool can't run inside a subagent), scheduling the frontier, the branch, pushes, and the PR.
- **Exploration subagent** (optional): reads the codebase and external docs the tickets need, and saves markdown notes to the notes directory.
- **Implementer subagents:** one per ticket, run in the background with `isolation: "worktree"` so each works on its own branch. Each one works test-first, runs the tests of the packages it touched, commits on its branch, and returns the branch name and a short summary.
- **Merger subagent:** merges one finished ticket branch into the PR branch and runs the touched packages' tests there.

## Tickets: where they come from

Identify the tracker from the argument, and use the same tracker for the whole run:

| Tracker | Spec and tickets | Blocking edges | Linked in the PR as | Marked done |
|---|---|---|---|---|
| **GitHub** | spec issue and its sub-issues, or issues referencing it (`gh issue view`, `gh issue list`) | native sub-issue/blocking links, else each ticket's "Blocked by" section | `Closes #N` per issue | automatically, when the PR merges |
| **Jira** | spec issue and its child issues or epic children (Atlassian tools: `getJiraIssue`, `searchJiraIssuesUsingJql`) | "is blocked by" issue links, else the ticket's "Blocked by" text | ticket keys (`PROJ-123`) in the PR body, plus the spec key in the title if the repo's convention uses keys | only with the user's OK at the end (Step 9) |
| **Local** (`/to-tickets`) | a spec file plus `.scratch/<feature>/issues/NN-*.md` | each file's `**Blocked by:**` line | the ticket file paths, listed in the PR body | set the file's `**Status:**` to `done` once it is merged |

If the graph has a cycle, or a ticket names a blocker that doesn't exist, ask the user before going further.

## Steps

### 1. Read the spec and tickets

Read the spec and enough of each ticket to build the task graph. Also read `CLAUDE.md` / `AGENTS.md`; their rules bind every implementer.

Create a **notes directory outside the repo** (`mktemp -d /tmp/implement-spec-XXXX`); every subagent gets a pointer to it. Optionally, run the exploration subagent now so implementers can focus on implementing instead of exploring.

### 2. Grill the user before any branch exists

Invoke `mattpocock-skills:grilling` with the Skill tool and run its session to completion. It is the skill `/grill-me` loads; call it by this name, because `/grill-me` sets `disable-model-invocation` and the Skill tool refuses it.

Seed the design tree with every gap the spec, tickets, and notes leave open: ambiguous acceptance criteria, conflicts between the spec and the code, blocking relationships the tickets imply but don't state, and decisions a ticket leaves to the implementer. Implementer subagents can't ask the user, so a decision left open here becomes a guess in a worktree. Facts are your legwork, never the user's.

**Done when** the frontier is empty and the user confirms you share an understanding. Then:
- Write the settled decisions as `D1`, `D2`, ... to `decisions.md` in the notes directory. Every implementer, and the fix subagents later, gets a pointer to it.
- If a decision contradicts the spec or a ticket, ask whether to update that issue's text before the PR links to it.
- If the session shows the spec can't be implemented as written, stop: no branch, no PR.

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

After any rebase or merge, re-read the spec, tickets, and notes against the updated tree, and fix stale paths or APIs in the notes. Notes live outside the repo, so nothing updates them for you. A settled decision whose premise changed goes back to the user via grilling before any implementer starts.

### 4. Work the frontier

Repeat until every ticket is merged:

1. **Launch** one implementer subagent per frontier ticket, in the background, in a single message. Each gets pointers to: its ticket, the spec, `decisions.md`, the notes directory, and the PR branch tip it starts from. Its first check is that its worktree contains that tip (`git merge-base --is-ancestor <tip> HEAD`); if it doesn't, it stops and reports rather than building on the wrong base.
2. **On a decision the notes don't settle**, an implementer returns `needs user decision` instead of guessing. Reopen that branch of the design tree with grilling, record the answer in `decisions.md` (marking anything superseded), rework tickets already built on a superseded decision, and relaunch.
3. **Merge** each finished ticket with a merger subagent, **one merge at a time**, because concurrent merges into one branch race. The merger runs `git merge --no-ff <ticket-branch>` on the PR branch, resolves conflicts in line with both tickets' intent, and runs the touched packages' tests. If they fail, send the ticket back to an implementer with the failure output.
4. **Mark local tickets done** after their merge (set `**Status:** done`). GitHub and Jira tickets are handled in Steps 3 and 9.
5. **Recompute the frontier** after each merge and launch whatever it unblocked right away, without waiting for the rest of the batch.

### 5. Review against the spec (`spec-review`)

Once every ticket is merged, invoke `spec-review` with `<base>` as its fixed point, so it doesn't stop to ask for one. Fix everything it raises in a single implementer subagent, branched from the current PR branch tip, and merge that branch the same way as in Step 4. The fixes aren't done until they're on the PR branch.

### 6. Codex review (`codex-review`)

Invoke `codex-review` on the PR branch, naming its scope as the **branch delta against `<base>`**, so it doesn't stop to ask. It adjudicates each finding, fixes the accepted ones, and runs the project's gates. Its questions are the user's to answer; let them through. When it finishes, commit its fixes on the PR branch, staging by explicit path (never `git add -A`) and following the repo's commit convention.

### 7. Verify: format, lint, build, full tests

The PR goes ready only on green. If `codex-review`'s final verification ran all four gates green and nothing has changed since, that result counts. Otherwise run them now, in order, over the whole branch: **format** (apply, then check), **lint**, **build**, and the **full test suite**, including any integration or e2e suites CI runs. Use the repo's own commands from `CLAUDE.md`, the README, CI config, or the task file, and give each one a timeout.

- **A failure caused by this work:** fix it, commit, and re-run all four.
- **A failure that looks pre-existing:** prove it by running the same command on `<base>` in a throwaway worktree (`git worktree add --detach <tmp> <base>`, then remove it). If it fails there too, `AskUserQuestion`: fix it, stop, or mark the PR ready with the failure named in the PR body. If it passes there, the failure is yours.
- **A gate the repo genuinely doesn't have:** report it as `not configured`, never as green.

### 8. Publish and mark ready

```bash
git push origin <branch>                                 # fast-forward only; never --force
git ls-remote --exit-code origin refs/heads/<branch>     # its SHA must equal: git rev-parse HEAD
gh pr ready <branch>
```

Compare against the remote itself, not the local `origin/<branch>` ref, which a narrowed fetch can leave stale. A rejected push, a non-zero exit, or a SHA mismatch is a stop. Marking a PR ready while its commits are local shows reviewers an empty or stale diff.

Update the PR body with: the tickets delivered, the decisions recorded, the `spec-review` and `codex-review` outcomes, and each gate's state.

### 9. Wrap up

- **Jira:** `AskUserQuestion` whether to transition the delivered tickets (for example to "In Review"), and name the tickets and the target status. Transitioning is visible to the whole team, so it needs an explicit yes.
- **Worktrees:** remove each implementer worktree whose branch is merged (`git worktree remove <path>`, then `git branch -d <ticket-branch>`). `-d` refuses to delete an unmerged branch; if it does, report that branch instead of forcing it. Finish with `git worktree prune`.
- **Report:** the PR URL and state; tickets delivered and how each was marked; the decisions; parallelism (how many batches, the widest frontier); the `spec-review` and `codex-review` outcomes (accept / reject / defer counts); each gate with its command and state; and anything not done, with its reason.
