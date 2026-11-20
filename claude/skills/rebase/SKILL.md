---
name: rebase
description: Rebases the current branch onto another branch or remote ref (e.g. origin/main) and leaves it coherent - resolves conflicts, asking on risky ones; reconciles code, tests, docs, specs, and ADRs with the incoming changes; runs codex-review and the project's gates; never pushes. Use whenever the user wants to rebase onto main or another branch, or bring a feature branch up to date with the latest main - including one that has fallen behind or conflicts before a PR. Not for merge commits, interactive history edits (squash, reword, reorder, drop), a quick `git pull --rebase`, or a conflict already in progress.
---

# Rebase skill

Bring `<input>`'s changes into the **current** branch by replaying the current branch's commits on top of `<input>`'s tip. `<input>` is only ever read, and no other branch moves. A clean replay is not the finish line: the rebase resolves *textual* overlap only, so the branch's own code, tests, and docs then have to be made consistent with what `<input>` changed underneath them.

Output: linear history on the current branch, every conflict and reconciliation edit accounted for, a documentation staleness sweep, an adjudicated codex review, green gates, and the user's uncommitted work back where it was.

The repo's `CLAUDE.md` and `AGENTS.md` govern every edit made here; read `AGENTS.md` if it isn't already in context. The skill never pushes: publishing a rewritten branch is the user's call.

## Roles

Within this skill's own steps:

- **Main loop:** every git state change (fetch, stash, rebase, conflict resolution, edits, commits), every `AskUserQuestion`, and the `codex-review` invocation, which then runs its own procedure. State changes run strictly one after another.
- **Reader subagents** (`general-purpose`): the two Step 3 analyses. Each follows a procedure file in `references/`, may build but never edits, and returns a list of sites. They can't ask the user anything, so a question they hit comes back as `needs user decision: <question>` for the main loop to ask.

**Every exit runs Step 6.** Once Step 0 has stashed the user's work, any stop (an abort, a user answering "stop", a failed check) restores the stash before the report, so the user's work is never left hidden.

## Step 0 - Preflight

Stop before touching anything rather than partway through.

1. **Resolve `<input>`** from the argument to a full refname, `refs/heads/<name>` or `refs/remotes/<remote>/<name>`, and use that from here on: a tag or other ref with the same short name otherwise wins silently. With no argument, list `git branch -a --sort=-committerdate` and ask the user to pick, offering the default branch's remote ref (e.g. `origin/main`) first. If the user named a branch to rebase that isn't the current one, ask before checking it out. If `<input>` exists neither locally nor on any remote, tell the user and stop.
   - **Remote ref** (`origin/main`, or a name that exists only on a remote): fetch with an explicit refspec, `git fetch <remote> '+refs/heads/<name>:refs/remotes/<remote>/<name>'`, then `git rev-parse --verify refs/remotes/<remote>/<name>`. A plain `git fetch <remote> <name>` can update only `FETCH_HEAD` in a single-branch or narrowed clone, leaving the tracking ref stale while reporting success. Rebase onto the tracking ref directly; no local branch is needed.
   - **Local branch:** if it tracks a remote, fetch the upstream the same way; if `git rev-list <input>..<input>@{upstream}` is non-empty, the local branch is behind: ask whether to rebase onto the local tip, the upstream tip, or stop.
2. **Check there is something to do.** Record `git branch --show-current` as `<current>`. Stop and tell the user when:
   - `<current>` is empty: a detached HEAD, which is also what a rebase in progress looks like;
   - a merge, cherry-pick, or revert is in progress (`MERGE_HEAD`, `CHERRY_PICK_HEAD`, `REVERT_HEAD`, `rebase-merge`, or `rebase-apply` exists at `git rev-parse --git-path <name>`), since stashing would silently cancel it;
   - `git merge-base --is-ancestor <input> HEAD` succeeds: `<input>` is already in the branch.
