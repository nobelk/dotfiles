---
name: review-response
description: Prepare a principal-engineer-grade plan for responding to a pull request's review comments, written to review_response_<PR#>.md — per-thread classification (agree / modify / push back / clarify) with evidence from the code, tests, specs, and Jira ticket, a drafted reply each, and sequencing, then codex-reviewed. Takes a GitHub PR link or bare number as the argument (inferred from the current branch if omitted). The plan file is the only deliverable — never posts to the PR or changes code. Invoke manually when a PR has review comments to respond to.
---

# Review-response skill

Act as a principal software engineer preparing to respond to code review feedback on a pull request. The flow is: fetch PR + review comments → find the Jira ticket → analyze the codebase/tests/specs against each comment → write a response plan to `review_response_<PR#>.md` → codex review of the plan with validated findings folded back in. The plan is the deliverable — nothing is posted to the PR and no code is changed.

## Subagent delegation — parallel by default

Run the expensive, self-contained steps in **`general-purpose` subagents** (via the `Agent`/`Task` tool) and keep orchestration in the main loop. When two or more subagent tasks are independent, **launch them in a single message with multiple `Agent` tool calls so they run concurrently** — never serialize subagents that don't depend on each other's output.

- **Main loop owns** (never delegate): every `AskUserQuestion` gate, writing/editing `review_response_<PR#>.md`, and the final report — subagents cannot prompt the user.
- **Delegate, in parallel**:
  - Steps 1 and 2 overlap: once the PR metadata (title, body, branch, commits) is in hand, launch the Jira ticket identification/fetch (Step 2) as a subagent **in the same message as** the Step 1 deep-fetch subagent (threads, reviews, diff, resolution state) — neither needs the other's output. Any `AskUserQuestion` gate in Step 2 (ambiguous ticket, MCP unavailable) is raised by the main loop after the subagent returns its candidates.
  - Step 3 fans out: cluster the comment threads and launch **one subagent per cluster, all in one message**. Wall-clock time is the slowest cluster, not the sum.
  - Step 6 adjudication fans out: split codex findings into batches and adjudicate the batches in parallel subagents.
- Give each subagent a self-contained prompt with exact commands, file paths, comment bodies, and the precise result shape to return — parallel subagents share no state, so anything a subagent needs must be in its prompt.
- Parallel subagents must be **read-only with respect to shared state**: none of them may write the plan file or mutate the working tree; each returns findings as text and the main loop merges them. If two clusters need the PR head fetched locally, the main loop runs the `git fetch` once before fanning out so subagents don't race on the same ref.

## Step 0 — Resolve inputs

The skill accepts one argument: a GitHub PR link (`https://github.com/<owner>/<repo>/pull/<number>`) or a bare PR number (resolved against the repo in the current directory).

- Verify `gh` is authenticated (`gh auth status`). If not, stop and tell the user to run `gh auth login` (suggest `! gh auth login` so it runs interactively in the session).
- If a full URL is given, parse `<owner>/<repo>` and `<number>` from it. Pass `--repo <owner>/<repo>` to every `gh` call so the skill works even when the cwd is a different clone; if the cwd is not a clone of that repo, note it — Step 3's code analysis then reads files via `gh api` / `git fetch` of the PR head instead of the local tree.
- If no argument is given, try `gh pr view --json number,title,url` on the current branch. If it resolves, confirm that PR with the user via `AskUserQuestion`; if it doesn't, ask the user for the PR link — do not guess.
- The output path is always **`review_response_<PR#>.md` in the current working directory** (e.g. `review_response_1234.md`).
- If the plan file already exists, use `AskUserQuestion` to ask whether to **overwrite**, **update in place**, or **abort**. Update in place means: re-fetch all threads; keep entries for threads whose comments are unchanged (preserving any user edits to the drafted replies); add new threads; mark threads now resolved on GitHub as `✅ Resolved`; and re-run Steps 3–6 only for new or changed threads.

