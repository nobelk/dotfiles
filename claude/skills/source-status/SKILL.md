---
name: source-status
description: Sync every intramotev git repo under ~/sources to its default branch, review the last three days of commits and PRs against it as a principal engineer, and write an adversarially-verified summary of key changes and critical issues (under 450 words) to ~/sources/review/source_summary_MM_DD_YY.md.
disable-model-invocation: true
---

# Source status

Produce a short, accurate, evidence-backed status report covering the last three days of work across the intramotev repos in `~/sources`. Act as a principal software engineer: the report is a **triage**, not a changelog. Only key changes and critical issues earn a line.

Flow: fix the window → discover repos → sync each to its default branch → collect commits and PRs → review active repos in parallel subagents → draft → adversarial verification → write the file → chat summary.

"Main branch" means each repo's GitHub default branch (`main` for every intramotev repo today).

## Step 0 — Fix the window

Capture both bounds once, before any sync, and reuse them in every later command and prompt:

```bash
NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
SINCE=$(date -u -d "$NOW - 72 hours" +%Y-%m-%dT%H:%M:%SZ)   # GNU date; on macOS: date -u -v-72H +%Y-%m-%dT%H:%M:%SZ
```

Activity after `$NOW` is out of scope even if a later query returns it.

## Step 1 — Discover repos

A repo is in scope when all of these hold:

- It is a top-level directory of `~/sources` (depth 1 only).
- Its name does not end in `-worktrees`.
- It is a main working tree, not a linked worktree: the two lines of `git rev-parse --path-format=absolute --git-dir --git-common-dir` are equal.
- Its origin owner is exactly `intramotev` on `github.com`. Match all three URL forms, with or without `.git`: `https://github.com/intramotev/<repo>`, `ssh://git@github.com/intramotev/<repo>`, `git@github.com:intramotev/<repo>`. Personal repos (e.g. `nobelk/*`) are out of scope.

Done when: you hold a list of `(dir, owner/repo)` pairs, and every skipped top-level directory has a one-word reason (not-git, worktree, personal).

## Step 2 — Sync each repo to its default branch

Run per repo, sequentially, from the repo dir. Each repo ends in exactly one sync state: `synced`, `stashed+synced`, `review-only (<reason>)`, or `stale (<reason>)`.

1. Resolve the default branch from GitHub, the source of truth:
   `DEFAULT=$(gh repo view <owner/repo> --json defaultBranchRef -q .defaultBranchRef.name)`. If that fails or is empty, fall back to `git symbolic-ref --short refs/remotes/origin/HEAD | sed 's@^origin/@@'`. If both fail, mark the repo `incomplete (no default branch)` and skip to the next repo.
2. `git fetch --prune origin "+refs/heads/$DEFAULT:refs/remotes/origin/$DEFAULT"`. If fetch fails, mark `stale (fetch failed)`, skip steps 3–5, and review the existing `origin/$DEFAULT` with that caveat carried into the report. If `origin/$DEFAULT` does not exist locally either, mark `incomplete (no default ref)`: skip git collection for this repo but still collect and review its PRs.
3. Record the current branch and `git rev-parse HEAD`. If `git status --porcelain` is non-empty, run
   `git stash push -u -m "source-status $(date +%F) from <branch>"`. Then confirm both: the stash command exited 0, and `git status --porcelain` is now empty. Record the stash ref (`git rev-parse stash@{0}`). If either check fails (unmerged files, submodule changes), mark `review-only (stash failed)` and skip steps 4–5. Ignored files are not stashed and do not block checkout.
4. `git checkout --no-overwrite-ignore "$DEFAULT"`. The flag stops checkout from clobbering ignored files (`.env`, local config) that `stash -u` left in place. If checkout fails (an ignored-file collision, or the branch is checked out in a linked worktree), mark `review-only (<reason>)` and **skip step 5**.
5. Confirm `git branch --show-current` equals `$DEFAULT`, then `git pull --ff-only origin "$DEFAULT"`. If the pull fails (diverged local branch), leave the local branch untouched and mark `review-only (pull failed)`.

Pin the reviewed tip: `TIP=$(git rev-parse "origin/$DEFAULT")`. Every later step reads from `$TIP`, never from the working directory: a `review-only` repo may still have a feature branch checked out, and a local default branch may carry unpushed commits. A sync failure never removes a repo from review.