3. **Record the fixed points** and echo them in the conversation, so they survive an interrupted session:
   ```bash
   git rev-parse HEAD             # <pre-rebase-sha>: the rollback point
   git rev-parse <input>          # <input-sha>: the new base, and the review base in Step 4
   git merge-base HEAD <input>    # <fork-point>: where the branch left <input>'s history
   ```
   From here on use `<input-sha>`, not the ref, so a fetch mid-run cannot move the base.
4. **Clear the working tree.**
   - Look in `git stash list` for an entry named `rebase <current>`: an interrupted earlier run left it there. Tell the user about it before going on.
   - If `git status --porcelain` is non-empty, ask: stash and continue, or stop. To stash, note `git rev-parse -q --verify refs/stash`, run `git stash push -u -m "rebase <current>"`, then read `refs/stash` again: if it changed, echo the new value as `<stash-oid>`; if not, nothing was stashed. If the tree still isn't clean (a dirty submodule is the usual cause), run Step 6 and stop. The stash stays put until Step 6, so every commit in between is made on a clean tree and the gates test exactly what is committed.
   - Ignored files are never stashed, and git overwrites them without asking. If `<input>` starts tracking a path that is ignored and present here, copy those files to a scratch directory outside the repo and tell the user:
     ```bash
     comm -12 <(git diff --name-only --diff-filter=A <fork-point> <input-sha> | sort) \
              <(git ls-files -o -i --exclude-standard | sort)
     ```

## Step 1 - Survey both sides

Do this in the main loop: Step 2's conflicts are resolved here, so both sides' intent has to be in this context, not a subagent's.

```bash
git log --format='%h %s%n%b' <fork-point>..<pre-rebase-sha>         # the branch's own commits: these get replayed
git rev-list --count <fork-point>..<input-sha>                       # how far behind the branch is
comm -12 <(git diff --name-only <fork-point> <pre-rebase-sha> | sort) \
         <(git diff --name-only <fork-point> <input-sha> | sort)     # <overlap>: files both sides touched
git log --format='%h %s%n%b' <fork-point>..<input-sha> -- <overlap>  # incoming intent where the sides collide
```

The overlap is where conflicts and semantic inconsistencies will be. Read both sides' diffs of those files now; on a large overlap, read each file's two diffs when its conflict comes up instead. If several of the branch's commits touch the same overlapping file, the same conflict will recur as each one is replayed: resolve it the same way each time.

Check two things about the branch's own commits before replaying them:

- **Commits that aren't the branch's own.** If the branch was stacked on another branch that has since been squash-merged into `<input>`, the parent's commits are still in `<fork-point>..<pre-rebase-sha>` and would be replayed against their own squash. Ask the user for the true fork point, set `<fork-point>` to it, and use the `--onto` form in Step 2.
- **Merge commits.** The rebase flattens them: the commits they brought in that `<input>` lacks are replayed, but whatever a merge itself changed (a conflict resolution, a manual fix-up) is not, and range-diff won't show the loss. For each of `git rev-list --merges <fork-point>..<pre-rebase-sha>`, keep the output of `git show --remerge-diff <merge>` when it is non-empty; Step 2 checks those changes survived.

## Step 2 - Rebase

```bash
git rebase --no-update-refs <input-sha>
git rebase --no-update-refs --onto <input-sha> <fork-point>   # instead, when Step 1 moved <fork-point>
```

`--no-update-refs` keeps other local branches where they are even when the user's config sets `rebase.updateRefs`, so the rollback in Step 7 restores everything the rebase moved.

Resolve conflicts yourself, and confirm the risky ones. Record every conflict in a **conflict list** (replayed commit, file, mechanical or risky, resolution); Steps 3, 4, and 7 use it.

