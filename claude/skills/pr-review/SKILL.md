---
name: pr-review
description: Triage every open pull request in a GitHub repository as the active gh login — inventories the PRs, plans the work, runs `/code-review high` on the PRs still waiting for my review and posts the findings as inline PR comments (one confirmation per run), verifies on the current head that the author addressed every piece of feedback I left on the PRs I already reviewed, approves the ones that are fully addressed (one confirmation per run), and closes with a brief chat summary of what was posted, what was approved or is approvable, which of my own PRs are approved, and which PRs are still waiting on their author. Takes a GitHub repo (`owner/repo` or URL) as the argument (inferred from the cwd's origin remote if omitted). Invoke manually when it is time to work through a repo's review queue.
argument-hint: '[owner/repo | https://github.com/owner/repo] [--me <login>[,<login>]] [--dry-run]'
---

# PR-review skill

Act as a principal engineer working through a repository's open pull request queue. The flow is: resolve repo and identity → inventory every open PR → classify with an ordered decision tree and present the plan → verify the PRs that already carry my feedback against the current head (read-only) → run `/code-review high` on the PRs waiting for my review and on the unreviewed delta of feedback PRs → **Gate 1**: post the captured findings as inline review comments → **Gate 2**: approve the PRs whose feedback is fully addressed → brief chat summary. The summary is chat-only; no file is written.

Exactly two actions mutate GitHub — posting review comments and approving PRs — and each sits behind exactly one `AskUserQuestion` per run. Each gate approves a frozen payload bound to a head SHA; anything that changes after the gate is skipped for this run, never re-done silently. `--dry-run` skips both gates and both actions and reports what would have been posted and approved.

## Subagent delegation — parallel by default

Keep orchestration in the main loop; run the expensive, self-contained steps in **`general-purpose` subagents** via the `Agent` tool. When tasks are independent, **launch them in a single message** so they run concurrently.

- **Main loop owns** (never delegate): every `AskUserQuestion` gate, every `gh` call that mutates GitHub, the `/code-review` invocations, and the final summary. Subagents cannot prompt the user.
- **Delegate, in parallel**:
  - Step 1 per-PR deep fetch: one subagent per PR, all launched together.
  - Step 3 verification: one subagent per feedback PR, all launched together, read-only against the fetched PR head. These run *while* the main loop is doing the Step 4 **B-PR** `/code-review` runs; the C-PR delta reviews depend on Step 3's result and start only after it returns.
- `/code-review` is invoked from the main loop with the `Skill` tool. It forks its own background subagent, and nesting it inside another subagent is unsupported. Run one PR at a time and wait for its completion before starting the next so findings are never interleaved.
- Every subagent prompt is self-contained: the exact commands with explicit `<owner>/<repo>` paths, the feedback items it must check, and the exact result shape to return. Subagents share no state and must not mutate the working tree or GitHub.

## Step 0 — Resolve inputs and identity

- **Repo** — the argument is `owner/repo` or any `https://github.com/owner/repo[/...]` URL; parse `<owner>/<repo>`. With no argument, derive it from the cwd's `origin` URL (`git remote get-url origin`), which must be a `github.com` URL — `gh repo view` is not used for inference because `GH_HOST` could redirect it. If neither resolves, ask via `AskUserQuestion` — never guess.
- **Auth** — `gh auth status --hostname github.com --active` must succeed. If not, stop and tell the user to run `gh auth login` (suggest `! gh auth login` so it runs interactively).
- **Identity** — `ME=$(gh api --hostname github.com user --jq .login)` is the **active login**: the only account that posts and approves, and the only account whose feedback drives Gate 2. `--me a,b` adds **alias logins** used *only* for ownership (a PR authored by any identity is bucket A) and for reporting (feedback left by an alias is listed, never auto-approved, because an approval from the active login does not supersede another account's CHANGES_REQUESTED). Compare logins case-insensitively. State in the plan which login is active and which are aliases. Immediately before each mutation in Gates 1 and 2, re-run the same `gh api --hostname github.com user` call and abort the run if the login differs from `ME` (a `GH_TOKEN`/`GH_HOST` change or `gh auth switch` mid-run must never post as a different account).
- **`gh` invocation rule** — the host is pinned on every call so `GH_HOST` cannot redirect a read or a write: `gh pr ...` / `gh repo ...` take `--repo github.com/<owner>/<repo>`, and `gh api` (which has no `--repo` flag) takes `--hostname github.com` with paths spelling out `repos/<owner>/<repo>/...`. Every example below follows this.
- **Working clone** — `/code-review` needs the cwd to be a clone of the target repo (it accepts a bare PR number or a ref range, not `owner/repo#n` or a URL). If the cwd's `origin` URL is `github.com` and points at `<owner>/<repo>`, use it after `git fetch origin`. Otherwise clone once into the scratchpad (`gh repo clone github.com/<owner>/<repo> <scratchpad>/pr-review/<repo> -- --filter=blob:none`) and `cd` there. Never check out branches or otherwise mutate a clone the user was working in: PR heads are fetched into `refs/remotes/origin/pr-<n>` and read with `git show`.

## Step 1 — Inventory every open PR

List: `gh pr list --repo github.com/<owner>/<repo> --state open --limit 1000 --json number,title,author,isDraft,headRefName,baseRefName,headRefOid,updatedAt,reviewDecision,reviewRequests,url,labels`. Completeness check: `gh api --hostname github.com 'search/issues?q=repo:<owner>/<repo>+is:pr+is:open' --jq '[.total_count, .incomplete_results]'` must report `incomplete_results == false` and a count equal to the list length; otherwise raise `--limit` and re-list (retry the search once if it was incomplete). If the repo has no open PRs, say so and stop.

**Fail closed.** If any per-PR fetch below errors or cannot be completed (a failed page, a truncated connection), the PR is marked **incomplete**: it is listed in the plan and summary with the exact error, and it is excluded from both gates for this run.

Then fan out **one subagent per PR** in a single message. Each runs:

- **Reviews** — `gh api --hostname github.com repos/<owner>/<repo>/pulls/<n>/reviews --paginate --jq '.[] | {login: .user.login, state, submitted_at, commit_id, body, html_url}'`. Drop `PENDING` (unsubmitted, null `submitted_at`) and `DISMISSED` reviews. From the rest compute, per login: `latestEvent` (most recent submitted review of any state), `latestOpinion` (most recent `APPROVED` or `CHANGES_REQUESTED`), and `bodyFeedback` (non-empty bodies of `COMMENTED`/`CHANGES_REQUESTED` reviews).
- **Review threads** — cursor-paginated GraphQL; omit `-F cursor=...` on the first page (a null `after` is the first page; an empty string is not), then loop with `endCursor` until `hasNextPage` is false:

  ```bash
  # first page: no -F cursor; later pages: add -F cursor="$END_CURSOR"
  gh api --hostname github.com graphql -F owner=<owner> -F repo=<repo> -F pr=<n> -f query='
    query($owner:String!,$repo:String!,$pr:Int!,$cursor:String){
      repository(owner:$owner,name:$repo){ pullRequest(number:$pr){
        reviewThreads(first:100, after:$cursor){
          pageInfo{ hasNextPage endCursor }
          nodes{ id isResolved isOutdated path line originalLine startLine originalStartLine diffSide startDiffSide subjectType
            comments(first:100){ pageInfo{ hasNextPage endCursor } nodes{ author{ login } body createdAt url diffHunk } } } } } } }'
  ```

  Merge `nodes` across pages. For every thread whose `comments.pageInfo.hasNextPage` is true, loop with `-F id=<thread id> -F cursor=<endCursor>` on
  `query($id:ID!,$cursor:String){ node(id:$id){ ... on PullRequestReviewThread { comments(first:100, after:$cursor){ pageInfo{ hasNextPage endCursor } nodes{ author{ login } body createdAt url diffHunk } } } } }`
  until `hasNextPage` is false, appending to that thread's comment list. `--paginate` does not walk nested connections; do it by hand.
- **Issue comments by the identity set** — `gh api --hostname github.com repos/<owner>/<repo>/issues/<n>/comments --paginate --jq '.[] | select((.user.login|ascii_downcase) as $l | $l == "<me, lowercased>" or $l == "<alias, lowercased>" ...) | {login: .user.login, body, created_at, html_url}'` (`gh api --jq` has no `--arg`, so interpolate the lowercased logins into the filter). Comments by anyone outside the identity set are out of scope for this skill.
- **Head, base and CI** — `gh pr view <n> --repo github.com/<owner>/<repo> --json headRefOid,baseRefName,baseRefOid,isDraft,state,mergeable,mergeStateStatus,statusCheckRollup,commits`. Normalize CI from `statusCheckRollup` by item type: a `CheckRun` is **fail** when `conclusion` ∈ {`FAILURE`, `ERROR`, `CANCELLED`, `TIMED_OUT`, `ACTION_REQUIRED`, `STARTUP_FAILURE`}, **pending** when `status` ≠ `COMPLETED` (`QUEUED`, `IN_PROGRESS`, `PENDING`, `REQUESTED`, `WAITING`) or `conclusion` is `STALE`, otherwise pass (`SUCCESS`, `NEUTRAL`, `SKIPPED`); a legacy `StatusContext` has only `state`: `FAILURE`/`ERROR` → fail, `PENDING`/`EXPECTED` → pending, `SUCCESS` → pass. Aggregate: any fail → **fail**; else any pending → **pending**; else non-empty → **pass**; empty rollup → **none**.

Return one record per PR:

```
{number, title, author, isDraft, headRefOid, baseRefName, baseRefOid, lastCommitAt, ci, mergeable, mergeStateStatus,
 me:      {latestEvent, latestOpinion, bodyFeedback:[{body, submitted_at, commit_id, html_url}], issueComments:[...]},
 aliases: {<login>: {latestEvent, latestOpinion, threadCount, bodyFeedbackCount, issueCommentCount}},
 others:  {latestOpinionByLogin: {...}, unresolvedThreadCount},
 threads: [{id, path, line, originalLine, startLine, originalStartLine, diffSide, startDiffSide, subjectType, isResolved, isOutdated,
            starter, firstCommentAt, firstCommentBody, firstDiffHunk, replies:[{login, createdAt, body}]}]}
```

`myThreads` = threads containing **any** comment by the active login (started by me, or another reviewer's thread I replied in — my latest comment in the thread is the ask to verify). `myFeedbackItems` = `myThreads` ∪ `me.bodyFeedback` ∪ `me.issueComments`, each carrying the timestamp of my latest comment/body. `feedbackBaseSha` = `me.latestEvent.commit_id` when I have a submitted review, else the newest PR commit whose `committedDate` precedes my latest feedback item's timestamp, else null (no commit predates my feedback — the whole PR counts as unreviewed delta).

## Step 2 — Classify (ordered decision tree) and plan

Evaluate the rules **in order**; the first match wins, so buckets are exclusive and exhaustive:

1. **A — Mine.** `author` matches the active login or any alias. Never code-reviewed and never approved by this skill. Sub-state from *other* logins' `latestOpinion`, all on the current head (`commit_id == headRefOid`): **approved** (at least one APPROVED, no CHANGES_REQUESTED), **changes requested** (any CHANGES_REQUESTED), else **awaiting review**. Report CI and `mergeStateStatus` alongside; call it "ready to merge" only when approved, `reviewDecision` is `APPROVED`, no unresolved non-outdated threads, CI is pass, not draft, and `mergeStateStatus` is `CLEAN`.
2. **D — Approved by me on the current head.** `me.latestOpinion` is APPROVED, its `commit_id == headRefOid`, and no item in `myFeedbackItems` is newer than that approval. No action; listed for completeness.
3. **C — Has my feedback.** `myFeedbackItems` is non-empty, or `me.latestOpinion` is CHANGES_REQUESTED. (Resolved and outdated threads are included — resolution is verified in Step 3, not trusted.) Sub-flag **stale-approval** if `me.latestOpinion` is APPROVED on an older commit.
4. **B — Waiting for my review.** Everything else: no review from me, or only a review with no feedback items whose `commit_id != headRefOid`. Drafts are included and flagged.

A PR that rule 3 would not catch but where an alias has threads, body feedback, issue comments, or a CHANGES_REQUESTED opinion is **C-alias** (checked between rules 3 and 4): it is neither verified nor reviewed nor a Gate 2 candidate — the summary lists it with the alias login and item counts and says it must be handled from that account.

Present the plan in chat: one row per PR — number, title (truncated), author, bucket, draft flag, CI, and the planned action (`code-review + post`, `verify feedback`, `verify + review delta`, `none`). Informational only; the gates come after the findings exist.

## Step 3 — Verify the PRs that already have my feedback (read-only)

Main loop first, once per C PR, so subagents do not race:

```bash
git fetch --force origin refs/pull/<n>/head:refs/remotes/origin/pr-<n>
test "$(git rev-parse origin/pr-<n>)" = "<headRefOid>"   # abort this PR if not
```

Then launch **one subagent per C PR in a single message**. Each gets the PR record, the head SHA, the local `git diff <feedbackBaseSha>...<headRefOid>` (whole-PR range when null), and `feedbackBaseSha`. It reads head code with `git show origin/pr-<n>:<path>` and must judge each of `myFeedbackItems` against the **current head code**, never against the author's reply text:

- **Thread items** — locate the site by interpreting the anchor, not by reusing a number: `subjectType: FILE` is a whole-file comment (no line; judge the file); otherwise `diffSide: RIGHT` with non-null `line` is a head-side line, and a range spans `startLine..line` (if `startDiffSide` is `LEFT` the range starts on the old side — take the whole hunk as the site); `diffSide: LEFT` anchors an old-side (deleted or pre-change) line, so find the corresponding code on head by content from `firstDiffHunk` around `originalLine`, never by line number; a null `line` on a `LINE` thread means the anchor is outdated — re-locate by content from `originalLine`/`originalStartLine` and `firstDiffHunk`, and say so in the evidence. Classify:
  - **Addressed** — the head code does what the comment asked; cite `path:line` on head. `isResolved`/`isOutdated` alone is not evidence; a thread whose file or line no longer exists is Addressed only if the removal is what the comment asked for or the concern demonstrably no longer applies.
  - **Replied, not addressed** — the author replied (agreement, question, "will do") but the head code still has the issue. Quote the reply's first line.
  - **Pushback to consider** — the author argued the comment is wrong or out of scope and the code is unchanged. Do not decide; surface it.
  - **No response** — no author reply and no relevant change.
- **Review-body and issue-comment items** — split each body into its concrete asks. Each ask that maps to a code location is classified exactly like a thread item. An ask that cannot be mapped to code (e.g. "needs a design discussion") is **Unverifiable** and blocks approval; report it verbatim.
- **Delta since my feedback** — if `feedbackBaseSha` is null, the unreviewed delta is the whole PR. Otherwise `git merge-base --is-ancestor <feedbackBaseSha> <headRefOid>`: if false, history was rewritten — report **rewritten** (blocks approval; the whole PR needs a fresh review); if true, the **unreviewed delta** is the full change set `<feedbackBaseSha>..<headRefOid>` (list its files); feedback on one line of a file does not make the rest of that file reviewed.

Return: `{number, headRefOid, items:[{ref, path, line, classification, evidence}], unreviewedDelta:[files] | "rewritten", othersUnresolvedThreads, ci, isDraft}`.

## Step 4 — Run `/code-review high`

From the main loop, with the `Skill` tool, level **high**, review-only (no `--comment`, no `--fix`) — `--comment` posts immediately and would bypass Gate 1. Documented argument order is level, flags, target; always pass the level explicitly because the skill otherwise reuses whatever level was typed last.

- **B PRs** — review an immutable range, never the mutable PR number: fetch the head (`git fetch --force origin refs/pull/<n>/head:refs/remotes/origin/pr-<n>`, verify it equals `headRefOid`) and the base (`git fetch origin <baseRefName>`), compute `MB=$(git merge-base origin/<baseRefName> <headRefOid>)`, and invoke `/code-review high <MB>...<headRefOid>` with the full SHAs, one PR at a time. The findings are then bound to `headRefOid` by construction; a head that moves later is caught at Gate 1. Do not skip drafts (the user chose to include them); note in the summary that a draft was reviewed. Skip a PR only when the skill itself declines (closed, trivial/automated) and record why. A B PR whose review returns **zero findings** becomes a **clean-review** Gate 2 candidate (Step 6) so it is not re-reviewed on every run.
- **C PRs with a non-empty, non-rewritten unreviewed delta** (after Step 3 returns) — `/code-review high <feedbackBaseSha>...<headRefOid>` so only the new changes are reviewed (a null `feedbackBaseSha` means the whole-PR range as for B). The range is immutable, so no head re-check is needed for the review itself. A delta with zero findings counts as reviewed for Gate 2; a delta with findings makes the PR not approvable this run.

Wait for each review's completion in the conversation, then parse its findings into `{path, line, summary, failureScenario}` and record the `headRefOid` the review ran against. If more than 25 reviews are queued, confirm via `AskUserQuestion` before launching, offering to cap by most-recently-updated.

## Step 5 — Gate 1: post findings as inline review comments

Build the **exact payload per PR before asking**, bound to the reviewed `headRefOid`:

- Resolve each finding's anchor against the hunks of the same immutable range the review used, `git diff <MB>...<headRefOid>` on the local clone (not the mutable `gh pr diff`): a line that appears in any hunk on the new side — changed **or unchanged context** — is commentable as `{"path", "line", "side": "RIGHT", "body"}`; a line absent from every hunk goes into the review `body` as a bullet with a permalink `https://github.com/<owner>/<repo>/blob/<full headRefOid>/<path>#L<start>-L<end>`.
- Comment body: one or two sentences stating the defect and the failure scenario. No preamble, no emojis. `event` is always `COMMENT`.
- PRs with zero findings get no review at all (no "no issues" noise).

**Gate 1 — one `AskUserQuestion` per run.** Show, per PR: head SHA (short), inline count, body-fallback count, and the one-line list of findings (`path:line — summary`). Options: **post all** / **post none** / **Other** (free text naming PR numbers to skip). If everything is empty, say so and skip the gate.

After approval, for each PR still in scope: re-fetch `headRefOid`, `baseRefName` and `baseRefOid`; **if the head differs from the payload's SHA, or the base ref/SHA differs from the Step 1 record, skip the PR this run and report it** — never re-review and post without a fresh gate. Otherwise:

```bash
gh api --hostname github.com repos/<owner>/<repo>/pulls/<n>/reviews --method POST --input review.json
# {"commit_id":"<headRefOid>","event":"COMMENT","body":"<header + fallback bullets>","comments":[{"path":"...","line":N,"side":"RIGHT","body":"..."}]}
```

Check the exit status, record `.html_url`, and re-fetch `headRefOid`: if it no longer equals the returned `commit_id`, report the review as **posted against a superseded head**. On failure (422 line not in diff, 403 permissions, etc.) report the exact error for that PR and continue with the others; do not retry blindly.

## Step 6 — Gate 2: approve fully addressed PRs

A C PR is **approvable** only when **all** hold, using the Step 3 result plus the Step 4 delta review:

1. every item in `myFeedbackItems` is **Addressed** (none Replied-not-addressed, Pushback, No response, or Unverifiable);
2. the unreviewed delta is empty, or was reviewed with zero findings; history is not rewritten;
3. `ci` is **pass**, or **none** (no checks configured — say so in the reason); **fail** and **pending** block;
4. not a draft, PR still open;
5. no unresolved, non-outdated threads started by **other** reviewers, and no other reviewer's current `latestOpinion` is CHANGES_REQUESTED — a PR failing only this rule is listed as **approvable with caveat** and is included only if the user names it in the gate.

A **clean-review** B PR (Step 4: zero findings at its reviewed SHA) is approvable under rules 2–5 and is listed in the gate under its own heading so the user can leave it out.

Everything else is **waiting on author**, with the blocking items listed.

**Gate 2 — one `AskUserQuestion` per run.** List approvable PRs (head SHA short, reason such as "3/3 items addressed, delta of 2 files reviewed clean, CI pass"), then clean-review PRs, then approvable-with-caveat PRs, each under its own heading. Options: **approve all approvable** / **approve none** / **Other** (free text naming PRs to skip or caveat PRs to include). If no PR is approvable, say so and skip the gate.

After approval, for each PR still in scope, **re-run the Step 1 fetch for that PR and diff the whole record** against the one Step 3/4 used (head SHA, base ref and SHA, state, isDraft, CI, every review's state, thread set and resolution, body feedback, issue comments, others' opinions). If anything changed, **skip the PR this run and report what changed** — do not re-verify after the gate. Otherwise submit the approval through the REST endpoint so it is bound to the verified SHA (`gh pr review --approve` has no commit selector):

```bash
gh api --hostname github.com repos/<owner>/<repo>/pulls/<n>/reviews --method POST \
  -f commit_id=<headRefOid> -f event=APPROVE \
  -f body="All review feedback addressed on <short sha>. Approved."
```

Check the exit status and the returned `state`/`commit_id`, then re-fetch `headRefOid`: if it no longer equals the returned `commit_id`, report the approval as **bound to a superseded head** so the user can dismiss it. A failed call is an error in the summary, never an approval. GitHub offers no transactional read-then-write, so a change landing between the refresh and the POST is a residual, unavoidable window; the refresh, the SHA-bound POST, and the post-check keep it to seconds and make it visible. Do not resolve threads on the author's behalf; do not merge.

## Step 7 — Summary (chat only)

A brief chat summary, nothing else. Short lists, omit empty sections:

1. **Posted** — PRs that received review comments: number, title, inline/fallback counts, `html_url`. Then PRs reviewed with zero findings.
2. **Approved** — PRs approved this run with the SHA (feedback-addressed and clean-review listed separately). In `--dry-run` or if the gate was declined, title it **Approvable** and list what qualified (with caveat PRs marked).
3. **My PRs** — bucket A: approved (and whether ready to merge), changes requested, awaiting review — one line each.
4. **Waiting on author** — C PRs not approved: number, title, blocking items (`path:line — classification`), Pushback items for the user to decide, and C-alias PRs with the alias that must act.
5. **Skipped / errors** — declined reviews, incomplete-fetch PRs, PRs whose head or eligibility moved during or after a step, mutations bound to a superseded head, failed POSTs with the exact error, rewritten-history PRs.

Counts and per-PR lines only; never paste review bodies or diffs into the chat.

## Stop-and-ask conditions (use `AskUserQuestion`; do not silently proceed)

- The repo argument cannot be resolved, or the active `gh` login cannot access it.
- More than 25 `/code-review high` runs are queued (Step 4).
- The `code-review` skill is unavailable or errors on every PR — do not substitute an ad-hoc review; report and stop.
- Gate 1 and Gate 2 themselves. No other GitHub mutation exists in this skill.
