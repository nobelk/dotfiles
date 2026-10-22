---
name: codex-review
description: Reviews the repository's changed files with codex (OpenAI Codex CLI), adjudicates every finding against the actual code and project rules (accept / reject / defer with evidence), fixes the ones that hold up, and verifies with the project's own gates. Scope is auto-detected (uncommitted changes, else the branch delta against the default branch). Use before committing or opening a PR when a second-model code review is wanted.
---

# Codex review skill

Get an independent code review of this repository's changed files from codex, then act on it the disciplined way: **validate every finding before touching code** — codex's comments are hypotheses to adjudicate, not instructions to follow. Output is the raw codex review, a per-finding disposition table (accept / reject / defer, each with evidence), the fixes for accepted findings, and a green verification run.

If the repo has a `CLAUDE.md`, read it first — it is authoritative for conventions, layering rules, and testing expectations, and it wins over any codex suggestion that contradicts it.

## Subagent delegation

Run the expensive, self-contained steps in a **`general-purpose` subagent** (via the `Agent` tool), and keep orchestration in the main loop. The split is fixed:

- **Main loop owns** (never delegate): the scope decision in Step 0, every `AskUserQuestion` gate (Step 0 scope tie-break, Step 4 ambiguous/invasive fix, Step 5 pre-existing red), the Step 2 fallback decision, presenting the disposition table, and the Step 6 final report. Subagents cannot prompt the user — anything that might stop-and-ask stays here.
- **Delegate to a `general-purpose` subagent** (each returns a compact result, keeping verbose output out of the main context):
  - **Step 2** — launch the codex review through the companion script, wait for it **under the deadline and liveness rules in Step 2** (on breach, cancel and report back so the main loop runs the native adversarial fallback), fetch the result, and return the raw findings verbatim (also written to the scratch file). The lengthy codex transcript stays in the subagent. Because the native fallback fans out subagents the main loop owns, the *decision* to fall back returns to the main loop rather than firing inside this subagent.
  - **Step 3** — split the findings into disjoint batches (~3–5 each; contradictory findings share a batch so one subagent resolves the conflict) and launch one adjudication subagent per batch **in a single message**, each getting the Step 1 project rules and adjudicating its findings against the actual code, returning its slice of the accept/reject/defer disposition table with file/line evidence. The main loop merges the slices, reviews the table, and owns any follow-up question.
  - **Step 4** — after the main loop has cleared every ambiguous/invasive finding via `AskUserQuestion`, dispatch a subagent to apply the remaining accepted fixes and return a summary mapped to finding numbers.
  - **Step 5** — run the project's verification gate (`task ci`, etc.) and return pass/fail plus only the failing output.

Give each subagent a self-contained prompt: the exact command(s) to run, the file list/scope from Step 0, and the precise shape of the result to return.

**Parallelize by default.** When delegated tasks have no data dependency, dispatch them as multiple `Agent` calls in a **single message** so they run concurrently — never run independent subagents one at a time across turns. Here the core path **is** a chain (Step 2 → 3 → 4 → 5: findings feed adjudication feeds fixes feed verification), so the steps stay sequential — though within Step 3 the adjudication batches fan out in parallel — and the genuinely independent work runs in parallel:
- **Launch codex FIRST, then overlap.** The Step 2 launch has **no data dependency on Step 1**: codex computes the diff itself. Fire the Step 2 launch subagent and the Step 1 rule-gathering subagents in the **same message**, and let codex run (typically 1–3 minutes) *while* you gather rules. Only Step 3 (adjudication) needs the findings in hand.
- **Step 1 rule-gathering** — fan the `CLAUDE.md` / ADR / sibling-code reads out across parallel reader subagents in one message; they share no state.
- **Step 2 union scope** (user chose both) — launch the working-tree and branch-delta reviews with distinct job tags (Step 2 job identity), each with its **own** scratch file, wait on both, then merge and dedupe by file:line in the main loop (details in Step 2).

## Step 0 — Determine the review scope (auto-detect)

If the invoking user or calling skill already named the scope (uncommitted, branch delta, or union) or a pinned base ref, use them as given: skip the question in step 3 below, and use the named base instead of resolving one in step 2. Otherwise "new and modified files" resolves in this order:

1. Collect **uncommitted changes**: staged, unstaged, and untracked files.
   ```bash
   git status --porcelain
   ```
