---
name: review-response
description: Answers a GitHub pull request's review comments end to end. Classifies each thread (agree, agree with modification, push back, needs clarification) with evidence from the code, tests, specs, and Jira ticket, grills the user on the contested calls, writes the plan to review_response_<PR#>.md, and has codex review it. Then implements the agreed changes, runs the project's gates, commits, pushes, posts an inline reply on every review thread, and updates the PR. Takes a PR link or number (defaults to the current branch's PR). Use when a PR has review comments to respond to, address, or resolve.
argument-hint: "[PR-URL | PR-number]"
---

# Review-response skill

Act as a principal engineer answering the review on a pull request. The flow:

snapshot the PR → gather evidence per item → classify and draft replies → **grill** the user on the contested calls → write `review_response_<PR#>.md` → codex review of the plan → implement and verify → **publish** (push, reply on every thread, update the PR) → report.

The user is consulted at two points: the grilling session, and the publish round before anything leaves the machine. Everything between runs unattended.

## Conventions

**Questions go through grilling.** Every question in this run uses the `grilling` skill's round format, exactly as that skill writes it (its `❓` and `➡️` markers included): the whole frontier in one numbered round, each question carrying a recommended answer worded so "yes" accepts it. Invoke **`mattpocock-skills:grilling`** with the Skill tool at Step 3. It is the skill `/grill-me` loads; call it by that name, because `/grill-me` sets `disable-model-invocation` and the Skill tool refuses it. The same format then carries every later question: a reopened decision, a stop, the publish round. `AskUserQuestion` stays unused here: the user wants batched rounds with recommendations, not one dialog per decision.

Facts are your legwork. Whatever the PR, the code, the ticket, or a command can answer gets looked up. Where a missing input has a safe default, take it and say so in the session's opening status instead of asking.

**Main loop and subagents.** The main loop owns everything that talks to the user or writes shared state: the grilling, the plan file, the final call on each review finding, commits, and the publish step. `general-purpose` subagents take bulky, self-contained work and return text. A subagent costs more than the context it saves when the work is small, so on a small PR (a handful of items in a few files, a gate that runs in seconds, a short findings list) do that work in the main loop. When you do delegate, launch independent subagents in one message so they run concurrently, and give each a self-contained prompt: absolute paths, the item bodies it needs, how to read the PR head, and the result shape to return.

**Helper script.** `python3 "${CLAUDE_SKILL_DIR}/scripts/pr.py"` does the GitHub plumbing (`fetch`, `reply`, `body`) and is written as `pr.py` below.

**Placeholders.** Create one scratch directory with `mktemp -d` and record its path as `<tmp>`. `<pr>` is the PR link, `<n>` its number, and `pr.url`, `head_oid`, and the like are fields of the Step 0 snapshot. Substitute the values yourself: shell variables do not survive between Bash calls.

**Voice.** Replies are posted under the user's GitHub login, so write them as the user: first person, direct, technical, respectful. Acknowledge what is right in a comment before disagreeing, and commit to specifics ("extracted this into `X` and added a test for `Y`") over "good point, fixed". Cite code by symbol or test name: the fix moves line numbers before the reply is read. Leave out emojis, signature lines, and any note on how the reply was produced.

## Step 0 - Snapshot the PR and pick the mode

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/pr.py" fetch [<PR-URL | PR-number>] --out "<tmp>/pr.json"
```

With no argument it uses the current branch's PR. It prints the counts and writes one JSON snapshot: `pr` (`url`, `title`, `body`, `author`, `state`, `head_ref`, `head_oid`, `head_repo`, `base_ref`), `viewer` (the login replies post as), `threads` (each with `root_comment_id`, `path`, `line`, `is_resolved`, `is_outdated`, `comment_count`, `diff_hunk`, `comments`), `reviews` (summary bodies and their `state`), `conversation` (top-level comments), and `ticket_candidates`. Exit 2 means no PR resolved: ask for the link. A `gh` auth failure is the user's to fix (`! gh auth login`).

Then settle three things:

- **Something to answer.** The items are every unresolved thread, plus each review summary or conversation comment that asks for something (bot and CI noise, acknowledgements, and the author's own comments ask for nothing). With no items, say so and stop.
- **Mode.** *Execute* needs the PR head checked out here: `gh pr view --json number` on the current branch resolves to this PR, `head_oid` is `HEAD` or an ancestor of it (`git merge-base --is-ancestor`), tracked files are clean (`git status --porcelain --untracked-files=no`), and the PR is `OPEN`. Local commits ahead of `head_oid` are fine: the publish round lists them. A miss becomes the first question of the Step 3 session. Its recommended answer is the remedy (`gh pr checkout <pr.url>` on a clean tree, `git pull --ff-only` when behind, commit or stash for local changes) and it names *plan-only* as the alternative. Plan-only runs Steps 0-5 and the report, changing and posting nothing; it is the only mode when this directory is not a clone of `head_repo` or the PR is closed.
- **Plan file.** The plan is `review_response_<n>.md` in the current directory: a working document that is never staged or committed. When it already exists, update it in place: keep the entry of every thread whose `comment_count` is unchanged, with the user's edits and its `Posted:` line; redo threads that changed; add new ones; mark threads resolved since. Steps 1-5 then cover only the new and changed items.

## Step 1 - Gather evidence

Read the repo's `CLAUDE.md` first when it has one: its rules outrank a reviewer's preference and this skill.

Read the flagged code **at `head_oid`**, never the base branch's version of a line: the working tree when `HEAD` is `head_oid`, otherwise `git show <head_oid>:<path>`. If `git cat-file -e <head_oid>^{commit}` fails, fetch it once before any fan-out (`git fetch origin <head_ref>`, or `pull/<n>/head` for a fork); outside a clone, use `gh api` file contents at `head_oid`.

Two kinds of evidence, gathered together:

- **The ticket**, when `ticket_candidates` is non-empty and an Atlassian MCP server is connected. Load its tools with ToolSearch (`+atlassian getJiraIssue`, and `getAccessibleAtlassianResources` for the `cloudId`), fetch each candidate with `fields: ["*all"]`, and drop keys that resolve to no issue (the pattern also matches tokens like `UTF-8`). Keep the summary, description, acceptance criteria, status, linked issues, and recent comments of the ticket this PR implements; if more than one is plausible, keep each and flag it. With no ticket, or Jira unreachable, the plan's header says "Jira context unavailable"; ticket content is never reconstructed from memory.
- **One evidence row per item**, clustering related items (same file or subsystem, a shared root cause, explicit cross-references) so each cluster is read once. Check three sources: the **code** at the flagged site (the whole hunk the comment sits on, since a vague comment often points at a defect a line or two away), the **tests** that cover it (does a test already settle the reviewer's concern, contradict it, or is it untested), and the **specs** (`specs/<name>/` requirements, plan, and validation docs for this branch, plus any design doc the PR cites). The row: `item id - what the code does there, with file:line - what the tests cover or miss - what the spec says, or "no spec coverage" - the reviewer's claim holds: yes / partially / no, with a one-line reason`.

**Done when** every item has an evidence row.

## Step 2 - Classify and draft

Decide each item on its evidence, weighing the ticket's acceptance criteria as the statement of intended behavior:

- **Classification**
  - `Agree` - the reviewer is right; plan the fix.
  - `Agree with modification` - the concern is valid, a different remedy is better; plan that one and say why. Before asking the user to prefer your remedy over the reviewer's, confirm it works against the head code (trace it, or prototype it in `<tmp>`) and name what it changes for existing callers.
  - `Push back` - the code is right as written. The case rests on code behavior, a test, a spec section, or a ticket criterion, never on preference or seniority.
  - `Needs clarification` - the comment is ambiguous or rests on an unstated assumption; draft the specific question that would settle it.
- **Evidence** - the file:line, test, spec, and ticket citations behind the classification.
- **Action** - for the two `Agree` classes: the files, the approach, the tests to add or change, any spec update when behavior changes, and a size (S / M / L). Otherwise "no code change".
- **Reply** - the text to post, in the *Voice* above, written as it will read once the work has landed: past tense, with a named placeholder such as `<sha:boundary-fix>` for each commit it cites, one name per planned commit.

Then look across the items: name each **cross-cutting theme** (three comments pointing at one missing abstraction get one action, not three), order the actions so a fix that settles several comments is done once, and flag any item whose fix changes the PR's scope enough to belong in a follow-up ticket. Resolved and outdated threads are listed for completeness and get no action unless their concern is still live in the head code. A defect the evidence turned up that no reviewer raised joins an action only when it shares that action's root cause; otherwise it goes to the plan's Open questions. No reply may lean on something the evidence showed to be false.

**Done when** every item has exactly one classification, its evidence, an action, and a reply.

## Step 3 - Grill the user on the contested calls

Invoke the grilling skill and run its session to completion. Open with a status block so the user sees the whole picture before the first round: the PR, the ticket used (or unavailable), the mode, the count per classification, and the plain `Agree` items as a one-line-each list. Those are settled by the evidence and are not questions.

Seed the design tree with what is the user's to decide, each question carrying the evidence behind its recommended answer:

- **Execution blockers** from Step 0, in the first round.
- **Push backs** - each one. The user owns the relationship with the reviewer, so they see the reviewer's point, the evidence, and the stance before it is taken in their name.
- **Agree with modification** - the reviewer's remedy against the one planned.
- **Clarifications** - each one: the user may know what the reviewer meant, and the question goes to the reviewer only if they do not.
- **Scope** - an L-sized fix, or one that changes what the PR delivers: in this PR, or a follow-up ticket.
- **Intent gaps** - a classification that turns on product intent neither the spec nor the ticket settles.
- **Ambiguous ticket** - only when Step 1 kept more than one.

With nothing contested, the session is one confirmation round.

**Done when** the frontier is empty and the user has confirmed shared understanding. List the **settled decisions** (`D1`, `D2`, ...) in the conversation: Step 4 records them, Step 5 checks findings against them.

## Step 4 - Write the plan

Write `review_response_<n>.md` in this order:

1. **Header** - PR link, title, author, branches; the ticket key, summary, and status (or "Jira context unavailable"); the date; the mode; item counts (total / unresolved / resolved or outdated). In plan-only mode, say that the replies are drafts of what to post once the work lands.
2. **Summary table** - one row per item: anchor (`path:line`, reviewer, first-line excerpt), classification, size.
3. **Settled decisions** - `D1...Dn` from Step 3.
4. **Cross-cutting themes** - each shared root cause and the one action that addresses it.
5. **Per-item detail** - the comment (quoted), classification, evidence, action, reply, dependencies on other items, and a `Posted:` line. A thread records its `root_comment_id` and `comment_count` from the snapshot, which Step 7 posts with; review summaries and conversation comments record their `id` and are answered together in the one conversation comment.
6. **Execution order** - a numbered checklist of the code, test, and spec changes in the order to make them, grouped into the planned commits.
7. **Open questions** - anything the user deferred, clarifications awaiting a reviewer, and defects no reviewer raised.
8. **Plan review** - the Step 5 disposition table.

The plan states only what has happened: commit placeholders stay placeholders until Step 6 creates the commits, checklist boxes stay unticked until the work is done, and `Posted:` stays empty until Step 7 returns a URL.

## Step 5 - Codex review of the plan

Run `command -v codex` in the main loop. When it resolves, dispatch one subagent that follows `${CLAUDE_SKILL_DIR}/CODEX.md` (pass the absolute path), giving it the repo root, the plan path, the PR URL, `head_oid`, the settled decisions, and `<tmp>`. It returns the findings verbatim, or `failed` with a reason.

When codex is absent or the subagent returns `failed`, run the review natively without asking: two adversarial `general-purpose` subagents in one message. One audits the **diagnosis**: every item covered, each classification following from its evidence, each cited fact true at `head_oid`. The other audits the **response**: whether each planned change resolves the concern and is testable as planned, whether each reply is accurate and specific, and whether the execution order and scope calls hold. Give both the plan path, `<tmp>/pr.json`, the settled decisions, and how to read the head code; ask for numbered findings, each citing the plan item and the file:line it concerns. Name the substitution and its reason in the report.

Findings are hypotheses, not orders. Merge duplicates, then give each finding **accept**, **reject**, or **defer** with one line of evidence, checked against the threads, the Step 1 rows, the ticket, and the settled decisions. When the list is long and its findings each need their own investigation, split it into disjoint batches of three to five, contradicting findings sharing a batch, with one adjudication subagent per batch. Apply the accepted ones to the plan and record the table in its Plan review section.

A finding that would change a settled decision reopens that branch of the grilling session before it is applied. A finding that only disputes a choice the user made is rejected.

**Done when** every finding has a disposition and the plan reflects each accepted one. The plan is now final; show the user the disposition table and carry on. In plan-only mode, go to Step 8.

## Step 6 - Implement and verify

Work through the plan's Execution order on the checked-out PR branch, one planned commit at a time:

- **Test first** wherever an action changes behavior: write the test that fails on the reviewer's scenario, then the fix. Follow the repo's own conventions, layering, and test idioms.
- **Stay inside the plan.** Make the smallest change that satisfies the item. When an action proves wrong or wider than planned, update its entry in the plan; if that touches a settled decision, reopen that branch with the user before continuing.
- **Commit each action or theme when its tests pass**, before starting the next edit to a file it shares with a later commit, so every commit stages whole files. These are new commits on top of the branch: reviewers follow "changes since my last review", which amended or rebased history erases, and a fast-forward push never needs force. Match the repo's commit convention from `git log`, stage explicit paths (`git add -- <path>...`), and include the trailers the environment requires. Independent M or L actions in separate files may go to subagents launched together; the main loop commits their work.
- **Gates.** With the commits in, run the project's format, lint, build, and full test gates over `HEAD`, using the commands the repo defines (`CLAUDE.md`, the CI config, the task file), each bounded by a timeout. Fix a failure this work caused in a further commit and run all of them again; the same applies when a commit hook rewrites files. A failure that also reproduces at `head_oid` (check in a throwaway `git worktree`) predates this work: put it to the user (fix it, stop, or publish with the waiver named in the PR). A gate the repo does not define is reported as not configured, never as green.

Then fill each commit placeholder in the plan's replies with its short SHA, and re-read every reply against `HEAD`: each one must describe what the code now does.

**Done when** every planned action is committed, the gates are green on `HEAD`, the tree is clean apart from the plan file, and no reply holds a placeholder.

## Step 7 - Publish

Nothing has left the machine yet, and a notification cannot be recalled, so prepare everything, show it once, then send it.

**Prepare** in `<tmp>`:

- `replies.json` - one `{"reply_to": <root_comment_id>, "seen_comments": <comment_count>, "body": "..."}` per thread, and at most one `{"conversation": true, "body": "..."}` that answers the review summaries and top-level comments together, quoting each point it answers.
- `pr-section.md` - what changed in response to review, by theme with commit SHAs, and what was deferred (with its ticket, or "no ticket yet"). Where a change makes a statement in the existing description false, say so here; the rest of the description stays as its author wrote it.
- The outgoing commits (`git log --oneline <head_oid>..HEAD`) and the push destination: `head_ref` on the remote the current branch pushes to (`branch.<current>.pushRemote`, else `branch.<current>.remote`).
- The reviewers to re-request: those who requested changes and whose threads all receive a reply.

Run `pr.py reply <pr> "<tmp>/replies.json" --dry-run` to learn which threads would be held.

**Publish round** (one question, grilling format). Show the destination and the outgoing commits; each reply as one line (`path:line - reviewer - classification - what the reply says, in a few words`), with the plan path for the full text; the PR section; the reviewers to re-request; anything the dry run would hold. "Yes" publishes all of it, and the user may strike any part.

**Send**, in this order, each step only after the one before it succeeded:

1. **Push** with `git push <remote> HEAD:refs/heads/<head_ref>`; with no outgoing commits there is nothing to push, so start at the replies. A rejected push means the branch moved: stop and put it to the user; force is theirs alone to choose. Verify with `pr.py fetch <pr> --out "<tmp>/pr-after.json"`: `pr.head_oid` must equal `git rev-parse HEAD`. GitHub can lag by some seconds, so try up to three times. Replies citing commits the reviewers cannot see would mislead, so an unverified push ends the step here.
2. **Reply** with `pr.py reply <pr> "<tmp>/replies.json"`. Write each `posted` URL into its item's `Posted:` line. A `held` thread was resolved or gained a comment after the snapshot, so its reply may no longer fit: leave it unanswered and report it with the latest comment. Report a `failed` reply with its exact error; one attempt each.
3. **Update the description** with `pr.py body <pr> "<tmp>/pr-section.md"`. It replaces only this skill's marked block, so a later round updates the block instead of stacking another.
4. **Re-request review** with `gh pr edit <pr.url> --add-reviewer <logins>`, leaving out any reviewer with a held or failed thread.

Threads stay unresolved: resolving one is the reviewer's acknowledgement to give.

**Done when** each part the user approved is sent and verified, or reported with the reason it was not.

## Step 8 - Report

Remove `<tmp>`, then report. Keep it short, and point at the plan file for the detail:

- **Plan** - the path; item counts per classification; the ticket used, or that it was unavailable.
- **Review** - codex or the native substitute (and why); findings accepted / rejected / deferred, with one line per rejection.
- **Changes** - the commits, and each gate as pass / fail / not configured, naming any waiver.
- **Published** - the push and its verified head; replies posted, held, and failed, each held or failed one with its reason; the PR description update; the reviewers re-requested. In plan-only mode: that nothing was changed or posted, and what has to be true to execute.
- **Open** - clarifications awaiting reviewers, deferred items and their follow-up tickets, and any remaining risk.
