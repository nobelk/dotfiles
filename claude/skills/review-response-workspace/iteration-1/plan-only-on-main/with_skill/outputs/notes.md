# Notes on the review-response skill (plan-only-on-main run)

Run shape: Steps 0-5 and 8. Steps 6-7 skipped (plan-only). Four subagents were spawned (evidence, codex, two adversarial reviewers), about 218k subagent tokens and roughly 10 minutes of subagent wall time, for a PR of 102 added lines. Nothing was committed, pushed, or posted; `gh-state/state.json` is byte-identical to `state.initial.json`.

I did not read `CODEX.md` or the source of `pr.py` myself (the skill has the codex subagent read `CODEX.md`, and never tells the main loop to read either). The CODEX.md section below is relayed from the subagent that followed it.

## Where the skill was unclear, wrong, or missing something

### Step 0 - snapshot and mode

1. **Review summaries have no slot in the plan format.** Step 4 says per-item detail carries "`root_comment_id` and `comment_count` from the snapshot (Step 7 posts with them)". Review 7001 is an item (Step 0: "each review summary or conversation comment that asks for something") but has neither field. I recorded `review id: 7001` and a note that it is answered through `{"conversation": true}`. The skill should say what a non-thread item records, and note that such items get no `seen_comments` protection.
2. **Plan-only is never offered as an option in the blocker question.** "A miss becomes the first question of the Step 3 session, with the remedy as its recommended answer: `gh pr checkout <pr.url>` on a clean tree". Plan-only is described only as "the remedy when this directory is not a clone of `head_repo` or the PR is closed, and the user may choose it at any time". I had to decide on my own to name plan-only as the alternative in Q1. For a user sitting on `main` on purpose, the skill should say to present both.
3. **Mode is unknown through Steps 1-2.** The blocker question is asked at Step 3, so evidence and drafting run without knowing whether anything will be implemented. That worked, but replies are drafted "as it will read once the work has landed: past tense" (Step 2) even when the run turns out to be plan-only. The plan then holds first-person claims of work nobody did. Nothing in the skill says to mark them as drafts in plan-only mode; I said so in the header only.

### Step 1 - evidence

