---
name: implement-spec
description: "Implement a specification in code. Rebases the PR branch onto the default branch via the rebase-branch skill before any implementation starts."
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

3. Create a branch, and a draft PR. The PR should be marked as 'closing' the spec issue and tickets.

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

   - **Two early exits count as "already current"**, and neither is a failure: `rebase-branch` stops at its preflight when the branch tip *equals* the default ref's tip (the usual outcome for the branch step 3 just created off a freshly fetched default), and stops with "nothing to integrate" when the default ref is already an ancestor of `HEAD`. Record which one occurred and continue. Every other preflight stop is a real stop — never infer a no-op from the branch merely being new.
   - `rebase-branch` owns conflict resolution and its own stop-and-ask gates. Do not pre-empt or auto-answer them; if it aborts, stop here and report rather than launching implementers onto a half-integrated tree.
   - **Its codex review and its format/lint/build/test gates run over the whole repository and are not trivial** — let the full workflow run and honour its verdicts. It is still not the step 8 `/code-review`, which runs over the finished implementation.
   - **Check for an orphaned stash before moving on.** If the tree was dirty, `rebase-branch`'s preflight may have stashed it, and an early preflight exit never reaches the pop. Identify it by **object id**, not name or position — `git stash list` descriptions repeat across sessions and its `stash@{N}` selectors renumber whenever an entry is pushed. Record `git rev-parse --verify --quiet refs/stash` before invoking the skill and re-read it after: unchanged means nothing was stashed here, so restore nothing; changed means the new entry is `stash@{0}` — confirm its id matches. A surviving entry is **not** proof nothing was restored: a `git stash pop` that hit conflicts applies its changes and leaves the entry in place, so popping again would apply them twice. What `rebase-branch` reported (a pop, or a pop conflict) is the primary signal; corroborate with `git status --porcelain`, treating **any** unmerged state as a conflicted restore (`UU`, `AA`, `DD`, `AU`, `UD`, `UA`, `DU`), and with `git stash show --include-untracked -p stash@{0}` — the reference stashes via `stash push -u`, so plain `stash show -p` omits untracked files and makes a partial restore look complete. Only pop — `git stash pop stash@{0}`, naming the selector explicitly — when nothing was applied; otherwise finish resolving, leave the restored work in the working tree as uncommitted **and unstaged** changes (`git restore --staged .` unstages without touching file contents — staged is not the same as uncommitted), and `git stash drop stash@{0}`. If you cannot confirm the entry is fully represented in the tree, keep the stash and say so: an orphaned stash is recoverable, a dropped one is not. Check this on every exit path, including an abort, since `rebase-branch` only reaches its own stash restore in its Step 2.
   - **Synchronize the remote branch yourself — `rebase-branch` never pushes.** Step 3 already pushed this branch to open the draft PR, so: after an early-exit no-op there is nothing to push; after a rebase that only fast-forwards, `git push <remote> <branch>`; only when the replay actually rewrote published commits, `git push --force-with-lease <remote> <branch>`. Name the PR's remote and branch explicitly, and stop on any push failure — a draft PR pointing at an abandoned tip is worse than no push.
   - **Re-read the spec and tickets (step 1) after any rebase that changed the tree**, and **re-validate the step 2 exploration notes against the rebased tree**, updating them in place. Those notes live outside the repository, so the rebase cannot fix stale paths, APIs, or recommendations in them — every implementer subagent reads them as fact.

5. Use **implementer subagents** to implement each ticket. Each implementer subagent should work in its own worktree, on its own branch.

6. Once an **implementer subagent** completes, merge its work to the PR branch with a **merger subagent**.

7. If this changes the **frontier** of available tickets, kick off more **implementer subagents** to work on the new tickets. This allows for maximum concurrency.

8. Once all tickets are complete, run /code-review on the PR branch. Fix all issues raised by the code review in a single **implementer subagent**, and merge that subagent's work back to the PR branch the same way step 6 does — the fixes are not done until they are on the PR branch.

9. **Publish, then** mark the PR as ready for review. Step 4 was the only push so far, and it happened before any implementation: push the PR branch now, require the push to exit zero, and then confirm the **remote's** tip matches local `HEAD` by querying the remote rather than a local tracking ref — `git ls-remote --exit-code <remote> refs/heads/<branch>` and compare the SHA it prints with `git rev-parse HEAD`. `git rev-parse <remote>/<branch>` reads the local remote-tracking ref, which a narrowed fetch mapping can leave stale or absent even after a successful push. A non-zero status or a mismatch is a stop. Marking a PR ready while its commits are local makes reviewers read an empty or stale diff.

10. Clean up all **implementer subagent** worktrees.
