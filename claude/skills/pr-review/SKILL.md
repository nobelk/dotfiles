---
name: pr-review
description: Work through a GitHub repo's open, ready-for-review PRs as the active gh login, skipping drafts and my own PRs. For PRs I already commented on, checks each comment is addressed or resolved on the latest code and that CI passes, then approves. For PRs I haven't reviewed, and for code pushed after my feedback, runs `/code-review high`, a changed-line unit-test coverage check (skipped for Ansible and Flutter/Dart), and a check against the Jira ticket, PR title and description, and spec, then posts the findings as inline comments. Asks before posting and before approving; `--yes` posts without asking, and `--dry-run` only reports. Takes `owner/repo` or a repo URL (inferred from the cwd's origin if omitted). Invoke manually, or from a scheduled job with `--yes`, when a repo's review queue needs working through.
argument-hint: '[owner/repo | https://github.com/owner/repo] [--me <login>[,<login>]] [--yes | --dry-run]'
---

# PR-review skill

Act as a principal engineer working through a repository's open pull request queue. The flow is: resolve repo, identity and mode → inventory the open PRs → classify them and present the plan → check the PRs that already carry my feedback against their current head (read-only) → run the three **review checks** (code review, coverage, intent) on PRs waiting for my review and on unreviewed code pushed after my feedback → **Gate 1**: post the findings as inline review comments → **Gate 2**: approve the PRs whose feedback is fully handled → update the ledger → brief chat summary.

## Modes

- **Interactive** (default): Gate 1 and Gate 2 are each one `AskUserQuestion` per run.
- **`--yes`** (for scheduled or headless runs): Gate 1 posts without asking. Gate 2 approves nothing; it lists approvable PRs in the summary. Never call `AskUserQuestion` in this mode: every stop-and-ask condition uses its **unattended default** (see the last section).
- **`--dry-run`**: no GitHub writes and no ledger writes. Both gates report what would have been posted or approved. Local scratch work (clone, worktrees, coverage runs) still happens, because the report needs it. No questions either; the same unattended defaults apply.

`--yes` and `--dry-run` together is an input error: stop and say so.

Only two actions change GitHub: posting a review with comments, and approving. Each gate approves a frozen payload bound to a head SHA. If anything changes after the gate, skip that PR for this run; never re-do it silently.

## Posting voice

Everything posted to GitHub (inline comments, review bodies, approval bodies) is written in first person, as me, the reviewer: plain engineering prose, one or two sentences for each finding. Leave out any mention of how the review was produced, including tool, model, assistant, or automation names, skill or command names, confidence or severity tags copied from tool output, emojis, and signature lines. Just before every POST, scan the payload case-insensitively for `claude`, `anthropic`, `\bai\b`, `llm`, `gpt`, `codex`, `bot`, `automated`, `generated`, `assistant`, `/code-review`, and `🤖`, and rewrite any match as ordinary reviewer prose. Only a code identifier quoted in backticks (such as `aiClient`) is exempt. Paraphrase any prose you quote from a ticket, spec, or PR if it contains one of those terms.

## Subagent delegation — parallel by default

Keep orchestration in the main loop; run the expensive, self-contained steps in **`general-purpose` subagents** via the `Agent` tool. When tasks are independent, **launch them in a single message** so they run concurrently.

- **Main loop owns** (never delegate): every `AskUserQuestion` gate, every `gh` call that changes GitHub, the `/code-review` runs, the ledger, and the final summary. Subagents cannot prompt the user.
- **Delegate, in parallel**:
  - Step 1 per-PR deep fetch: one subagent per eligible PR, all launched together.
  - Step 3 verification: one subagent per C PR, read-only against the fetched PR head.
  - Step 4 coverage and intent checks: one coverage subagent and one intent subagent per review target. Keep at most **3 coverage subagents** running at once, because they build and run test suites.
  - These run *while* the main loop is doing the serial `/code-review` runs. A C PR's delta checks depend on its Step 3 result, so they start only after it returns.
- `/code-review` runs from the main loop through the `Skill` tool. It starts its own background subagent, and running it inside another subagent is unsupported. Run one PR at a time and wait for each to finish so findings never get mixed up.
- Every subagent prompt is self-contained: the exact commands with explicit `<owner>/<repo>` paths, the clone path, the SHAs, the items to check, and the exact result shape to return. Coverage and intent subagents are told to read and follow `~/.claude/skills/pr-review/COVERAGE.md` or `~/.claude/skills/pr-review/INTENT.md`. Subagents share no state. Apart from the coverage subagent's own scratch worktree, they change neither the working tree nor GitHub.

## Step 0 — Resolve inputs, identity, and clone

- **Repo**: the argument is `owner/repo` or any `https://github.com/owner/repo[/...]` URL; parse `<owner>/<repo>`. With no argument, derive it from the cwd's `origin` URL (`git remote get-url origin`), which must be a `github.com` URL. `gh repo view` is not used for this, because `GH_HOST` could redirect it. If neither works, ask with `AskUserQuestion` in interactive mode; in unattended modes, stop. Never guess.
- **Auth**: `gh auth status --hostname github.com --active` must succeed. If not, stop and tell the user to run `! gh auth login`.
- **Identity**: `ME=$(gh api --hostname github.com user --jq .login)` is the **active login**. It is the only account that posts and approves, and the only one whose feedback drives Step 3 and Gate 2. The skill's owner is **`nobelk`**: PRs authored by `nobelk` are always treated as mine, whatever the active login. If `ME` isn't `nobelk` (case-insensitive), interactive mode asks whether to continue as `ME`. Unattended modes stop, so a scheduled run can never post as another account. `--me a,b` adds **alias logins**. These are used only to recognise my own PRs and for reporting: feedback an alias left is listed but never auto-approved, because approving from the active login doesn't clear another account's CHANGES_REQUESTED. Compare logins case-insensitively. Immediately before each POST in Gates 1 and 2, re-run the same `gh api --hostname github.com user` call. If the login differs from `ME`, abort the run, so a mid-run `GH_TOKEN`/`GH_HOST` change or `gh auth switch` can never post as another account.
- **`gh` invocation rule**: pin the host on every call so `GH_HOST` cannot redirect a read or a write. `gh pr ...` and `gh repo ...` take `--repo github.com/<owner>/<repo>`. `gh api` has no `--repo` flag, so it takes `--hostname github.com`, with paths spelling out `repos/<owner>/<repo>/...`. Every example below follows this.
- **Working clone**: `/code-review` needs the cwd to be a clone of the target repo (it takes a ref range, not `owner/repo#n` or a URL). If the cwd's `origin` URL is a `github.com` URL for `<owner>/<repo>`, run `git fetch origin` and use it. Otherwise clone once into the scratchpad with `gh repo clone github.com/<owner>/<repo> <scratchpad>/pr-review/<owner>__<repo> -- --filter=blob:none` and `cd` there. Never check out branches in a clone the user works in. Fetch PR heads into `refs/remotes/origin/pr-<n>` and read them with `git show`. Coverage runs use detached worktrees under the scratchpad (see `COVERAGE.md`).
- **Ledger**: `~/.local/state/pr-review/<owner>__<repo>.json` (create the directory when missing) maps PR number → `{headSha, outcome, at}`, where `outcome` is `clean` or `posted`. It only saves the Step 4 checks from running twice on the same head. It never replaces the fresh CI and eligibility evaluation in Gate 2. If the file won't parse, move it aside to `<file>.corrupt-<timestamp>`, treat the ledger as empty, and say so in the summary.

## Step 1 — Inventory

List: `gh pr list --repo github.com/<owner>/<repo> --state open --limit 1000 --json number,title,body,author,isDraft,isCrossRepository,headRefName,baseRefName,headRefOid,updatedAt,reviewDecision,url`. Completeness check: `gh api --hostname github.com 'search/issues?q=repo:<owner>/<repo>+is:pr+is:open' --jq '[.total_count, .incomplete_results]'` must report `incomplete_results == false` and a count equal to the list length. Otherwise raise `--limit` and list again (retry the search once if it was incomplete). If the repo has no open PRs, say so and stop.

Set these aside before any deep fetch, and only count them in the summary:
- **Mine**: `author.login` matches the active login or an alias. These are never reviewed, verified, or approved.
- **Draft**: `isDraft` is true.

**Fail closed.** If any per-PR fetch below errors or can't finish (a failed page, a cut connection), mark the PR **incomplete**. List it in the plan and summary with the exact error, and keep it out of both gates for this run.

Then fan out **one subagent per remaining PR** in a single message. Each runs:

- **PR facts**: `gh api --hostname github.com repos/<owner>/<repo>/pulls/<n> --jq '{author_association, head_repo: .head.repo.full_name}'`.
- **Reviews**: `gh api --hostname github.com repos/<owner>/<repo>/pulls/<n>/reviews --paginate --jq '.[] | {login: .user.login, state, submitted_at, commit_id, body, html_url}'`. Drop `PENDING` reviews (not submitted; `submitted_at` is null) and `DISMISSED` reviews. From the rest, compute per login:
  - `latestEvent`: the most recent submitted review of any state;
  - `latestOpinion`: the most recent `APPROVED` or `CHANGES_REQUESTED`;
  - `bodyFeedback`: the non-empty bodies of `COMMENTED` and `CHANGES_REQUESTED` reviews.
- **Review threads**: cursor-paginated GraphQL. Omit `-F cursor=...` on the first page (a null `after` means the first page; an empty string does not), then loop with `endCursor` until `hasNextPage` is false:

  ```bash
  # first page: no -F cursor; later pages: add -F cursor="$END_CURSOR"
  gh api --hostname github.com graphql -F owner=<owner> -F repo=<repo> -F pr=<n> -f query='
    query($owner:String!,$repo:String!,$pr:Int!,$cursor:String){
      repository(owner:$owner,name:$repo){ pullRequest(number:$pr){
        reviewThreads(first:100, after:$cursor){
          pageInfo{ hasNextPage endCursor }
          nodes{ id isResolved resolvedBy{ login } isOutdated path line originalLine startLine originalStartLine diffSide startDiffSide subjectType
            comments(first:100){ pageInfo{ hasNextPage endCursor } nodes{ author{ login } body createdAt url diffHunk } } } } } } }'
  ```

  Merge `nodes` across pages. For every thread whose `comments.pageInfo.hasNextPage` is true, keep appending to that thread's comment list by looping with `-F id=<thread id> -F cursor=<endCursor>` on
  `query($id:ID!,$cursor:String){ node(id:$id){ ... on PullRequestReviewThread { comments(first:100, after:$cursor){ pageInfo{ hasNextPage endCursor } nodes{ author{ login } body createdAt url diffHunk } } } } }`
  until `hasNextPage` is false. `--paginate` does not walk nested connections, so do this by hand.
- **Issue comments by the identity set**: `gh api --hostname github.com repos/<owner>/<repo>/issues/<n>/comments --paginate --jq '.[] | select((.user.login|ascii_downcase) as $l | $l == "<me, lowercased>" or $l == "<alias, lowercased>" ...) | {login: .user.login, body, created_at, html_url}'`. `gh api --jq` has no `--arg`, so write the lowercased logins into the filter.
- **Head, base, commits and CI**: `gh pr view <n> --repo github.com/<owner>/<repo> --json headRefOid,baseRefName,baseRefOid,isDraft,state,mergeable,mergeStateStatus,statusCheckRollup,commits`. Normalize CI from `statusCheckRollup` by item type:
  - A `CheckRun` is **fail** when `conclusion` is one of `FAILURE`, `ERROR`, `CANCELLED`, `TIMED_OUT`, `ACTION_REQUIRED`, `STARTUP_FAILURE`. It is **pending** when `status` is not `COMPLETED` (`QUEUED`, `IN_PROGRESS`, `PENDING`, `REQUESTED`, `WAITING`) or `conclusion` is `STALE`. Otherwise it passes (`SUCCESS`, `NEUTRAL`, `SKIPPED`).
  - A legacy `StatusContext` has only `state`: `FAILURE`/`ERROR` → fail, `PENDING`/`EXPECTED` → pending, `SUCCESS` → pass.
  - Aggregate: any fail → **fail**; otherwise any pending → **pending**; otherwise a non-empty rollup → **pass**; an empty rollup → **none**.

Return one record per PR:

```
{number, title, body, author, authorAssociation, isCrossRepository, state, isDraft, headRefName, headRefOid, baseRefName, baseRefOid, commits, ci, mergeable, mergeStateStatus,
 me:      {latestEvent, latestOpinion, bodyFeedback:[{body, submitted_at, commit_id, html_url}], issueComments:[...]},
 aliases: {<login>: {latestEvent, latestOpinion, threadCount, bodyFeedbackCount, issueCommentCount}},
 others:  {latestOpinionByLogin: {...}, unresolvedThreadCount},
 threads: [{id, path, line, originalLine, startLine, originalStartLine, diffSide, startDiffSide, subjectType, isResolved, resolvedBy, isOutdated,
            starter, firstCommentAt, firstCommentBody, firstDiffHunk, replies:[{login, createdAt, body}]}]}
```

- `myThreads`: threads with **any** comment by the active login, whether I started them or replied in another reviewer's thread.
- `myFeedbackItems`: every **actionable comment** I made, each as its own item with its body, timestamp, and (for thread comments) its thread's anchor and resolution. A thread holding two separate requests from me yields two items. Pure acknowledgements ("thanks", "LGTM", "resolved") aren't actionable and yield none. Review bodies (`me.bodyFeedback`) and issue comments (`me.issueComments`) are items on the same terms.
- `feedbackBaseSha`: `me.latestEvent.commit_id` when I have a submitted review; this is the head GitHub bound my review to. Otherwise null, and the whole PR counts as unreviewed. Commit dates are set by the author and don't show when code was pushed, so they are never used to infer this.

Reclassify from the fresh `state` and `isDraft`: a PR that closed or became a draft since the inventory is set aside as a draft or closed PR.

## Step 2 — Classify (ordered decision tree) and plan

Mine and draft PRs are already set aside. Evaluate the rules **in order**; the first match wins, so the buckets don't overlap and cover every PR:

1. **D — Approved by me on the current head.** `me.latestOpinion` is APPROVED, its `commit_id == headRefOid`, and no item in `myFeedbackItems` is newer than that approval. No action.
2. **C — Has my feedback.** `myFeedbackItems` is non-empty, or `me.latestOpinion` is CHANGES_REQUESTED. Resolved and outdated threads are included: Step 3 judges them rather than trusting the flag. Add the sub-flag **stale-approval** if `me.latestOpinion` is APPROVED on an older commit.
3. **C-alias**: rule 2 did not match, but an alias has threads, body feedback, issue comments, or a CHANGES_REQUESTED opinion. It is not verified, reviewed, or approved. The summary lists it with the alias login and item counts, and says it must be handled from that account.
4. **R — Reviewed at this head.** The ledger has this PR with `headSha == headRefOid`. The Step 4 checks don't run again. A ledger `clean` entry still makes the PR a **clean-review** Gate 2 candidate, judged on this run's fresh CI and eligibility. A `posted` entry needs no action (next run it will be C, because it carries my threads).
5. **B — Waiting for my review.** Everything else.

Show the plan in chat, one row per PR: number, title (truncated), author, bucket, CI, and the planned action (`review + post`, `verify feedback`, `verify + review delta`, `none`). Finish with one line giving the counts of skipped mine and draft PRs. The plan is informational only; the gates come after the findings exist.

## Step 3 — Verify the PRs that already have my feedback (read-only)

In the main loop, run this once per C PR first, so subagents don't race:

```bash
git fetch --force origin refs/pull/<n>/head:refs/remotes/origin/pr-<n>
test "$(git rev-parse origin/pr-<n>)" = "<headRefOid>"   # abort this PR if not
```

Then launch **one subagent per C PR in a single message**. Each gets:
- the PR record and the head SHA;
- `feedbackBaseSha`;
- the local `git diff <feedbackBaseSha>...<headRefOid>` (the whole-PR range when `feedbackBaseSha` is null).

It reads the head code with `git show origin/pr-<n>:<path>` and judges each of `myFeedbackItems` against the **current head code**. The author's reply text is context, not proof.

**Thread items: find the site.** Work it out from the anchor rather than reusing a line number:
- `subjectType: FILE` is a whole-file comment with no line; judge the file.
- `diffSide: RIGHT` with a non-null `line` is a head-side line. A range spans `startLine..line`; if `startDiffSide` is `LEFT`, the range starts on the old side, so take the whole hunk as the site.
- `diffSide: LEFT` points at an old-side line (deleted or before the change). Find the matching code on head by its content from `firstDiffHunk` around `originalLine`, never by line number.
- A null `line` on a `LINE` thread means the anchor is outdated. Find the site by content from `originalLine`/`originalStartLine` and `firstDiffHunk`, and say so in the evidence.

**Thread items: classify.**
- **Addressed**: the head code does what the comment asked; cite `path:line` on head. If the file or line no longer exists, the item is Addressed only when removing it is what the comment asked for, or the concern clearly no longer applies.
- **Resolved**: the thread `isResolved` and the head code doesn't show the requested change. The item counts as handled:
  - if `resolvedBy` is the active login, I accepted it;
  - otherwise, record who resolved it and quote the first line of the author's last reply (or "no reply"), so the summary lists it under *resolved without a code change*.
- **Replied, not addressed**: the thread is unresolved, the author replied (agreement, a question, "will do"), but the head code still has the issue. Quote the first line of the reply.
- **Pushback to consider**: the thread is unresolved, the author argued the comment is wrong or out of scope, and the code is unchanged. Don't decide it; surface it.
- **No response**: the thread is unresolved, with no author reply and no relevant change.

**Review-body and issue-comment items.** These can't be resolved on GitHub. Split each body into its concrete requests. Classify each request that maps to a code location like a thread item, without the Resolved option. A request that can't be tied to code (for example "needs a design discussion") is **Unverifiable**: it blocks approval, and is reported word for word.

**Delta since my feedback.**
- If `feedbackBaseSha` is null, the unreviewed delta is the whole PR.
- Otherwise run `git merge-base --is-ancestor <feedbackBaseSha> <headRefOid>`. If it is false, the history was rewritten: report **rewritten**, which blocks approval and sends the whole PR back through the Step 4 checks as a B PR would go. If it is true, the **unreviewed delta** is the full change set `<feedbackBaseSha>..<headRefOid>`; list its files. Feedback on one line of a file doesn't make the rest of that file reviewed.

Return: `{number, headRefOid, items:[{ref, path, line, classification, evidence, resolvedBy?}], unreviewedDelta:[files] | "rewritten", othersUnresolvedThreads, ci}`.

## Step 4 — Review checks

Each **review target** is a PR plus an immutable range:
- **B PRs**: fetch the head (`git fetch --force origin refs/pull/<n>/head:refs/remotes/origin/pr-<n>`, and check it equals `headRefOid`) and the base (`git fetch --force origin <baseRefName>:refs/remotes/origin/<baseRefName>`, and check `git rev-parse origin/<baseRefName>` equals `baseRefOid`, or else skip the PR this run). The range is `MB...headRefOid`, where `MB=$(git merge-base <baseRefOid> <headRefOid>)`.
- **C PRs with a non-empty unreviewed delta** (after Step 3 returns): the range is `feedbackBaseSha...headRefOid`. A null `feedbackBaseSha` or rewritten history uses the whole-PR range, as for B.

The range is immutable, so findings are bound to `headRefOid` by construction. Always pass full SHAs. If a queued PR's head moves before its checks run, skip it for this run and report it.

Run three checks on each target:

1. **Code review**: from the main loop, invoke the `code-review` skill through the `Skill` tool as `/code-review high <base>...<headRefOid>`: level **high**, review-only. Leave out `--comment` and `--fix`, because `--comment` posts immediately and would skip Gate 1. Pass the level explicitly, since otherwise the skill reuses whatever level was typed last. Wait for each review to finish, then parse its findings into `{path, line, summary, failureScenario}`. Skip a PR only when the skill itself declines (closed, trivial, or automated), and record why.
2. **Coverage**: a subagent that follows `COVERAGE.md`. It gets the clone path, `<owner>/<repo>`, PR number, `authorAssociation`, `isCrossRepository`, range base, `headRefOid`, and the scratchpad path. It skips Ansible and Flutter/Dart changes and untrusted authors on its own. It returns uncovered changed-line findings, or a skip or failure reason.
3. **Intent**: a subagent that follows `INTENT.md`. It gets `<owner>/<repo>`, PR number, title, body, `headRefName`, `commits`, range base, `headRefOid`, and the clone path. It returns mismatches between the change and the Jira ticket, the PR title and description, and the spec. For a C delta, it also gets my existing feedback bodies and reports only new mismatches.

Launch every B target's coverage and intent subagents together with the Step 3 subagents, in one message (respecting the coverage cap). Then run the B code reviews one at a time while they work. A target is **clean** only when all three checks **ran to completion** with zero findings:
- the code review returned;
- coverage is `measured`, or `skipped` for an exempt reason (`ansible`, `flutter/dart`, `no production code`, `no coverage tooling`);
- the intent check had its ticket (`fetched` or `none-in-repo`).

A target whose coverage was skipped for an untrusted author, whose coverage failed, or whose Jira fetch was unavailable is **partial**. It can still have findings posted, but it is never clean. For a B PR, clean makes it a **clean-review** Gate 2 candidate. For a C delta, clean counts as reviewed for Gate 2, and any finding makes the PR not approvable this run.

If more than 25 targets are queued, ask with `AskUserQuestion` before starting, offering to cap them by most recently updated. The unattended default is to take the 25 most recently updated and list the rest as deferred.

## Step 5 — Gate 1: post findings as inline review comments

Build the **exact payload for each PR before asking**, bound to the reviewed `headRefOid`:

- **Merge** the three checks' findings. Drop duplicates that share an anchor and concern, keeping the most specific. Also drop any finding that repeats feedback already in `myFeedbackItems`.
- **Anchor** each finding against the hunks of the same range the review used: `git diff <base>...<headRefOid>` on the local clone, not the mutable `gh pr diff`.
  - A line that appears on the new side of any hunk, changed **or unchanged context**, becomes an inline comment `{"path", "line", "side": "RIGHT", "body"}`. A range adds `start_line` and `start_side: "RIGHT"`.
  - A line absent from every hunk, and any finding with no code location (for example a title or ticket mismatch), goes into the review `body` as a bullet. When it has a location, the bullet carries a permalink: `https://github.com/<owner>/<repo>/blob/<full headRefOid>/<path>#L<start>-L<end>`.
- **Cap coverage comments** at 10 inline per PR. Fold the rest into one body bullet listing `path:lines`.
- **Comment body**: follow *Posting voice*. A code finding states the defect and the scenario where it fails. A coverage finding names the untested behaviour and the test case to add. An intent finding quotes the ticket, spec, or PR text it contradicts. The review `body` holds only the bullets (empty when every finding is inline). `event` is always `COMMENT`.
- A PR with zero findings gets no review at all, so there is no "no issues" noise.

**Gate 1.** Show for each PR: head SHA (short), inline count, body-bullet count, and a one-line list of findings (`path:line — summary`) labelled by check.
- **Interactive**: ask once with `AskUserQuestion`, offering **post all**, **post none**, or **Other** (free text naming PR numbers to skip).
- **`--yes`**: post all without asking.
- **`--dry-run`**: post nothing.
- If there is nothing to post, say so and skip the gate.

After approval, for each PR still in scope, fetch `headRefOid`, `baseRefName`, `baseRefOid`, `state` and `isDraft` again. **If the head differs from the payload's SHA, the base ref or SHA differs from the Step 1 record, or the PR is no longer open or has become a draft, skip it this run and report it.** Never re-review and post without a fresh gate. Otherwise, run the voice scan from *Posting voice*, then:

```bash
gh api --hostname github.com repos/<owner>/<repo>/pulls/<n>/reviews --method POST --input review.json
# {"commit_id":"<headRefOid>","event":"COMMENT","body":"<bullets>","comments":[{"path":"...","line":N,"side":"RIGHT","body":"..."}]}
```

Check the exit status and record `.html_url`. Then fetch `headRefOid` again: if it no longer equals the returned `commit_id`, report the review as **posted against a superseded head**. On failure (422 for a line not in the diff, 403 for permissions, and so on), report the exact error for that PR and continue with the others. Don't retry blindly.

## Step 6 — Gate 2: approve fully handled PRs

A C PR is **approvable** only when **all** of these hold, using the Step 3 result and the Step 4 delta checks:

1. Every item in `myFeedbackItems` is **Addressed** or **Resolved**. Replied-not-addressed, Pushback, No response, and Unverifiable items all block.
2. The unreviewed delta is empty, or its three checks came back clean, and the history was not rewritten.
3. `ci` is **pass**. **fail** and **pending** block. **none** (no checks reported) is treated like rule 5: **approvable with caveat**, with the reason "no CI checks".
4. The PR is still open and not a draft.
5. No other reviewer has an unresolved, non-outdated thread, and no other reviewer's current `latestOpinion` is CHANGES_REQUESTED. A PR that fails only this rule is **approvable with caveat**, and is approved only if the user names it at the gate.

A **clean-review** PR (a clean B target this run, or an R PR with a ledger `clean` entry) is approvable under rules 3–5, and is listed at the gate under its own heading so the user can leave it out. Every other C PR is **waiting on author**, with its blocking items listed.

**Gate 2.** List approvable PRs (head SHA short, plus a reason such as "3/3 items handled (1 resolved without change), delta reviewed clean, CI pass"), then clean-review PRs, then approvable-with-caveat PRs, each under its own heading.
- **Interactive**: ask once with `AskUserQuestion`, offering **approve all approvable**, **approve none**, or **Other** (free text naming PRs to skip, or caveat PRs to include).
- **`--yes` and `--dry-run`**: approve nothing; the summary lists them as **Approvable**.
- If no PR is approvable, say so and skip the gate.

After approval, for each PR still in scope, **run the Step 1 fetch for that PR again and compare the whole record** with the one Steps 3 and 4 used: head SHA, base ref and SHA, state, isDraft, CI, every review's state, the thread set and resolution, body feedback, issue comments, and others' opinions. If anything changed, **skip the PR this run and report what changed**; don't re-verify after the gate. Otherwise, submit the approval through the REST endpoint so it is bound to the verified SHA (`gh pr review --approve` can't target a commit):