## Step 1 — Fetch the PR and its review comments

Gather the full review context via `gh` (JSON output, not screen-scraping):

- PR metadata: `gh pr view <n> --json number,title,body,headRefName,baseRefName,state,author,url`.
- The diff: `gh pr diff <n>` (and `gh pr view --json files` for the changed-file list).
- Inline review threads: `gh api repos/<owner>/<repo>/pulls/<n>/comments --paginate` — these carry `path`, `line`/`original_line`, `diff_hunk`, `in_reply_to_id`, and `pull_request_review_id`. Reconstruct threads by grouping on the root comment (`in_reply_to_id` chains).
- Reviews (approvals / change requests and their summary bodies): `gh api repos/<owner>/<repo>/pulls/<n>/reviews --paginate`.
- Top-level conversation comments: `gh api repos/<owner>/<repo>/issues/<n>/comments --paginate` — include only those that are actual review feedback, not bot/CI noise.
- Thread resolution state: `gh api graphql` on `reviewThreads { isResolved isOutdated }` — resolved and outdated threads are listed in the plan for completeness but marked as such and given no action unless their content is still live.

If the PR has no unresolved review comments, say so and use `AskUserQuestion` to ask whether to still produce a plan covering resolved/outdated threads or stop.

## Step 2 — Identify the associated Jira ticket

- Extract candidate ticket keys (`[A-Z][A-Z0-9]+-\d+`) from, in priority order: the PR head branch name, the PR title, the PR body, and the PR's commit messages (`gh pr view --json commits`).
- Exactly one candidate: fetch it. Multiple candidates or zero: present the candidates (or ask for a key) via `AskUserQuestion`.
- Fetch the ticket with the Atlassian MCP tools (`mcp__claude_ai_Atlassian__getJiraIssue`; load via ToolSearch first if deferred). Capture: summary, description, acceptance criteria, status, linked issues, and recent comments — this is the source of truth for *intended* behavior when adjudicating review comments in Step 4.
- If the Atlassian MCP server is not connected or the fetch fails, do not fabricate ticket content: ask via `AskUserQuestion` whether to proceed without the ticket (the plan then notes "Jira context unavailable" wherever ticket evidence would apply) or stop.

## Step 3 — Analyze the codebase, tests, and specs against each comment