Done when: every in-scope repo has a sync state and a pinned `$TIP`.

## Step 3 — Collect commits and PRs

Per repo, collect:

- **Commits on the default branch** in the window:
  `git log "$TIP" --since-as-filter="$SINCE" --until="$NOW" --format='%h %cI %an %s'`
  plus the landing view `git log "$TIP" --first-parent --since-as-filter="$SINCE" --until="$NOW" --format='%h %s'`. `--since-as-filter` scans all history, so out-of-order commit dates do not hide commits.
- **PRs targeting the default branch**, with `gh pr list --repo <owner/repo> --base "$DEFAULT" --limit 200 --json number,title,author,state,isDraft,createdAt,updatedAt,mergedAt,headRefOid,mergeCommit,url,additions,deletions,reviewDecision`:
  - open PRs created or updated in the window: `--state open --search "updated:>=$SINCE"`;
  - PRs merged in the window: `--state merged --search "merged:>=$SINCE"`.
  If a query returns exactly 200 results, split the window in halves and re-query until each part returns fewer than 200.

Commit dates miss work that landed recently but was authored earlier (a local fast-forward push keeps old dates). Treat merged PRs as the authoritative landing signal: include each merged PR's `mergeCommit` even when its date falls outside the commit query.

Classify each repo on two independent axes:

- **Activity**: `active` when any successful query found a commit or PR in the window; `inactive` when every query succeeded and returned nothing. A repo with failed queries and no found activity is `unknown`, never `inactive`.
- **Completeness**: `incomplete` when any query failed (auth, rate limit, network, missing ref).

Active repos go to Step 4 even when incomplete: review what was collected. Inactive repos are dropped from every later step and from the report. Incomplete and unknown repos get one phrase each in the report's coverage note.

Done when: every in-scope repo is active, inactive, or incomplete, and each active repo has its commit list and PR list.

## Step 4 — Review active repos (parallel subagents)

Dispatch one `general-purpose` subagent per active repo, **all in one message** so they run concurrently. Give each a self-contained prompt with: repo dir, `owner/repo`, `$DEFAULT`, `$TIP`, `$SINCE`, `$NOW`, the commit and PR lists from Step 3, and the review brief below. Subagents are read-only: they never commit, push, check out, comment on, or approve anything.

Review brief for each subagent:

- Read every in-window commit's diff with `git show --diff-merges=first-parent <sha>`. Plain `git show` on a merge shows a combined diff that hides most of the merged change.
- Pin every in-window PR before reading it: `git fetch origin "pull/<n>/head:refs/source-status/pr-<n>"`, then `PR_TIP=$(git rev-parse refs/source-status/pr-<n>)`. If `PR_TIP` differs from the Step 3 `headRefOid`, the PR moved; review `PR_TIP` and say so. Read an open PR's diff as `git diff "$TIP"..."$PR_TIP"`; read a merged PR through its `mergeCommit` with `git show --diff-merges=first-parent`. Delete the `refs/source-status/*` refs when done (`git for-each-ref --format='%(refname)' refs/source-status | xargs -r -n1 git update-ref -d`).
- Read every in-window PR's description, reviews, and conversation via `gh pr view <n> --repo <owner/repo> --json body,reviews,comments`; inline review threads via `gh api --paginate repos/<owner/repo>/pulls/<n>/comments`.
- Read surrounding code from the pinned trees only: `git show "$TIP":<path>` for the default branch, `git show "$PR_TIP":<path>` for an open PR. Read the repo's `CLAUDE.md`/ADRs the same way when a judgment depends on them. For open PRs, check compatibility with current `$TIP`.
- Judge as a principal engineer across five lenses: **engineering** (reliability, operability, security, performance, dependencies), **architecture** (boundaries, coupling, data flow, contracts between services), **design** (API and schema shape, migrations, backward compatibility), **coding** (correctness, error handling, concurrency, readability), **testing** (missing or weakened tests, coverage of the changed behavior, red CI via `gh pr checks <n> --repo <owner/repo>`).
- Search when a judgment depends on facts outside the diff. GitHub: `gh search prs "<symbol or contract name>" --owner intramotev`, `gh search code "<symbol>" --owner intramotev` for consumers in sibling repos. Web: CVEs, library changelogs, deprecations.
- Report only what clears the **critical bar**: a defect, risk, or regression that will plausibly cause an outage, data loss, security exposure, a broken contract with another repo, or untested production behavior. Rate each finding `critical` (likely harm on deploy) or `high` (real risk, needs a fix before it compounds). Style nits and minor suggestions stay out.