```bash
gh api --hostname github.com repos/<owner>/<repo>/pulls/<n>/reviews --method POST \
  -f commit_id=<headRefOid> -f event=APPROVE \
  -f body="Thanks, all my feedback is addressed. Approving at <short sha>."
```

Check the exit status and the returned `state` and `commit_id`. Then fetch `headRefOid` again: if it no longer equals the returned `commit_id`, report the approval as **bound to a superseded head** so the user can dismiss it. A failed call is an error in the summary, never an approval. GitHub has no transactional read-then-write, so a change landing between the refresh and the POST can't be ruled out. The refresh, the SHA-bound POST, and the post-check keep that window to seconds and make it visible. Don't resolve threads for the author, and don't merge.

## Step 7 — Ledger

Skip this step in `--dry-run`. Otherwise, write the ledger entries for this run:
- `clean` for every B target whose three checks came back clean;
- `posted` for every PR whose review POST succeeded, bound to the head SHA it was posted against.

Leave out any PR whose target was **partial** (Step 4) or whose code review errored, so it gets reviewed again next run.

To write: re-read the ledger file, merge this run's entries into it (this run wins per PR), write the result to `<file>.tmp.<pid>` in the same directory, then `mv` it over the ledger. That way a crash or a concurrent run can't leave a truncated file.