- **Mechanical** (one side moved or reformatted code the other edited, import lists, adjacent additions, lockfiles): resolve directly, preserving both intents.
- **Risky** (both sides made meaningful, incompatible changes to the same logic, API signature, test expectation, or doc statement): show the user both sides and your recommendation with `AskUserQuestion` before staging it. Offer concrete resolutions ("keep the branch's signature, port the input's body"; "take the input's version, re-apply the branch's fix on top"), not "ours/theirs".
- Then `git add` the resolved files and `git rebase --continue`.
- `git rebase --skip` drops that commit's changes entirely, so ask before using it.
- If the rebase becomes unrecoverable, or the user stops at a question, `git rebase --abort` returns the branch to `<pre-rebase-sha>` untouched; run Step 6, report, and stop.

When the rebase finishes, check it:

```bash
git merge-base --is-ancestor <input-sha> HEAD                        # must succeed
git range-diff <fork-point>..<pre-rebase-sha> <input-sha>..HEAD
comm -23 <(git diff --name-only <pre-rebase-sha> HEAD | sort) \
         <(git diff --name-only <fork-point> <input-sha> | sort)     # must be empty
```

- **Range-diff.** `=` is a commit replayed unchanged and `!` one that changed. A `!` whose inner diff touches only context lines comes from `<input>` editing nearby code and is expected; one that changes `+`/`-` lines should trace to the conflict list. A `<` with no matching `>` is a commit that no longer exists: git drops a commit whose change is already upstream or that became empty, and a heavily resolved commit can also show as an unmatched `<`/`>` pair. List each dropped commit for the report, and raise any you can't explain with the user.
- **Path check.** The last command lists paths that changed across the rebase although `<input>` never touched them: content the replay lost or altered. Together with the merge changes kept in Step 1 (conflict resolutions are usually redone during the replay; manual fix-ups are not), restore whatever is missing in a reconciliation commit, asking when it isn't clear what the branch meant.

If HEAD is now `<input-sha>`, every commit was already upstream and there is nothing to reconcile or review: run Step 6 and report.

## Step 3 - Reconcile with the incoming changes

Now find the **semantic** inconsistencies: places where the branch's own work no longer agrees with what `<input>` changed under it. Run this step even when the rebase had no conflicts.

Dispatch two reader subagents in a single message; they share no data. Give each the repo path, `<fork-point>`, `<pre-rebase-sha>`, `<input-sha>`, the conflict list, and the absolute path of its procedure in this skill's `references/` directory:

- **Inconsistency hunt** (`references/inconsistency-hunt.md`): stale calls, tests encoding behavior the other side changed, rules one side added that the other breaks, duplicated work, and conflict resolutions that dropped one side's intent.
- **Doc sweep** (`references/doc-sweep.md`): docs, specs, and ADRs the rebase made stale.

Check each returned site against the tree, then fix the ones that hold as minimal edits in the main loop, following the repo's conventions (tests updated alongside behavior, doc style matched). Ask the user about every `needs user decision` they return, and whenever a fix means choosing between the two sides' designs.

Commit the edits on top as one or a few labeled commits (e.g. `Reconcile <area> with <input> changes`), staging by explicit path and following the repo's commit convention. Leave the replayed commits as they are, so the reconciliation stays reviewable on its own.

## Step 4 - Codex review

Invoke the `codex-review` skill, telling it:

- its scope is the **branch delta against `<input-sha>`** (a pinned base), so it reviews what this branch adds on top of `<input>`, the replayed commits plus the reconciliation, and doesn't ask about scope. `<input>`'s own changes were reviewed on their way into that branch;
- the project rules its adjudication must respect are the repo's `CLAUDE.md` / `AGENTS.md` and the standards they cite;
- a gate failure its own fixes didn't cause is not its stop: it reports the failure and returns, and Step 5 triages it;
- the conflict list, so that if codex is unavailable, one of its fallback reviewers takes "conflict resolutions that dropped one side's intent" as its lens.