Each subagent returns exactly:

```
REPO: <name>
SUMMARY: <1–2 sentences: what changed and why it matters>
KEY CHANGES: <≤3 bullets, each citing a sha or PR#>
CRITICAL ISSUES: <every finding that clears the bar, no cap: [severity][lens] issue — evidence (sha/PR#, path:line, external URL if used) — impact>
```

Done when: every active repo has a returned block, and every finding cites a sha or PR number plus path:line.

## Step 5 — Draft the report

Build the draft from the subagent blocks. Structure:

```markdown
# Source status — <Mon DD, YYYY> (window: <SINCE> → <NOW> UTC)

## Critical issues
- **<repo>** [<severity>/<lens>] <issue> — <impact> (<sha|PR#>, `<path:line>`)

## Changes by repo
### <repo>
<1–2 sentence summary>. Key: <change> (<sha|PR#>); <change> (<PR#> open).

_Coverage: <stale / review-only / incomplete repos, one phrase each; omit the line when all synced>_
```

Rules:

- Under **450 words total**, checked with `wc -w`. When over, cut change lines first, least important first. Then cut `high` findings, lowest impact first, and end the section with `+N more high findings (see chat)`. `critical` findings are never cut. If `critical` findings alone still exceed 450 words, drop the **Changes by repo** section, compress each critical line to issue + citation, and move impact detail to chat.
- Order findings by severity, then impact, across repos. If there are none, write `None found.` under the heading.
- Every claim cites a sha or PR number. Open PRs are labelled `open`.
- Inactive repos never appear, not even as "no changes".

## Step 6 — Adversarial verification

Dispatch two `general-purpose` subagents in one message. Each gets the draft, the full Step 4 finding list (including findings cut from the draft for length), the repo dirs with their `$TIP`, `$SINCE`, `$NOW`, the Step 1 skip list, and the Step 3 classifications. An omission already in the cut list is not new; it stays in chat unless it outranks a retained line. Each acts as an **adversary**: its job is to break the draft, not approve it.

- **Accuracy adversary**: for every claim and finding, re-check the cited sha/PR/path:line against the actual diff. Return each item as `CONFIRMED`, `WRONG (<correction>)`, or `OVERSTATED (<why>)`. Also flag any finding whose severity does not clear the critical bar in Step 4.
- **Omission adversary**: re-run the Step 3 queries independently for **every** in-scope repo, including inactive and incomplete ones, and confirm each classification. Then skim every in-window commit and PR and return anything that clears the critical bar but is missing from the draft, with evidence. Also flag any repo in the draft with no in-window activity, and any top-level directory wrongly skipped in Step 1.

Run Step 6 even when no repo is active: the omission adversary then confirms the empty result.

Apply results: fix every `WRONG` item, downgrade or drop every `OVERSTATED` item, add each evidenced omission. When an adversary and a Step 4 subagent disagree, read the cited diff yourself and decide; the evidence decides, not either side.

Then dispatch the accuracy adversary once more on **only the changed or added lines** (including lines reworded to fit the word limit). Apply its corrections the same way.

Done when: every claim in the draft is `CONFIRMED` or corrected, every omission is added or rejected with a reason, the second accuracy pass is clean, and `wc -w` is under 450.

## Step 7 — Write the file

```bash
mkdir -p ~/sources/review
OUT=~/sources/review/source_summary_$(date +%m_%d_%y).md
```

Write the final report to `$OUT`, overwriting any earlier run from the same day.

## Step 8 — Chat summary

Reply with:

- the report path and its word count;
- every finding, one line each, including any `high` findings cut from the file;
- housekeeping the user must know about: every stash created (repo, original branch, stash ref, message), every repo left `review-only`, `stale`, or `incomplete`, and every skipped directory with its reason.
