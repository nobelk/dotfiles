---
name: implement-spec
description: "Implements a spec and its tickets as one PR on a single branch, with parallel implementer subagents working the ticket task graph. Grills the user on open decisions first and rebases the PR branch onto the default branch via the rebase-branch skill before any implementation starts. Invoke manually with a spec that has tickets."
disable-model-invocation: true
---

You have been provided a spec. This spec should have tickets associated with it, describing how to implement the spec.

The goal is a PR which implements the entire spec on a single branch.

The tickets are not a list of steps. They are a **task graph** with blocking relationships between them. This means there is always a **frontier** of tickets which are ready to be grabbed.

Communication to and from subagents should be sparse. Communicate primarily through **context pointers**: to the spec, tickets, research notes, and previous commits. Don't duplicate information already available via pointers.

**Implementer subagents** should be run in the background where possible for **maximum concurrency**.

## Steps

1. Read the spec and tickets. Read enough to understand the task graph.

2. (optional) Use an **exploration subagent** to conduct any exploration required by the tickets - relevant codebase files or external documentation. Ensure the exploration subagent can save files - it should save its markdown notes in a directory outside the repo, accessible by all future subagents. This lets **implementer subagents** focus on implementation rather than exploration.

2a. **Grill the user on the spec before any branch exists.** Invoke the **`grilling`** skill with the Skill tool and run its session to completion. `grilling` is the skill `/grill-me` loads; call it by that name, because `/grill-me` sets `disable-model-invocation` and the Skill tool refuses it.

   Seed the design tree with every gap the spec, tickets, and exploration notes leave open: ambiguous acceptance criteria, conflicts between the spec and the code, blocking relationships the tickets imply but do not state, and decisions a ticket leaves to the implementer. Implementer subagents cannot ask the user, so a decision left open here becomes a guess in a worktree. Facts are your legwork (the exploration subagent, or a new one), never the user's.

   **Done when** the frontier is empty and the user has confirmed shared understanding. Then:
   - Write the **settled decisions** as a numbered list (`D1`, `D2`, ...) to `decisions.md` in the notes directory from step 2 (create one outside the repo if step 2 was skipped). Every implementer subagent, and the step 8 fix subagent, gets a pointer to it.
   - If a settled decision contradicts the spec or a ticket, ask the user whether to update that issue's text before step 3 links the PR to it.
   - If the session shows the spec cannot be implemented as written, stop here: no branch, no draft PR.

3. Create a branch, and a draft PR. The PR should be marked as 'closing' the spec issue and tickets (a `Closes #N` line per issue in the body). GitHub refuses a PR whose head has no commits beyond its base, so give the new branch an empty first commit. `--allow-empty` still commits anything already staged, so first run `git diff --cached --quiet`; if it exits non-zero, stop and ask the user how to handle the staged changes (never commit or push them). Then commit (`git commit --allow-empty -m "<subject>"`), confirm `git diff --quiet HEAD~1 HEAD` exits 0 (the commit changes no files), push it with `git push -u origin <branch>`, then open the PR with `gh pr create --draft`.