2. Resolve the default branch and collect the **branch delta**:
   ```bash
   git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null \
     || (git show-ref --verify --quiet refs/heads/main && echo main) \
     || (git show-ref --verify --quiet refs/heads/master && echo master)
   git diff --name-only <base>...HEAD
   ```
   `<base>` is a remote-tracking ref (`origin/main`) when `origin/HEAD` is set, else the local
   `main`/`master` fallback — both are valid refs for the `git diff`/`review` below. (Don't strip
   `origin/`: a bare `main` fails in clones that have no local default branch.)
3. Pick the scope:
   - Only uncommitted changes exist → review those.
   - Only a branch delta exists (clean tree) → review the branch delta.
   - **Both exist and the file sets differ** → use AskUserQuestion to ask the user which scope to review (uncommitted only, branch delta only, or the union). Do not guess.
   - Both exist with the same file set → review the union.
   - Neither exists → stop and tell the user there is nothing to review.

Filter out generated files, vendored code, and lockfiles unless the user or calling skill asks otherwise, and list what was filtered in the Step 6 report. Record the final file list — it is the contract for everything below.

## Step 1 — Gather the project's rules

While the Step 2 launch runs (see *Parallelize by default*), read in parallel whatever exists: `CLAUDE.md`, ADRs or specs relevant to the changed files, and the nearest existing code/tests in the touched packages. You need these to *validate* codex's findings in Step 3 — a finding that contradicts a documented project rule is rejected no matter how plausible it sounds.

## Step 2 — Run codex's native review over the chosen scope

The `/codex:*` entries are Claude Code slash commands with `disable-model-invocation: true`: neither this loop nor a subagent can call them, and they are not shell commands. Check `command -v codex`, then drive the companion script the plugin wraps, from the repo root:

```bash
# Resolve once (the version dir varies; sort -V so 1.0.10 beats 1.0.9), then substitute the path for <companion>:
ls -d ~/.claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs 2>/dev/null | sort -V | tail -1   # record the printed path as <companion>: shell variables do not persist between Bash calls

node "<companion>" review --background --scope working-tree   # scope = uncommitted changes; launch with run_in_background: true
node "<companion>" review --background --base <base>          # scope = branch delta;        launch with run_in_background: true
node "<companion>" status --json                 # the new job's id is in .running[] (kind review)
node "<companion>" status <job-id> --wait --timeout-ms 240000   # bounded 4-minute wait; repeat until finished
node "<companion>" status <job-id> --json        # status, pid, logFile for the liveness check
node "<companion>" result <job-id>               # the stored verdict and findings
node "<companion>" cancel <job-id>               # abandon a dead or stalled job
```

Pass each flag as its own argument, never one quoted string (the companion re-splits a single string with its own parser). The companion accepts `--background` but runs the review in the foreground; the Bash `run_in_background: true` flag is what detaches it; the job is recorded in the plugin's state, so the user's own `/codex:status` and `/codex:result` show it too. `review` is codex's native reviewer: it computes the diff itself and **accepts no custom focus text** (the companion rejects it), which is why the CLAUDE.md-conventions check lives in the Step 3 adjudication. A tailored prompt needs `adversarial-review`, which is not this skill.