Put each of its questions to the user. Its final report is not the end of this run: commit its fixes as a labeled commit, staging by explicit path, and continue to Step 5.

## Step 5 - Gates

If `codex-review`'s verification ran format, lint, build, and the full test suite green and nothing has changed since, that result counts. Otherwise run them now over the whole branch with the repo's own commands (task file, Makefile, CI config, `CLAUDE.md`, else the language's standard tools), each with a timeout (`timeout -k 10 900 task ci`, `go test -timeout 600s`).

- **A failure that traces to a resolution or reconciliation edit:** fix forward, commit, and re-run.
- **A failure that looks pre-existing:** run the failing command at `<input-sha>` and at `<pre-rebase-sha>` in throwaway worktrees (`git worktree add --detach <tmp> <sha>`, plus `git submodule update --init` if the repo has submodules; afterwards `git worktree remove --force <tmp>` and `git worktree prune`). If either is red, the failure came with that side: ask whether to fix it here or hand off with it documented. If both are green, the rebase caused it: fix forward. A fresh worktree lacks ignored local config such as `.env`; if the failure could come from that, say the baseline is unreliable rather than calling it pre-existing.
- **A gate the repo doesn't have** is `not configured`, never green.

## Step 6 - Restore the stashed work

Skip this if Step 0 stashed nothing. Otherwise every exit path comes through here.

1. Clear what this run left behind: commit or discard changes Steps 2-5 made but didn't commit, so they can't block the pop or mix into the user's work. Touch nothing this run didn't create, such as the dirty submodule that stopped Step 0.
2. Find the entry by object id, not position, since another stash may have been pushed meanwhile: `git stash list --format='%gd %H'`, matching `<stash-oid>`.
3. Note the untracked files in the stash that now collide with a tracked path; the pop restores everything except these:
   ```bash
   comm -12 <(git ls-tree -r --name-only <stash-oid>^3 2>/dev/null | sort) <(git ls-files | sort)
   ```
4. `git stash pop --index <ref>`, so staged changes stay staged. If `--index` refuses because of index conflicts, the tree is left untouched: run `git stash pop <ref>` and tell the user the staging was not kept.
5. Write each colliding file beside the tracked one, `git show <stash-oid>^3:<path> > <path>.stashed`. Resolve pop conflicts like Step 2's, mechanical ones directly and risky ones through `AskUserQuestion`.
6. A conflicted or partial pop keeps the entry: drop it by its ref only once all of its content is restored. Leave the restored work uncommitted.

## Step 7 - Report

Follow the repo's handoff checklist if it has one. On an early stop, report the same way: what ran, and the state the branch was left in. Cover:

- **What landed:** `<input>` and `<input-sha>`; how many commits were replayed and which were dropped (from the range-diff); `<pre-rebase-sha>` and the new tip; and the rollback, `git reset --hard <pre-rebase-sha>`. Set any restored uncommitted work aside before rolling back, since `--hard` discards it.
- **Publishing:** if the branch tracks a remote, its history was rewritten and the next push needs `git push --force-with-lease`.
- **Conflicts:** each entry of the conflict list, and any content the path check restored.
- **Reconciliation:** each edit, mapped to the inconsistency it fixed, and the build/typecheck result.
- **Doc sweep:** the candidate documents checked, each stale statement fixed, and any left standing with the reason. When nothing was stale, say so: "no docs were stale" is a finding; "docs were not checked" is a gap.
- **Codex review:** accept / reject / defer counts, a one-line reason for each rejection, and whether the review came from codex or the fallback.
- **Gates:** each gate, its command, and its state.
- **Stash:** restored cleanly, or what went differently (staging lost, conflicts resolved, files written as `.stashed`). The restored work was not part of the reconciliation, review, or gates. If any of it couldn't be restored, give `<stash-oid>` and the command to recover it, `git stash apply <stash-oid>`.
- **Remaining risk:** deferred findings, and interactions the gates can't cover.
