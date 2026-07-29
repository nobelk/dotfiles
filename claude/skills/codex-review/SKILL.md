---
name: codex-review
description: Code-review the repository's changed files by running codex (OpenAI Codex CLI) through the `/codex:review --background` flow, adjudicating every finding against the actual code and project rules (accept / reject / defer with evidence), fixing the ones that hold up, and verifying with the project's own gates. Auto-detects scope — uncommitted changes if any, else the branch delta vs the default branch. Invoke manually before committing or opening a PR when you want a second-model review of your changes.
---

# Codex review skill

Get an independent code review of this repository's changed files from codex, then act on it the disciplined way: **validate every finding before touching code** — codex's comments are hypotheses to adjudicate, not instructions to follow. Output is the raw codex review, a per-finding disposition table (accept / reject / defer, each with evidence), the fixes for accepted findings, and a green verification run.

If the repo has a `CLAUDE.md`, read it first — it is authoritative for conventions, layering rules, and testing expectations, and it wins over any codex suggestion that contradicts it.

## Subagent delegation

Run the expensive, self-contained steps in a **`general-purpose` subagent** (via the `Agent`/`Task` tool), and keep orchestration in the main loop. The split is fixed:

- **Main loop owns** (never delegate): the scope decision in Step 0, every `AskUserQuestion` gate (Step 0 scope tie-break, Step 2 codex-unavailable, Step 4 ambiguous/invasive fix), presenting the disposition table, and the Step 6 final report. Subagents cannot prompt the user — anything that might stop-and-ask stays here.
- **Delegate to a `general-purpose` subagent** (each returns a compact result, keeping verbose output out of the main context):
  - **Step 2** — launch the `/codex:review --background` review, poll `/codex:status` to completion **under the 10-minute deadline / dead-pid / 5-minute-silence liveness rules defined in Step 2** (on breach, cancel and signal the main loop to run the native adversarial fallback — no fast-model retry), fetch `/codex:result <job-id>`, and return the raw findings verbatim (also written to the scratch file). The lengthy codex transcript stays in the subagent. Because the native fallback fans out subagents the main loop owns, the *decision* to fall back returns to the main loop rather than firing inside this subagent.
  - **Step 3** — split the findings into disjoint batches (~3–5 each; contradictory findings share a batch so one subagent resolves the conflict) and launch one adjudication subagent per batch **in a single message**, each getting the Step 1 project rules and adjudicating its findings against the actual code, returning its slice of the accept/reject/defer disposition table with file/line evidence. The main loop merges the slices, reviews the table, and owns any follow-up question.
  - **Step 4** — after the main loop has cleared every ambiguous/invasive finding via `AskUserQuestion`, dispatch a subagent to apply the remaining accepted fixes and return a summary mapped to finding numbers.
  - **Step 5** — run the project's verification gate (`task ci`, etc.) and return pass/fail plus only the failing output.

Give each subagent a self-contained prompt: the exact command(s) to run, the file list/scope from Step 0, and the precise shape of the result to return.