4. **The prescribed fetch failed and there is no fallback.** "run `git fetch origin pull/<n>/head:refs/remotes/origin/pr-<n>` once before fanning out". Here: `fatal: couldn't find remote ref pull/7/head` (the sandbox origin is a bare repo with no `pull/*` refs; the same happens on any non-GitHub mirror remote). `head_oid` was already present locally (`origin/feat/RATE-12-limiter`). The skill should check `git cat-file -e <head_oid>^{commit}` first and have subagents use `git show <head_oid>:<path>`, fetching only when the object is missing, then falling back to `git fetch origin <head_ref>`.
5. **No inline path for a tiny PR.** "a small PR is one cluster" still means one subagent. For a 39-line file, a 55-line test file, and an 8-line spec, the subagent cost 38k tokens and 70 seconds, and I re-read all three files afterwards anyway to check the rows before putting stances in the user's name. A threshold ("under N changed lines, gather the evidence in the main loop") would have saved that.
6. **Ticket subagent has no cheap precheck.** "A ticket subagent, when `ticket_candidates` is non-empty." Nothing says to check first whether any Atlassian tool is connected. (Deviation below: I did not launch it.)
7. **Nothing validates a planned remedy.** The evidence row shape asks only whether "the reviewer's claim holds". The evidence subagent volunteered a remedy for 5003 ("drop a key when its deque is empty after pruning") that cannot work: with `limit >= 1`, an emptied deque is always appended to in the same call, so the stale keys are the ones never touched again. In execute mode Step 6 would catch that; in plan-only mode ("Steps 0-5, then the report") a wrong Action reaches the final plan unless the Step 5 reviewer happens to build it. I prototyped the fix in `<tmp>` on my own initiative, which is what exposed it. For `Agree with modification` in particular (the user is asked to prefer my remedy over the reviewer's), the skill should require the remedy to be demonstrated before Step 3.
8. **Unraised defects have no home.** The evidence pass found four spec gaps no reviewer mentioned (stale docstring, `TypeError` vs R4's `ValueError`, NaN accepted, untested negative arguments). Step 2 covers only "items"; Step 3's seed list has no entry for them. I folded one into an existing action and made the rest a grilling question (Q5), then Open questions. The skill should say whether to fix, ask, or just list them.

### Step 2 - classify and draft

9. **Replies that cite `file:line` go stale by the time they are posted.** Step 2 asks for "the file:line ... citations behind the classification" as Evidence and for a Reply "written as it will read once the work has landed". I carried `limiter.py:15` and `limiter.py:34-35` from the evidence into the 5002 push-back reply. Those numbers are true only at `head_oid`; the fix commits move `_check_arguments` down nine lines before the reply is posted. A reviewer caught it. The skill should say: replies cite by symbol or test name, or Step 6's "replace each `<sha>`" also re-checks every line reference against the new `HEAD`.
10. **"Priority" is undefined.** Step 4's summary table wants "classification, size, priority", but priority is never defined or assigned in Step 2. I invented P1-P3 (P1 = spec violation or named merge blocker from a changes-requested review).
11. **Commit planning is underspecified for overlapping files.** Step 6: "one per action or theme where their files are disjoint, otherwise one combined commit". The docstring fix (theme T2) and the limiter fixes (theme T1) both touch `ratelimit/limiter.py`. My first Execution order made both edits and then described two commits, which cannot be staged without interactive hunk selection. A reviewer caught it. The skill could say: when two commits share a file, order the edits so each commit is made before the next edit to that file.

### Step 3 - grilling

12. **The grilling format's emoji markers collide with the harness rule.** "Every question in this run uses the `grilling` skill's round format", and that format is literally `❓ **Q1** - ...` / `➡️ <recommended answer>`. The Claude Code system prompt says the assistant must avoid emojis. I kept the structure and replaced the markers with `**Q1** -` and `Recommended:`. The skill should state which wins, since its own Voice section bans emojis only in replies.
13. **Needs-clarification items are not in the seed list.** The list is push backs, agree with modification, scope, intent gaps, ambiguous ticket. 5004 ("Hmm, is this right?") fits none, yet a question to a reviewer is posted in the user's name and the user may simply know what Tom meant. I asked it (Q4). Either add it to the list or say it is settled by the evidence.
14. **Dependent questions cost a second round by construction.** The follow-up-ticket question (Q6) depends on Q3, so the grilling format ("A question whose answer depends on another question still open in this round belongs to a later round") forces Round 2. Combined with "Do not act on it until the user confirms you have reached a shared understanding", a run with any contested call is at least two rounds, which sits oddly with "The user is consulted twice: the grilling session, and the publish round". Not wrong, but the skill could say whether a recommended-path follow-up may be folded into its parent question.
15. **Is a closing confirmation round required when there were contested calls?** "With nothing contested, the session is one confirmation round" and "Done when the frontier is empty and the user has confirmed shared understanding". It is unclear whether answering the last question counts as that confirmation. I added an explicit confirmation question (Q7) to Round 2.

### Step 4 - plan

16. **No section for the Step 5 outcome.** Step 5 says "show the user the disposition table", and Step 8 wants only counts "with one line per rejection". In plan-only mode the plan file is the only artifact that survives, and the seven-section layout has nowhere to put the table. I added an eighth section, "Plan review (Step 5)".
17. **`.gitignore` is not mentioned.** The plan is "a working document that is never staged or committed", written into the repo root, but nothing suggests checking that it is ignored. It shows up in `git status` as untracked, one `git add -A` away from being committed by something else.

### Step 5 - codex review

18. **A subagent is spent to learn that codex is absent.** "Dispatch one subagent that follows `${CLAUDE_SKILL_DIR}/CODEX.md`". It cost 38k tokens and 55 seconds to return `STATUS: failed / REASON: codex absent`. The main loop could run `command -v codex` first and go straight to the native reviewers.
19. **The native fallback is two sentences.** "one checking that every item is covered and each classification follows from its evidence, the other attacking the replies, the execution order, and the scope calls". No result shape, no cap on findings, no mention of giving them `<tmp>/pr.json`, the settled decisions, or how to read the PR head when the tree is elsewhere. I wrote all of that. They were worth it here (they found the test-pinning gaps, the stale line numbers, and the impossible commit order), but they cost 63k and 79k tokens and 3-5 minutes each on a 102-line PR.
20. **"About five or fewer" does not say whether duplicates count.** "Adjudicate about five or fewer in the main loop; split more into disjoint batches of three to five ... and fan out one adjudication subagent per batch." I had 10 raw findings, 8 distinct. (Deviation below.)
21. **The reopen rule has a gap.** "A finding that shows a settled decision rests on a wrong fact ... reopens that branch". Two reviewers showed that a fact I gave the user in Q5(b) was wrong in its cause, while the decision built on it (defer) became more justified, not less. The skill does not cover "the fact was wrong but the decision is reinforced". I reopened with one question, because the wording of D5 itself had to change.
22. **Sandbox mismatch (environment, not the skill).** The codex subagent reported that `command -v codex` actually succeeds on this machine and a companion script resolves; it returned `codex absent` only because the sandbox rule said to treat the check as failing.

### Steps 7-8

23. **`<tmp>` is never removed in plan-only mode.** The only cleanup instruction is in Step 7 ("Remove `<tmp>` when done"), and plan-only goes from Step 5 to Step 8. I removed it anyway.
24. **Step 8's "Changes" bullet in plan-only mode.** "each gate as pass / fail / not configured" has no value for "defined but not run". I reported `make lint` and `make test` as defined and not run, and format and build as not configured.

## Helper script (`scripts/pr.py`)

- `fetch` worked on the first call against the fake `gh` (three `gh api` calls), and the snapshot matched the field list in Step 0. Nothing in it needed working around.
- The printed summary gives thread counts and `reviews_requesting_changes`, but not how many review summaries or conversation comments have a non-empty, non-bot, non-author body. Those are the ones Step 0 makes me judge by hand. A count like `review_bodies_to_read: 1` would make "Something to answer" checkable at a glance.
- `ticket_candidates` listed RATE-12 once with `source: branch`, though the key is also in the PR title and body. It is unclear whether sources are deduplicated in some priority order; it did not matter here.
- `reply` and `body` were not exercised (plan-only), including `--dry-run`.
- Not the script's fault: my first spot-check command used `$H:tests/...` under zsh, where `:t` is a history modifier, and failed. The skill's instruction to "Substitute the values yourself" would have avoided it; I used a variable for brevity.

## `CODEX.md` (relayed from the subagent that followed it)

- The absent-codex path is clear and fast: "Check `command -v codex` (absent: return `failed: codex absent` at once)". But that shorthand does not match the required return block (`STATUS:` / `REASON:` / `DETAIL:`), and `DETAIL: <the error text or the last log lines>` has no defined content when `command -v` prints nothing.
- **It would not have worked off the PR head.** "`--scope working-tree` puts the uncommitted plan file in front of the reviewer" is true only for the plan. With the tree on `main`, none of the cited files (`ratelimit/limiter.py`, the tests, the spec) are on disk, and the focus text ("the code under review is the PR head, <head-oid>") does not tell the reviewer to use `git show <head-oid>:<path>`. A reviewer reading from disk could report every citation as missing. Plan-only runs are exactly the case where the tree is off the head.
- The reviewer is asked whether every unresolved thread is covered but is never given the thread list; `<tmp>/pr.json` is not referenced.
- The focus text says only "The user's settled decisions were: <D1...Dn>", with no sentence on what a finding may or may not do with them.
- "`not a git repository`" appears both as a trigger for the direct one-shot fallback and as a `REASON:` value.
- On the companion path no result filename is given (only the direct path names `<tmp>/codex-result.md`).
- The companion skips untracked files over 24 KB. This plan was 20 KB before the review and is 25 KB now, so a second pass would have silently dropped it from the inlined context.
- "bounded 4-minute wait; repeat until finished" does not fit "Hard deadline: 10 minutes".
- "launch with run_in_background: true" plus `--background` creates a detached process with no trap, no upper bound, and no orphan check, which the user's global `AGENTS.MD` requires of any background process.

## Deviations from the skill

1. **Ticket subagent not launched.** Skill: "A ticket subagent, when `ticket_candidates` is non-empty." `ticket_candidates` had RATE-12. Sandbox rule 2 forbids any Atlassian tool or ToolSearch for one, so I took the skill's own fallback ("With no ticket, or Jira unreachable, the plan says 'Jira context unavailable'") and said so in the opening status.
2. **`git show <head_oid>:<path>` instead of `origin/pr-7`.** The prescribed `git fetch origin pull/7/head:...` failed (note 4). The commit was already local, so no ref was created.
3. **Loaded the grilling skill before Step 3.** Skill: "Invoke `mattpocock-skills:grilling` with the Skill tool at Step 3." I invoked it while the Step 1 subagent was still running, to avoid ending my turn idle. It only loads instructions; the session itself ran at Step 3.
4. **No emoji markers in the rounds** (note 12).
5. **Asked two questions outside the seed list:** Q4 (needs clarification) and Q5 (unraised defects), per notes 13 and 8.
6. **Prototyped the fixes in `<tmp>` during Step 2 and again in Step 5.** Not prescribed in plan-only mode. Done so the `Agree with modification` put to the user was a remedy that works, and so each accepted test-gap finding was applied with tests shown to kill the reviewer's mutants.
7. **Adjudicated all findings in the main loop** rather than fanning out. Skill: "split more into disjoint batches of three to five ... one adjudication subagent per batch." 8 distinct findings is over "about five". Every finding was checkable with one scratch script (run the head code, run four mutants) or by reading my own plan, so two more subagents at 40-80k tokens each would have re-derived what the reviewers had already demonstrated.
8. **Added an eighth plan section**, "Plan review (Step 5)" (note 16).
9. **Removed `<tmp>` in plan-only mode** (note 23).
10. **`report.md` was not saved.** The harness refused the Write call for it ("Subagents should return findings as text, not write report files. Include this content in your final response instead."). I did not route around the refusal with another tool; the Step 8 report text is in my final message to the caller instead. This is an environment limit, not a skill issue.
11. **The user's rounds were written to `rounds.md` and answered by the simulated user** (sandbox rule 4) instead of waiting for a person.
