---
name: codex-review
description: Code-review the new and modified files in the current repository by running codex (OpenAI Codex CLI) headlessly, then validate every codex finding against the actual code and project rules, and fix the ones that hold up. Auto-detects scope (uncommitted changes if any, else the branch delta vs the default branch), runs `codex exec` for an independent review, marks each finding accept/reject/defer with evidence, auto-fixes accepted findings, and verifies with the project's own gates. Invoke manually before committing or opening a PR when you want a second-model review of your changes.
---

# Codex review skill

Get an independent code review of this repository's changed files from codex, then act on it the disciplined way: **validate every finding before touching code** — codex's comments are hypotheses to adjudicate, not instructions to follow. Output is the raw codex review, a per-finding disposition table (accept / reject / defer, each with evidence), the fixes for accepted findings, and a green verification run.

If the repo has a `CLAUDE.md`, read it first — it is authoritative for conventions, layering rules, and testing expectations, and it wins over any codex suggestion that contradicts it.

## Step 0 — Determine the review scope (auto-detect)

"New and modified files" resolves in this order:

1. Collect **uncommitted changes**: staged, unstaged, and untracked files.
   ```bash
   git status --porcelain
   ```
2. Resolve the default branch and collect the **branch delta**:
   ```bash
   git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's@^origin/@@' \
     || (git show-ref --verify --quiet refs/heads/main && echo main) \
     || (git show-ref --verify --quiet refs/heads/master && echo master)
   git diff --name-only <base>...HEAD
   ```
3. Pick the scope:
   - Only uncommitted changes exist → review those.
   - Only a branch delta exists (clean tree) → review the branch delta.
   - **Both exist and the file sets differ** → use AskUserQuestion to ask the user which scope to review (uncommitted only, branch delta only, or the union). Do not guess.
   - Neither exists → stop and tell the user there is nothing to review.

Filter out generated files, vendored code, and lockfiles unless the user asks otherwise. Record the final file list — it is the contract for everything below.

## Step 1 — Gather the project's rules

Before invoking codex, read (in parallel) whatever exists: `CLAUDE.md`, ADRs or specs relevant to the changed files, and the nearest existing code/tests in the touched packages. You need these to *validate* codex's findings in Step 3 — a finding that contradicts a documented project rule is rejected no matter how plausible it sounds.

## Step 2 — Run codex's review headlessly over the chosen scope

Use codex's purpose-built review mode from the repo root — it computes the diff itself, so pass only the scope flag matching Step 0:

```bash
# Scope = uncommitted changes:
codex exec review --uncommitted "<instructions>"
# Scope = branch delta:
codex exec review --base <base> "<instructions>"
```

With `<instructions>`:

> Review for: correctness bugs, error-handling gaps, concurrency hazards, security issues, violations of the conventions in CLAUDE.md (if present), missing or weak tests, and API-contract problems. For each finding output a numbered item with: file:line, severity (high/medium/low), the issue, and the suggested fix. Be specific — cite the actual code. Output findings only.

- For the "union" scope (user chose both), run both commands and merge the findings, deduping overlaps by file:line.
- Capture stdout verbatim and save it to a scratch file (e.g. `/tmp/codex-review-<branch>.md`) so Step 3 is auditable. Do **not** commit this file.
- Verify these flags against `codex exec review --help` if the command errors — the CLI evolves; fall back to plain `codex exec --sandbox read-only "<instructions plus explicit file list>"` if the review subcommand is unavailable in the installed version.
- If `codex` is not installed or the command errors even on fallback, do not silently skip: tell the user codex review failed, and use AskUserQuestion to offer alternatives (retry, substitute a self-review pass, or abort).

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
- `codex` is unavailable or its review errors (Step 2).
- An accepted finding's fix is ambiguous or invasive (Step 4).
- A verification gate fails for a reason unrelated to the fixes (pre-existing red) — ask whether to proceed, fix it, or stop.