**Parallelize by default.** When delegated tasks have no data dependency, dispatch them as multiple `Agent`/`Task` calls in a **single message** so they run concurrently — never run independent subagents one at a time across turns. Here the core path **is** a chain (Step 2 → 3 → 4 → 5: findings feed adjudication feeds fixes feed verification), so the steps stay sequential — though within Step 3 the adjudication batches fan out in parallel — and the genuinely independent work runs in parallel:
- **Launch codex FIRST, then overlap — the review must never be idle wall-clock.** The Step 2 launch has **no data dependency on Step 1**: codex computes the diff itself. So fire the Step 2 launch subagent and the Step 1 rule-gathering subagents in the **same message**, and let codex run (steady-state 1–3 min; the model fix in `~/.codex/config.toml`'s `review_model` keeps it there) *while* you gather rules. Never gather rules first and then start codex — that serializes two things that should overlap. When this skill is reached from `implement-spec` (or any flow where implementation just finished), launch the review the instant the code is written, then do the changelog/doc/self-review wrap-up while codex runs, and collect `/codex:result` at the end — a 2–3 min review overlapped with other work costs ≈0 wall-clock. Only Step 3 (adjudication) actually needs the findings in hand.
- **Step 1 rule-gathering** — fan the `CLAUDE.md` / ADR / sibling-code reads out across parallel reader subagents in one message; they share no state.
- **Step 2 union scope** (user chose both) — run the `--uncommitted` and `--base` codex reviews as two subagents in the same message; they are independent. Give each a **distinct** scratch file (e.g. `/tmp/codex-review-<branch>-uncommitted.md` and `…-base.md`) so the parallel writes don't clobber one shared path, then merge and dedupe by file:line in the main loop afterward.

## Step 0 — Determine the review scope (auto-detect)

"New and modified files" resolves in this order:

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
   - Neither exists → stop and tell the user there is nothing to review.

Filter out generated files, vendored code, and lockfiles unless the user asks otherwise. Record the final file list — it is the contract for everything below.

## Step 1 — Gather the project's rules

Before invoking codex, read (in parallel) whatever exists: `CLAUDE.md`, ADRs or specs relevant to the changed files, and the nearest existing code/tests in the touched packages. You need these to *validate* codex's findings in Step 3 — a finding that contradicts a documented project rule is rejected no matter how plausible it sounds.

## Step 2 — Run codex's review via `/codex:review --background` over the chosen scope

Run codex's native review through the **`/codex:review --background`** flow from the repo root — it computes the diff itself, so pass only the scope flag matching Step 0. The `--background` mode detaches the run into a Claude background task; recover its output with `/codex:status` (progress) and `/codex:result <job-id>` (the stored findings):

```bash
# Scope = uncommitted changes (working tree):
/codex:review --background --scope working-tree
# Scope = branch delta:
/codex:review --background --base <base>
```

`/codex:review` is native-review only — it uses codex's built-in review prompt and **does not accept custom focus instructions** (that is why the CLAUDE.md-conventions check lives in the Step 3 adjudication, not in the review call). If a tailored review prompt is ever required, that is the `/codex:adversarial-review --background "<focus>"` sibling, not this skill.

Concretely, `/codex:review --background` launches the codex-companion runtime detached (`node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" review "--background --scope working-tree"` with `run_in_background: true`, where `${CLAUDE_PLUGIN_ROOT}` is the codex plugin root). Then:

- **Do not block the launching turn.** After launching, poll `/codex:status` until the job reports finished, then read `/codex:result <job-id>` for the verdict and findings. Only then proceed to Step 3.
- **Enforce a 10-minute deadline AND a mechanical liveness check.** The companion has no internal timeout — a stalled `review/start` turn hangs the job forever (observed: 3.5 min of activity, then 38 min of silence; and a job that died one minute in yet sat `status:"running"`, `updatedAt:null` with a dead `pid`, never reaped). Poll with `node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" status <job-id> --wait` (4-min bounded waits) and track elapsed time. Between polls, read the job's state file (`~/.claude/plugins/data/codex-openai-codex/state/<workspace>/jobs/<job-id>.json`) and treat the job as **dead now** — no waiting — if its `pid` is not alive (`ps -p <pid>`) while status still says `running`; treat it as **stalled** if its `logFile` mtime has been silent for **5+ minutes**. On death/stall/deadline: run `/codex:cancel <job-id>` (and, if it left a stale state file, remove that job's `.json`/`.log` so it doesn't masquerade as running later), then go straight to the native adversarial fallback below — do **not** burn time on the `gpt-5.4-mini` retry, which has itself stalled on large diffs.
- For the "union" scope (user chose both), launch **two** background jobs — one `--scope working-tree`, one `--base <base>` — in the same message, await both via their job IDs, then merge the findings, deduping overlaps by file:line.
- Capture the `/codex:result` output verbatim and save it to a scratch file (e.g. `/tmp/codex-review-<branch>.md`) so Step 3 is auditable. Do **not** commit this file.
- If `codex` is not installed or the launch itself fails outright (no job created), do not silently skip: tell the user, then apply the native adversarial fallback below.

### Native adversarial fallback (when codex stalls, dies, or is unavailable)

Codex is the *second opinion*, never the critical path. The moment the liveness check above fires — or codex is unavailable — **do not block the workflow waiting on it**. Fall back to an in-loop review that has no external process and cannot stall:

- Fan out **2–3 adversarial `general-purpose` subagents in a single message**, each with a distinct lens over the exact Step 0 file list and the Step 1 project rules — e.g. **correctness/invariants**, **error-handling / silent-failure / fallback behavior**, and **test-coverage / edge cases**. Instruct each to cite `file:line` and to *verify* each claim against the actual code (no hypotheticals).
- In a repo that ships review agents, prefer those over generic subagents: this project's `pr-review-toolkit` provides `silent-failure-hunter`, `type-design-analyzer`, and `pr-test-analyzer` — dispatch the ones that fit the diff, concurrently.
- Feed the returned findings into Step 3 exactly as if they were codex's — the adjudication (accept/reject/defer with evidence) is identical; only the source changed. Note in the Step 6 report that the review came from the native fallback and why (codex stalled/died/unavailable).

Use AskUserQuestion only if you need the user to choose between retrying codex and proceeding with the native fallback; otherwise proceed with the fallback and report it.

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

Run the project's own gates over the result — whatever the repo defines (`task ci`, `make test`, `npm test`, etc.); prefer the full local CI target when one exists. If any gate fails, fix forward or revert the offending fix — never hand off red.

## Step 6 — Final report

State, per the repo's handoff checklist if it has one:

- **Scope** — which files were reviewed and why that scope was chosen.
- **Codex findings** — total count and the disposition breakdown (accepted / rejected / deferred), with one-line reasons for each rejection.
- **What changed** — the fixes applied, mapped to finding numbers.
- **Which checks ran** and which were skipped and why.
- **Remaining risk** — deferred findings and anything the review could not cover.

## Stop-and-ask conditions (use AskUserQuestion; do not silently proceed)

- Both uncommitted changes and a branch delta exist with differing file sets (Step 0).
- `codex` is unavailable, stalls, or its review errors (Step 2) — proceed with the native adversarial fallback; ask only if the user should choose between retrying codex and falling back.
- An accepted finding's fix is ambiguous or invasive (Step 4).
- A verification gate fails for a reason unrelated to the fixes (pre-existing red) — ask whether to proceed, fix it, or stop.