4. **Rebase the branch onto the default branch before any implementation work starts.**

   Resolve the default ref and refresh it:

   ```bash
   git symbolic-ref --short refs/remotes/origin/HEAD   # -> e.g. "origin/main", already remote-qualified
   git fetch origin '+refs/heads/<default-branch-name>:refs/remotes/origin/<default-branch-name>'
   git rev-parse --verify refs/remotes/origin/<default-branch-name>   # must succeed before the ref is used
   ```

   Pass the resolved string **verbatim** — it already carries the remote prefix, so never prepend `origin/` to it again. Fetch with the **explicit refspec** shown: a single-branch clone or a narrowed `remote.origin.fetch` can make a plain `git fetch origin <default-branch-name>` land in `FETCH_HEAD` only, leaving `origin/<default-branch-name>` stale or absent while the fetch still reports success.

   If `origin/HEAD` is unset, ask the remote directly with `git ls-remote --symref origin HEAD` and parse its `ref: refs/heads/<default-branch-name>	HEAD` record; then fetch and verify as above, use `origin/<default-branch-name>`, and — **only once that fetch has succeeded** — `git remote set-head origin --auto`, so the next run resolves it from the first command. (That command writes a symref to the remote-tracking ref, so it fails if the ref does not exist yet.) Do **not** fall back to a bare local `main`/`master` of unverified currency: step 3 has already created a draft PR, so a usable remote is a precondition of this whole skill — if the remote is unreachable, the default branch cannot be resolved, or the fetch/verify pair fails, stop and report rather than rebasing onto a stale local tip. Then, from the PR branch:

   ```
   /rebase-branch <resolved-default-ref>
   ```

   Why here: implementer subagents branch their worktrees off this branch, so any drift from the default branch is inherited by every one of them and only surfaces as conflicts at merge time in step 6. Rebasing once, up front, is the cheap version of that work.

   - **Two early exits count as "already current"**, and neither is a failure: `rebase-branch` stops at its preflight when the branch tip *equals* the default ref's tip, and stops with "nothing to integrate" when the default ref is already an ancestor of `HEAD` (the usual outcome for the branch step 3 just created, whose only commit is the empty one). Record which one occurred and continue. Every other preflight stop is a real stop — never infer a no-op from the branch merely being new.
   - `rebase-branch` owns conflict resolution and its own stop-and-ask gates. Do not pre-empt or auto-answer them; if it aborts, stop here and report rather than launching implementers onto a half-integrated tree.
   - **Its codex review and its format/lint/build/test gates run over the whole repository and are not trivial** — let the full workflow run and honour its verdicts. It is still not the step 8 `/spec-review`, which runs over the finished implementation.
   - **Check for an orphaned stash before moving on.** If the tree was dirty, `rebase-branch`'s preflight may have stashed it, and an early preflight exit never reaches the pop. Identify it by **object id**, not name or position — `git stash list` descriptions repeat across sessions and its `stash@{N}` selectors renumber whenever an entry is pushed. Record `git rev-parse --verify --quiet refs/stash` before invoking the skill and re-read it after: unchanged means nothing was stashed here, so restore nothing; changed means the new entry is `stash@{0}` — confirm its id matches. A surviving entry is **not** proof nothing was restored: a `git stash pop` that hit conflicts applies its changes and leaves the entry in place, so popping again would apply them twice. What `rebase-branch` reported (a pop, or a pop conflict) is the primary signal; corroborate with `git status --porcelain`, treating **any** unmerged state as a conflicted restore (`UU`, `AA`, `DD`, `AU`, `UD`, `UA`, `DU`), and with `git stash show --include-untracked -p stash@{0}` — the reference stashes via `stash push -u`, so plain `stash show -p` omits untracked files and makes a partial restore look complete. Only pop — `git stash pop stash@{0}`, naming the selector explicitly — when nothing was applied; otherwise finish resolving, leave the restored work in the working tree as uncommitted **and unstaged** changes (`git restore --staged .` unstages without touching file contents — staged is not the same as uncommitted), and `git stash drop stash@{0}`. If you cannot confirm the entry is fully represented in the tree, keep the stash and say so: an orphaned stash is recoverable, a dropped one is not. Check this on every exit path, including an abort, since `rebase-branch` only reaches its own stash restore in its Step 2.
   - **Synchronize the remote branch yourself — `rebase-branch` never pushes.** Step 3 already pushed this branch to open the draft PR, so: after an early-exit no-op there is nothing to push; after a rebase that only fast-forwards, `git push <remote> <branch>`; only when the replay actually rewrote published commits, confirm with the user via `AskUserQuestion`, then `git push --force-with-lease <remote> <branch>`. Name the PR's remote and branch explicitly, and stop on any push failure — a draft PR pointing at an abandoned tip is worse than no push.
   - **Re-read the spec and tickets (step 1) after any rebase that changed the tree**, and **re-validate the step 2 exploration notes against the rebased tree**, updating them in place. Those notes live outside the repository, so the rebase cannot fix stale paths, APIs, or recommendations in them — every implementer subagent reads them as fact. Re-check `decisions.md` the same way: a settled decision whose premise the rebase changed goes back to the user: reopen that branch and run grilling on it until its frontier is empty again and the user confirms, before any implementer starts.

5. Use **implementer subagents** to implement each ticket. Each implementer subagent should work in its own worktree, on its own branch. An implementer (or the step 8 fix subagent) that meets a decision `decisions.md` does not settle, or finds a settled one rests on a wrong fact or is unsafe, returns `needs user decision` instead of guessing or overriding it; reopen that branch and run grilling on it until its frontier is empty again and the user confirms, record the result in `decisions.md` (marking any superseded decision), rework tickets already built on a superseded decision, and resume.

6. Once an **implementer subagent** completes, merge its work to the PR branch with a **merger subagent**.

7. If this changes the **frontier** of available tickets, kick off more **implementer subagents** to work on the new tickets. This allows for maximum concurrency.

8. Once all tickets are complete, run `/spec-review <resolved-default-ref>` on the PR branch, passing the step 4 default ref as its fixed point so it does not stop to ask for one. Fix all issues raised by the code review in a single **implementer subagent**, and merge that subagent's work back to the PR branch the same way step 6 does — the fixes are not done until they are on the PR branch.

9. **Publish, then** mark the PR as ready for review. Steps 3 and 4 made the only pushes so far, both before any implementation: push the PR branch now, require the push to exit zero, and then confirm the **remote's** tip matches local `HEAD` by querying the remote rather than a local tracking ref — `git ls-remote --exit-code <remote> refs/heads/<branch>` and compare the SHA it prints with `git rev-parse HEAD`. `git rev-parse <remote>/<branch>` reads the local remote-tracking ref, which a narrowed fetch mapping can leave stale or absent even after a successful push. A non-zero status or a mismatch is a stop. Marking a PR ready while its commits are local makes reviewers read an empty or stale diff.

10. Clean up all **implementer subagent** worktrees.