## Step 8 — Summary (chat only)

Give a brief chat summary and nothing else. Use short lists and leave out empty sections:

1. **Posted**: PRs that got review comments, with number, title, inline and body counts split by check, and `html_url`. Then list the PRs reviewed clean. In `--dry-run`, title this section **Would post**.
2. **Approved**: PRs approved this run, with the SHA. List feedback-handled and clean-review PRs separately. In `--yes`, in `--dry-run`, or if the gate was declined, title it **Approvable** and list what qualified, marking caveat PRs.
3. **Waiting on author**: C PRs not approved, each with number, title, blocking items (`path:line — classification`), Pushback items for the user to decide, and red or pending CI. Also list C-alias PRs with the alias that must act.
4. **Resolved without a code change**: `path:line`, who resolved it, and the first line of the reply. These count as handled, but the user may want to look.
5. **Coverage not measured**: each skipped or failed coverage run with its reason (Ansible or Flutter/Dart, untrusted author, no tooling, test failure, timeout).
6. **Skipped**: counts of mine, draft, and reviewed-at-this-head PRs, plus deferred targets over the cap.
7. **Errors**: declined reviews, incomplete fetches, PRs whose head or eligibility moved during or after a step, writes bound to a superseded head, failed POSTs with the exact error, and rewritten-history PRs.

Give counts and one line per PR; never paste review bodies or diffs into the chat.

## Stop-and-ask conditions

Interactive mode asks with `AskUserQuestion` and doesn't proceed silently. `--yes` and `--dry-run` never ask; they take the **unattended default**:

- The repo argument can't be resolved, or the active `gh` login can't access it. Unattended default: stop, and report it.
- The active login isn't `nobelk` (Step 0). Unattended default: stop, and report it.
- More than 25 review targets are queued (Step 4). Unattended default: take the 25 most recently updated.
- The `code-review` skill is unavailable, or errors on every PR. Don't substitute an ad-hoc review. Unattended default: stop before Gate 1 and report; coverage and intent findings are still listed in the summary but not posted.
- The Atlassian MCP server isn't connected or the Jira fetch fails (`INTENT.md`). Interactive mode asks whether to continue without ticket context. Unattended default: continue, and note "Jira unavailable" in the summary.
- Gate 1 and Gate 2 themselves.