- **Deadline and liveness.** The companion has no internal timeout; a stalled review turn hangs the job indefinitely, and a job whose process died can keep saying `running`. Enforce a **10-minute** deadline for the whole review. Treat the job as **dead now** if its `pid` is not alive (`ps -p <pid>`) while status still says `running`, and as **stalled** if its `logFile` has been silent for **5+ minutes**. On death, stall, or deadline: run `cancel <job-id>` (it marks the job cancelled; do not hand-delete files under the plugin's state directory) and go straight to the native adversarial fallback below. Do not retry codex.
- **Unusable result.** A job that completes with an error, or whose result is absent or unreadable, counts as a failed review and takes the fallback. A review that completes and reports no findings is a passing review.
- **Job identity.** Give each launch its own tag: prefix the launch command with `CODEX_COMPANION_SESSION_ID=codex-review-<scope>-<random>` (the companion records it on the job), and find the job id with the same prefix on `CODEX_COMPANION_SESSION_ID=<tag> node "<companion>" status --json`, which then lists only that launch's job (in `running`, `latestFinished`, or `recent`). Do not match on `summary` or take "the newest job": the companion overwrites `summary` when a job finishes, and other reviews may share the workspace. If the tagged status shows no job, or more than one, treat it as a failed launch. Later `status <job-id>`, `result`, and `cancel` calls take the id and need no tag.
- **Union scope** (user chose both): launch both jobs with distinct tags, identify each by the rule above, wait on both job IDs, then merge the findings, deduping overlaps by file:line.
- **Save the output.** Capture each `result` verbatim to a scratch file named from the branch with `/` replaced by `-` (e.g. `"${TMPDIR:-/tmp}/codex-review-<branch>.md"`; add `-uncommitted` / `-base` for the union scope) so Step 3 is auditable. Do **not** commit it.
- If `codex` or the companion script is missing, or the launch fails outright (no job created), do not silently skip: tell the user, then apply the native adversarial fallback.

### Native adversarial fallback (when codex stalls, dies, or is unavailable)

Codex is the *second opinion*, never the critical path. When the liveness check fires, the result is unusable, or codex is unavailable, fall back to an in-loop review that has no external process and cannot stall:

- Fan out **2–3 adversarial `general-purpose` subagents in a single message**, each with a distinct lens over the exact Step 0 file list and the Step 1 project rules — e.g. **correctness/invariants**, **error-handling / silent-failure / fallback behavior**, and **test-coverage / edge cases**. Instruct each to cite `file:line` and to *verify* each claim against the actual code (no hypotheticals).
- If the session offers dedicated review agents (for example `pr-review-toolkit`'s `silent-failure-hunter`, `type-design-analyzer`, `pr-test-analyzer`), prefer the ones that fit the diff, dispatched concurrently.
- Feed the returned findings into Step 3 exactly as if they were codex's — the adjudication (accept/reject/defer with evidence) is identical; only the source changed. Note in the Step 6 report that the review came from the native fallback and why (codex absent / launch failed / dead pid / stalled / deadline / unusable result).

## Step 3 — Validate every codex finding (the load-bearing step)

Do **not** apply codex's comments blindly. For each numbered finding:

1. Open the actual code at the cited location and confirm the issue is real.
2. Check it against the project rules from Step 1.
3. Mark a disposition:
   - **accept** — real issue, fix is warranted; note the evidence.
   - **reject** — factually wrong, already handled elsewhere, or contradicts a documented project rule; note why with a file/line citation.
   - **defer** — real but out of scope for this change (pre-existing issue, needs an ADR, needs a wider refactor); note where it should go instead.

Scrutinize the classic external-reviewer failure modes: findings about code that doesn't exist (hallucinated lines), style opinions that contradict the repo's own conventions, suggestions to add dependencies the project's rules gate behind a decision record, and "fixes" that would break a documented invariant.

Present the full disposition table to the user before changing anything.

## Step 4 — Fix the accepted findings

Auto-fix every **accepted** finding, with two exceptions that require AskUserQuestion first:

- **Ambiguous findings** — more than one reasonable fix exists and they trade off differently (e.g. tighten an API vs. add validation at the call site). Ask which direction to take.
- **Invasive fixes** — the fix would touch files outside the review scope, change a public API, add a dependency, or exceed a small, local change. Ask before proceeding.

While fixing:
- Follow the project's own change workflow (tests first where behavior changes, minimal package-local edits, the repo's formatting/lint rules).
- One logical fix at a time; keep each traceable back to its finding number.
- Rejected and deferred findings get **no code changes** — they live only in the disposition table.

## Step 5 — Verify

Run the project's own gates over the result — whatever the repo defines (`task ci`, `make test`, `npm test`, etc.); prefer the full local CI target when one exists. Give each long-running gate an upper bound (`timeout -k 10 900 task ci`, `go test -timeout 600s`) so a hung test cannot stall the run. If any gate fails because of a fix, fix forward or revert the offending fix — never hand off red; a failure unrelated to the fixes is the pre-existing-red stop below.

## Step 6 — Final report

State, per the repo's handoff checklist if it has one:

- **Scope** — which files were reviewed and why that scope was chosen.
- **Codex findings** — total count and the disposition breakdown (accepted / rejected / deferred), with one-line reasons for each rejection.
- **What changed** — the fixes applied, mapped to finding numbers.
- **Which checks ran** and which were skipped and why.
- **Remaining risk** — deferred findings and anything the review could not cover.

## Stop-and-ask conditions (use AskUserQuestion; do not silently proceed)

- Both uncommitted changes and a branch delta exist with differing file sets (Step 0).
- An accepted finding's fix is ambiguous or invasive (Step 4).
- A verification gate fails for a reason unrelated to the fixes (pre-existing red) — ask whether to proceed, fix it, or stop.

Codex being unavailable, stalling, or erroring (Step 2) is not a stop: run the native adversarial fallback without asking and report it.
