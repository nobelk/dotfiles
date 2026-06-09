---
name: improve-coverage
description: Measure unit-test coverage of the current branch's changed Go packages, draft a CLAUDE.md-compliant plan to raise it, have codex review the plan, then implement and verify the improvement. Computes coverage from git diff main...HEAD (branch-changed packages only), writes a plan, runs `codex exec` to review it, validates and addresses the review, then formats/lints/builds/tests and confirms coverage rose significantly. Invoke manually when you want to harden test coverage on a feature branch before merge.
---

# Improve coverage skill

Raise unit-test coverage on the **packages this branch changed**, the disciplined way: measure first, plan against the project's own rules, get an independent (codex) review of that plan, validate the review, then implement and prove the lift. Output is a coverage report, a written plan, new tests, and a green verification run.

This skill follows the repo's TDD and hexagonal-discipline rules — read `CLAUDE.md` before doing anything; it overrides any default behavior here.

## Subagent delegation

Run the expensive, self-contained steps in a **`general-purpose` subagent** (via the `Agent`/`Task` tool), and keep orchestration in the main loop. The split is fixed:

- **Main loop owns** (never delegate): the Step 0 scope resolution, every stop-and-ask gate (Step 0 branch==base, zero changed files; the codex-unavailable gate), drafting the plan in Step 3, presenting baseline numbers and dispositions, and the Step 8 final checklist. Subagents cannot prompt the user, so the gates stay here.
- **Delegate to a `general-purpose` subagent** (each returns a compact result, keeping verbose `go test` / coverage output out of the main context):
  - **Step 1** — run the `go test … -coverprofile` + `go tool cover -func` commands over the target packages and return the per-package and total percentages plus the lowest-covered rows. The full profile output stays in the subagent.
  - **Step 4** — run the `codex exec` plan review and return the raw findings verbatim (also written to the review scratch file).
  - **Step 5** — hand the findings plus CLAUDE.md and the real source/tests to a subagent that adjudicates each and returns the accept/reject/defer table. The main loop rewrites `coverage-plan.md` from the accepted dispositions.
  - **Step 6** — dispatch a subagent to implement the planned tests for a target package (one subagent per package keeps each focused), following CLAUDE.md exactly, returning a summary of tests added and any minimal port extraction made. Re-running arch-lint after a port extraction belongs in Step 7's gate.
  - **Step 7** — run `task fmt/lint/build/test` (or `task ci`) and the after-coverage re-measure, returning gate pass/fail plus the before→after numbers and any `task mutation` survivors.

Give each subagent a self-contained prompt: the exact commands, the target-package list from Step 0, the relevant CLAUDE.md rules, and the precise result shape to return.

## Step 0 — Establish the baseline scope (changed packages)

The phrase "coverage of the current branch" means the Go packages touched relative to the default branch — not the whole module.

1. Resolve the default branch:
   ```bash
   git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's@^origin/@@' \
     || (git show-ref --verify --quiet refs/heads/main && echo main) \
     || (git show-ref --verify --quiet refs/heads/master && echo master)
   ```
   Call the result `<base>`. Record the current branch with `git branch --show-current`.
2. If the current branch *is* `<base>`, stop and ask the user which packages to target — there is no branch delta to scope from.
3. Compute the changed Go files and map them to packages:
   ```bash
   git diff --name-only <base>...HEAD -- '*.go' | grep -v '_test\.go$'
   ```
   Reduce each path to its directory, dedupe, and drop directories that hold no non-test `.go` files. These directories are the **target packages** (`./internal/domain`, `./internal/adapters/...`, etc.).
   - Note `_test.go`-only changes separately — they affect coverage but add no production lines to cover.
   - If the delta touches zero production `.go` files, stop and tell the user there is nothing to measure; offer to fall back to whole-module `task cover`.

## Step 1 — Measure current coverage (the "before" number)