Cluster related comment threads (same file/subsystem, same root cause, or explicit cross-references), then delegate **one `general-purpose` subagent per cluster, launched together in a single message so they run in parallel** (a small PR with one natural cluster gets one subagent). Each subagent's prompt must include the comment thread bodies with their `path:line` anchors and `diff_hunk`s, the PR branch names, and this required return shape per thread: `thread-id — <what the code actually does at the flagged site, with file:line evidence> — <what the tests cover or miss for it> — <what the spec/ticket says, or "no spec coverage"> — <does the reviewer's claim hold: yes / partially / no, with one-line reasoning>`.

The analysis must ground every judgment in three sources:

1. **Codebase** — read the flagged code on the PR head (fetch it without mutating the working tree: `git fetch origin pull/<n>/head:refs/remotes/origin/pr-<n>` then `git show origin/pr-<n>:<path>`, or `gh api` file contents at the head SHA). Never analyze the base branch's version of a flagged line.
2. **Tests** — locate the tests covering the flagged code (by package/module convention); note whether the reviewer's concern is already covered by a test, contradicted by one, or untested.
3. **Specs** — read `specs/<name>/` docs matching the branch/ticket (plan.md, requirements.md, validation.md per this machine's conventions) plus any `docs/` or design files the PR references; note where a comment conflicts with or is settled by the spec or the Jira ticket.

## Step 4 — Build the response plan (principal-engineer judgment)

For **every unresolved thread** (and summary-review bodies that request changes), decide:

- **Classification** — one of:
  - `Agree` — the reviewer is right; plan the fix.
  - `Agree with modification` — the concern is valid but the proposed remedy isn't the best one; plan the better fix and explain why.
  - `Push back` — the code is correct as written; the reply must cite evidence (code behavior, test, spec section, or ticket AC), never seniority or preference.
  - `Needs clarification` — the comment is ambiguous or rests on an unstated assumption; draft a specific question, not "can you clarify?".
- **Evidence** — the file:line, test, spec, or ticket citations from Step 3 that justify the classification.
- **Proposed action** — for `Agree`/`Agree with modification`: the concrete change (files, approach, new/updated tests, spec updates if behavior changes), sized S/M/L. For `Push back`/`Needs clarification`: explicitly "no code change".
- **Drafted reply** — the exact text to post on the thread, written as a principal engineer: direct, technical, respectful; acknowledges what's right in the comment before any disagreement; commits to specifics ("will extract this into X and add a test for Y") rather than "good point, will fix".
- **Priority and sequencing** — order actions so that comments invalidated by another comment's fix are handled once; flag any comment whose resolution changes the PR's scope enough to warrant a Jira ticket update or a follow-up ticket instead of cramming it into this PR.

Also surface **cross-cutting themes** (e.g. three comments all pointing at the same missing abstraction) as their own plan section, since responding thread-by-thread would miss them. Where a classification genuinely depends on product intent that neither spec nor ticket settles, route it through `AskUserQuestion` rather than guessing — the user's answer is recorded in the plan as the deciding evidence.

## Step 5 — Write review_response_<PR#>.md

Write the plan in this order:

1. **Header** — PR link/title/author/branches, Jira ticket key + summary + status (or "unavailable"), generation date, counts (threads total / unresolved / resolved-outdated).
2. **Summary table** — one row per thread: thread anchor (`path:line`, reviewer, first-line excerpt), classification, action size, priority.
3. **Cross-cutting themes** — shared root causes and the single action that addresses each.
4. **Per-thread detail** — for each thread: the comment (quoted), classification, evidence, proposed action, drafted reply, dependencies on other threads.
5. **Execution order** — a numbered checklist of code/test/spec changes in the order to make them, followed by the reply-posting order.
6. **Open questions** — anything routed to `AskUserQuestion` that the user deferred, plus clarification replies awaiting reviewer answers.

## Step 6 — Codex review of the plan

Have codex (OpenAI Codex CLI) review the plan, then validate and address its comments:

1. **Run the review in a `general-purpose` subagent**: launch `/codex:adversarial-review --background` targeting `review_response_<PR#>.md` (review focus: is every unresolved thread covered; do classifications match the cited evidence; are push-backs actually defensible from the code/tests/specs; are drafted replies specific and professional; is the execution order dependency-correct; is anything scoped into this PR that belongs in a follow-up ticket). The subagent polls `/codex:status` to completion, fetches `/codex:result <job-id>`, and returns the raw findings verbatim.
2. **Adjudicate each finding in parallel**: split the findings into batches (one per plan section, or ~3–5 findings each) and launch one adjudication subagent per batch **in a single message**. Each returns an accept/reject/defer disposition table with one-line evidence per finding, validated against the PR threads, the Step 3 analysis, and the Jira ticket — codex comments are input, not orders. Batches must be disjoint; if two findings contradict each other, put them in the same batch so one subagent resolves the conflict.
3. **Apply accepted findings** to the plan file in the main loop. Any finding that hinges on a judgment call you cannot settle from the evidence goes to the user via `AskUserQuestion`; never silently flip a classification.
4. If codex is unavailable or the review fails, say so explicitly and use `AskUserQuestion` to ask whether to finalize the plan without the review or stop.

## Step 7 — Report

Tell the user: the plan file path; thread counts by classification (agree / agree-with-modification / push back / needs clarification); the Jira ticket used (or that it was unavailable); the codex findings disposition (accepted/rejected/deferred counts); and any open questions blocking replies. Do not paste the whole plan into the chat, and do not post anything to the PR — point the user at the drafted replies in the plan file instead.
