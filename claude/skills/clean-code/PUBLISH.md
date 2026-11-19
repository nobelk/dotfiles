# Publishing (clean-code Step 0 fork case and Step 8)

Main-loop procedures for the fork case, gate-failure attribution, commit, push, and PR. The conventions in `SKILL.md` ("Conventions for every command in this skill") apply to every command here.

## Fork case

Read this at Step 0 when `<push-remote>` is a fork (`gh repo view <owner>/<repo> --json isFork,parent` for the push remote's repository), or at Step 8 when the PR identities are resolved.

Two refs are distinct here, and neither stands in for the other:

- `<default-branch-name>` on `<push-remote>` is **only** what Step 0.4 guards the destination against.
- The **review base** - what the branch's changes are diffed against, and what the PR will merge into - is `<pr-base>` in `<pr-repo>`, which for a fork is the upstream repository's default branch, not the fork's.

Resolve `<pr-repo>` and `<pr-base>` before computing the base. Fetch and pin the base from `<pr-repo>`'s default branch with an explicit refspec (adding it as a remote, or fetching by URL, if no remote points there), set `$base_oid` and `$merge_base` from it, and say which repository the base came from. `gh` can select a different repository than git does, so pass `--repo "$pr_repo"` on every `gh` subcommand that accepts it; `gh api` has no `--repo` and takes the repository in its path instead, plus `--hostname` for a host other than github.com.

## Attributing a gate failure

Attributing a failure takes two comparisons, in order, and neither alone is conclusive. A filename is weak evidence: a new seam can break an unchanged assertion inside a dirty test file, and a dirty config file can break a clean source file.

**First, rule out the retained dirt** (skip this when the Step 0.7 retained set is empty):

```bash
stash_before=$(git rev-parse --verify --quiet refs/stash)    # may be empty: no stash ref yet
git --literal-pathspecs stash push -u -- "${retained[@]}"
stash_after=$(git rev-parse --verify --quiet refs/stash)
[ -n "$stash_after" ] && [ "$stash_after" != "$stash_before" ] || stop   # this run created no stash
# ... re-run the failing command ...
git stash apply "$stash_after" || stop                       # restore this run's stash by object id; stop on conflict
ref=$(git stash list --format='%gd %H' | awk -v id="$stash_after" '$2 == id {print $1}')
[ -n "$ref" ] && git stash drop "$ref"                       # re-find its current selector only to drop it
```

`--literal-pathspecs` is required: `--` marks the arguments as pathspecs but does not make them literal, so a retained filename containing `*` or `[` would match extra files - and an **empty** array drops the path restriction entirely and stashes this run's own work, destroying the very comparison you are making.

Identify the stash by **object id**, not by existence: `refs/stash` resolving proves only that *some* stash exists, and a `stash push` that matched nothing still exits zero, leaving an unrelated older entry at `stash@{0}` that a bare `git stash pop` would then restore and drop. The stash stack is shared with other worktrees and sessions, so by the time the re-run finishes `stash@{0}` can be another session's entry. If no new stash was created, the comparison cannot be made - treat causation as unresolved rather than re-running against an unchanged tree.

- **Passes without the dirt** -> the failure is the user's retained work. Report it, leave it unfixed, and ask whether to remediate or re-verify against a clean state.
- **Still fails without the dirt** -> **"not explained by retained dirt"**, which is *not* the same as "caused by this run": a pre-existing failure also survives dirt removal. Go on to the second comparison.
- **Comparison impossible or inconclusive** -> causation is **unresolved**; say so rather than guessing an owner.

**Second, rule out a pre-existing failure** by reproducing the exact command against `<starting-commit>` in a throwaway worktree, where both this run's changes and the retained dirt are absent:

```bash
tmp_wt=$(mktemp -d)
git worktree add --detach "$tmp_wt" "$starting_commit"
# ... run the failing command there ...
git worktree remove --force "$tmp_wt"
```

Failing there too makes it pre-existing - stop and ask whether to fix it, abort, or proceed with a documented waiver. Passing there makes it yours to fix. If you cannot reproduce it either way, causation is unresolved; offer the waiver only as unproven.

## Commit

Take the accumulated write set - the plan file, the test files, any authorized seam, spec edit, or bug fix - **minus** the Step 0.7 pre-existing dirty set and every scratch file. Split it into **disjoint per-commit slices**: the tests and seams; the bug fix with its regression test; any authorized spec edit (with the plan, since both record intent, unless the repo's convention separates them); the plan document. Slices are by **file**, so a file cannot appear in two: if one test file holds both ordinary coverage tests and a bug's regression test, put the whole file in the bug-fix slice, since that is the commit a reviewer will bisect to, and say so in the message. Keep to whole files; partial-hunk staging is out. **Create a commit only for a slice that is actually non-empty** - a run whose coverage was already adequate legitimately has no test slice. Run this cycle once per non-empty slice, and stage paths explicitly (never `git add -A`):

```bash
git --literal-pathspecs add -- "${slice[@]}"
git --literal-pathspecs diff --cached --name-only -z --no-renames   # compare set-equal to this slice
git diff --cached --check                                           # whitespace errors / conflict markers
git diff --cached                                                   # read the content before committing
```

Quote every path and pass `--literal-pathspecs`: a filename containing `*`, `:`, or a leading `!` is a pathspec pattern to git and can pull in files outside the slice. Pass `--no-renames` on the verification listing - rename detection reports one path where two are staged. **Compare the staged list against the slice as sets**; listing paths is not verifying them. Unstage anything unintended (`git --literal-pathspecs restore --staged -- "$path"`) and re-check. An unexpectedly empty index for a slice you believed non-empty is a stop - check whether this is a re-run where that commit already exists before concluding either way.

Commit in the repo's own convention - match the recent `git log` subject style (ticket-key prefix, Conventional Commits, whatever the log shows) and include the trailers the repo or environment requires, omitting any the repo forbids. **After each commit check what the hooks did** (`git show --stat HEAD`, `git status --porcelain`): a `pre-commit` hook can reformat or re-stage files, so the committed tree may not be the tree the gates verified. If content changed, re-run the gates over the new state before committing anything further or pushing. When the last commit is in, confirm the union of the commits equals the intended write set and that the committed state - not just the working tree - is the state that tested green.

## Push

Pushing is outward-facing and hard to walk back, so show the destination and get explicit `AskUserQuestion` confirmation every time. First establish what is actually out there, distinguishing "no such branch" from "could not reach the server":

```bash
push_urls_raw=$(git remote get-url --push --all "$push_remote") || stop   # capture status, don't hide it
push_urls=(); while IFS= read -r u; do [ -n "$u" ] && push_urls+=("$u"); done <<< "$push_urls_raw"   # pushurl is multi-valued
[ "${#push_urls[@]}" -gt 0 ] || stop
```

Read `git remote get-url` from a captured variable, not a process substitution: the reading loop reports its *own* success, so a failing git call would yield an empty array and every endpoint check below would silently pass over nothing.

**Probe the push URLs themselves, always - not the remote name, and not only when there are several.** A remote's `pushurl` can differ from its fetch URL even when there is exactly one, so `git ls-remote "$push_remote"` can report the state of an endpoint this push will never touch:

```bash
for url in "${push_urls[@]}"; do
  git ls-remote --exit-code "$url" "refs/heads/$dest_branch"   # 0 = exists, 2 = absent, other = failure
done
```

Record each endpoint's exit status and OID as its own row. If there is more than one push URL, say so before confirming - a push fans out to all of them and they can diverge.

**Exit 2 everywhere** means the destination does not exist: say plainly that a **new remote branch will be created**, and list the commits relative to the base OID. **Exit 0** on an endpoint gives you its OID: **fetch that object from that URL** so the local repo actually has it (a narrowed clone will not), then compute the outgoing commits against it - not against a local tracking ref, which a narrowed refspec can leave stale or absent. Where endpoints hold different OIDs, evaluate the range against the one furthest behind, since that is what the push must fast-forward:

```bash
git fetch "$url" "$remote_oid" || git fetch "$url" "refs/heads/$dest_branch"
git rev-parse --verify "$remote_oid^{commit}" || stop     # object present locally?
git log --oneline "$remote_oid..HEAD" --
git merge-base --is-ancestor "$remote_oid" HEAD; echo "$?"   # 0 = fast-forward, 1 = not, >1 = command error
```

Distinguish `is-ancestor` exit 1 (genuinely not a fast-forward) from exit >1 (the command itself failed) - treat the latter as unknown and stop. Any other `ls-remote` exit is a transport or auth failure - stop and ask rather than confirming a destination you could not read.

Present the remote, the destination ref, the push URL(s) - **credentials redacted**, since an HTTPS remote can embed `user:token@`; show `https://***@host/path` - and the outgoing commit list: a branch can carry local commits the user forgot about, and "push this branch" is not consent to publish those unseen. Include the pull-request decision from the PR lookup below (create / update #N / skip and why), run read-only **before** this confirmation, so the user approves what will actually happen. If the push would not be a fast-forward, stop and ask; `--force` is the user's call alone.

On confirmation, push explicitly and verify the server took it:

```bash
git push "$push_remote" "HEAD:refs/heads/$dest_branch"   # add -u only if no upstream is set
push_status=$?
head_oid=$(git rev-parse HEAD)
for url in "${push_urls[@]}"; do
  git ls-remote --exit-code "$url" "refs/heads/$dest_branch"   # re-probe every endpoint
done
```

**Re-probe every push URL afterwards, whatever the push exit was** - a fan-out can partially succeed, so a non-zero status does not mean nothing landed. Classify from the **endpoint OIDs against `$head_oid`** first, and use the push's exit status only to explain the result:

- **Every endpoint at `$head_oid`** -> **succeeded** (name a non-zero push exit as an anomaly, but the refs are where they should be).
- **Some at `$head_oid`, some not** -> **partial publication**. Name which URL holds which OID, and which endpoints still need the push. Endpoint disagreement is evidence of a *partial* push only when at least one endpoint moved to `$head_oid`; pre-existing divergence with none advanced is a wholly failed push.
- **No endpoint at `$head_oid`** -> **failed**. Stop and report the exact push error.
- **The user declined** -> **declined**: nothing was pushed and the PR step does not run.

If any endpoint cannot be re-probed, the outcome is **unverified** - report it as such, and hold the PR step until the push is verified.

## PR

Decide before the push confirmation (the lookup is read-only); create or edit only after a verified successful push, re-running the lookup first and stopping to ask if its result changed since the user confirmed. Resolve the PR identities explicitly - they are not the git ones:

- `<pr-repo>` - the repository the PR lives in; pass `--repo` on every `gh` subcommand that accepts it rather than trusting `gh`'s own inference, which can differ from git's (`gh api` names the repository in its path, and takes `--hostname` for a non-github.com host).
- `<pr-head>` - the head as the **create** call needs it: `<dest-branch>` when the PR is opened in the same repository, and the qualified `<owner>:<dest-branch>` when `<push-remote>` is a fork (`<owner>` being the fork's owner). Keep `<dest-branch>` unqualified for the listing call below, which does not accept the qualified form.
- `<pr-base>` - the default branch **of `<pr-repo>`** (the "Fork case" value when the push remote is a fork).

```bash
gh pr list --repo "$pr_repo" --head "$dest_branch" --state all --limit 100 \
  --json number,url,state,isDraft,headRefName,baseRefName,headRepository,headRepositoryOwner
```

Use `gh pr list`, not `gh pr view --head` - `gh pr view` has no `--head` flag. Pass `--head` the **unqualified** branch name. Leave `--base` off: it filters on the server, so a PR from this branch into a different base would vanish and this skill would open a duplicate. Because several forks can offer the same branch name, select the match by `headRepositoryOwner` / `headRepository` (compared case-insensitively) and then check its `baseRefName`. If the result comes back at the limit (`gh pr list` has no pagination cursor), re-run with a larger one before concluding there is no match. A successful call returning `[]` means no PR; a **non-zero exit** is a syntax, auth, or transport failure and a stop, not an absence.

- **No PR** -> `gh pr create --repo "$pr_repo" --base "$pr_base" --head "$pr_head" --title "$title" --body-file "$tmp/pr-body.md"`. Always `--body-file` from outside the repo; a long body through `--body` gets mangled by shell quoting. **A fork owned by an organization** (`gh api "users/$fork_owner" --jq .type` prints `Organization`) cannot use the `<owner>:<branch>` head: `gh pr create` does not support an organization there. Create it through the REST API instead: `gh api --method POST "repos/$pr_repo/pulls" -f title="$title" -F body=@"$tmp/pr-body.md" -f base="$pr_base" -f head="$fork_owner:$dest_branch" -f head_repo="$fork_repo_name"`.
- **An open PR whose head repo/owner and base match** -> `gh pr edit "$number" --repo "$pr_repo" --body-file "$tmp/pr-body.md"`. Preserve anything a human added - append or amend a clearly-marked section rather than overwriting someone else's text.
- **Only closed or merged matches**, or an open match whose base is not `<pr-base>` -> stop and ask. Reopening a PR or retargeting its base is the user's call.

The body follows the repo's PR conventions (title format, headings, audience, banned content) and states: what the branch does (from the spec, or that no spec was found); the architecture verdict and the refactor verdict in plain language; that a simplification plan was produced, where it lives, and that **the simplification itself is not implemented** - the plan's items are pending follow-up for `/implement-plan` (or, when every unit is Leave and no correctness item remains, that none is needed); what this run *did* deliver (the tests, plus any authorized seam, spec edit, or bug fix, each named); coverage before -> after with the high-priority gaps closed and any deferred or left open; whether the plan's review was codex or the native fallback; the gates that ran, including any N/A or waived; and the plan's Non-goals as explicit follow-up. Include the trailers the environment requires for PR descriptions. If `gh` is unavailable or unauthenticated (`gh auth status --hostname <host>`), record **skip** as the PR decision and still offer the push - report the exact command the user should run, and say the PR step was not completed.