Run the project's own coverage target so local and the report agree:
```bash
go test <target-packages> -race -count=1 -coverprofile=coverage.before.out
go tool cover -func=coverage.before.out
```
- Use the explicit target-package list from Step 0, not `./...` — the report must be branch-scoped. Naming each package explicitly is deliberate: a changed package with **no test file** still reports `0.0%` (Go emits a profile row for any package named in the arg list), which is exactly the gap this skill exists to catch. Do **not** switch to `-coverpkg` to "fix" this — `-coverpkg` drops un-imported packages from the profile and would hide that 0% package.
- This measures **in-package self-coverage**: a package's own `_test.go` files covering its own statements. It does *not* credit a changed package for being exercised by a *sibling* package's tests. If a target package is intentionally covered by a consumer/helper package's tests (e.g. a port exercised via `portstest` or a consumer), its self-coverage number will read low — note this rather than chasing it, and only for that package re-measure with `go test ./... -coverpkg=<that-package> -coverprofile=...` to see whole-suite attribution. State which semantic each number is.
- Capture the **per-package** and **total** statement-coverage percentages from the `cover -func` tail. This total is the baseline you must beat.
- If any target package fails to compile or test, fix nothing yet — record it; a red package is itself a coverage finding for the plan.
- Identify the lowest-covered functions/files (the `cover -func` rows below the target) — these are the plan's raw material.

Report the baseline to the user before planning: per-package %, total %, and the largest uncovered gaps.

## Step 2 — Read the project's rules (CLAUDE.md + constitution/specs)

Before drafting the plan, read — in parallel — whatever exists:
- `CLAUDE.md` — **authoritative**. Pay special attention to "Testing expectations" (the six qualities: hermetic, deterministic, fast, boundary-driven, mock-at-the-port, diagnostic-on-failure), the project-specific test rules (safety-critical paths, regression tests, benchmarks), and the architecture layering rules.
- A constitution file if present (`constitution.md`, `CONSTITUTION.md`, `specs/constitution.md`, or `.specify/memory/constitution.md`). If none exists, the constitution role is filled by `CLAUDE.md` + `specs/adr/*` + `specs/mission.md` — say so explicitly rather than inventing one.
- `specs/adr/` ADRs relevant to the target packages, and the nearest existing `_test.go` files in those packages (match their patterns: `uber-go/mock` doubles, table-driven boundary cases, `t.Parallel()`).

The plan's test designs must conform to these. A plan that proposes `time.Now()` in a test, or a hand-written fake where the repo uses generated mocks, is wrong on its face — the rules win.

## Step 3 — Draft the coverage-improvement plan

Write the plan to `specs/<branch>/coverage-plan.md` (create the dir if absent; `<branch>` is the current branch name). If a `specs/<branch>/` already exists, add the file alongside the existing plan docs.

The plan must contain:
1. **Baseline** — the per-package and total coverage numbers from Step 1, plus the dated target (e.g. "raise `internal/domain` from 61% → ≥85% statement coverage").
2. **Gap inventory** — a table of uncovered or under-covered functions, each tagged with the boundary classes (from CLAUDE.md's boundary-driven list) it currently misses: happy / zero-empty-nil / singleton / max-overflow / invalid / cancellation-deadline / concurrency.
3. **Test designs** — for each gap, the specific test cases to add, named after the boundary they exercise (`"empty_input"`, `"ctx_cancelled_mid_call"`), the port/mock to use, and any new `Clock`/port extraction the test forces in production code.
4. **Safety-critical callout** — if any target package is on a safety-critical path (commands, ownership, consist propagation), note that mutation testing (`task mutation`) is required before merge, not just line coverage.
5. **Non-goals** — what this pass deliberately leaves uncovered and why (e.g. integration-only paths behind build tags).

Keep it concrete and minimal — it is a work list, not an essay. Do not embed Jira keys or issue numbers (CLAUDE.md forbids ticket IDs in the tree; this file is in the tree).

## Step 4 — Have codex review the plan (non-interactive)

Run codex headless over the plan to get an independent critique:
```bash
codex exec "Review the unit-test coverage-improvement plan in specs/<branch>/coverage-plan.md against the testing rules in CLAUDE.md (the six test qualities, boundary-driven coverage, mock-at-the-port, safety-critical mutation testing) and the hexagonal layering rules. List concrete gaps, weak test designs, missed boundary cases, any proposed test that would violate hermeticity/determinism, and any production change the plan implies but omits. Be specific and cite file/function names. Do not rewrite the plan; output a numbered list of findings."
```
- Run it from the repo root so codex sees the files. If `codex exec` needs approval flags in this environment, prefer its read-only/non-interactive mode and capture stdout.
- If `codex` is unavailable or errors, do not silently skip: tell the user codex review failed, and offer to substitute a second-pass self-review or another reviewer before continuing.
- Save codex's raw findings (e.g. to `specs/<branch>/coverage-plan.codex-review.md`) so the validation in Step 5 is auditable.

## Step 5 — Validate codex's findings, then update the plan

Do **not** apply codex's comments blindly — validate each one against the actual code and CLAUDE.md:
- For every finding, check it against the real source/tests and the rules. Mark each: **accept** (real gap — fold the fix into the plan), **reject** (incorrect or contradicts CLAUDE.md — note why), or **defer** (valid but out of scope — move to Non-goals).
- Common codex misses to scrutinize: suggestions that add a third-party assertion lib (check ADRs first), proposals to test unexported internals directly (CLAUDE.md says mock at the port, never below), or "increase coverage" advice that would test the standard library or the type under test.
- Rewrite `coverage-plan.md` incorporating the accepted findings. Record the accept/reject/defer dispositions briefly so the reasoning is traceable.

Present the validated dispositions to the user before implementing.

## Step 6 — Implement the tests (TDD, package-local)

Work through the updated plan, one target package at a time, following CLAUDE.md exactly:
- Write failing tests first; assert before implementing so each fails for the right reason.
- Table-driven, `t.Parallel()` on every leaf/subtest, generated `uber-go/mock` doubles at the port boundary, no wall-clock reads (inject a `Clock`), `cmp.Diff` for structs, diagnostic `want=/got=` failure messages.
- If a gap is unreachable without a production change (e.g. an un-extractable clock or an untestable concrete dependency), make the **minimal** port extraction the plan named — and re-verify arch-lint still passes.
- For any bug a new test uncovers, add a regression test that fails on `HEAD~1` and passes on the fix (CLAUDE.md regression rule).
- Run `gofmt` and the touched package's tests while iterating; keep changes minimal and package-local.

## Step 7 — Format, lint, build, test, and verify the lift

Run the project's gates and re-measure:
```bash
task fmt
task lint
task build
task test
go test <target-packages> -race -count=1 -coverprofile=coverage.after.out
go tool cover -func=coverage.after.out
```
- Prefer `task ci` for the full gate (lint + test + build + arch-lint) unless the user asked to skip it.
- Compare `coverage.after.out` total against the Step 1 baseline. "Significantly increased" means a material, named jump (state the before → after per package and total). If the lift is marginal, say so honestly and propose the next gap rather than declaring success.
- For safety-critical packages, run `task mutation` and report surviving mutants — line coverage alone does not clear a safety path.
- Clean up scratch coverage files (`coverage.before.out`, `coverage.after.out`) unless the user wants them kept; never commit them.

## Step 8 — Final response checklist (per CLAUDE.md)

Before handoff, state:
- **What changed** — packages, tests added, any production port extraction, before → after coverage per package and total.
- **Which checks ran** — `task fmt/lint/build/test`, `task ci`, `task mutation` (if safety-critical), and the codex review.
- **Which checks were skipped and why.**
- **Remaining risk** — uncovered paths left in Non-goals, surviving mutants, or any boundary class still unaddressed, especially around safety, ordering, concurrency, or architecture boundaries.

## Stop-and-ask conditions (do not silently proceed)

- Current branch equals the default branch (no delta to scope).
- Zero production `.go` files changed.
- A target package will not compile or its tests are red before you start.
- `codex` is unavailable or its review fails.
- A planned test cannot be written without a production change larger than a minimal port extraction.
