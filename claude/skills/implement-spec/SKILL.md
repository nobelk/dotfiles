---
name: implement-spec
description: Implement a feature spec directory end to end as a principal software engineer. Takes a spec directory <spec-dir> (containing plan.md, requirements.md, validation.md). Reads the three spec files plus the repo's conventions, implements plan.md to satisfy requirements.md following the project's TDD/workflow rules, validates against validation.md, then runs the /simplify skill on the changed code, runs the /codex-review skill and folds in the findings that hold up, verifies with the project's format/lint/build/test gates, and finally commits and pushes the branch to remote. Invoke manually when a spec under specs/<name>/ is ready to build.
---

# Implement-spec skill

Take a finished planning spec and **build it to done**, acting as a principal software engineer: deliberate, test-first, minimal, and faithful to the repo's own rules. The input is a spec directory `<spec-dir>` holding the three feature-spec artifacts:

- `<spec-dir>/requirements.md` — what must be true (the contract).
- `<spec-dir>/plan.md` — the ordered task groups to implement.
- `<spec-dir>/validation.md` — how we prove it's done.

Output is working, reviewed, verified code committed and pushed to the remote branch. The skill composes two existing skills rather than reinventing them: `/simplify` for the cleanup pass and `/codex-review` for the independent second-model review.

If the repo has a `CLAUDE.md`, read it first and treat it as authoritative — its conventions, layering rules, and testing expectations win over anything in this skill or any reviewer suggestion that contradicts it.

## Principal-engineer posture

This is the bar for every step below — not decoration:

- **Faithful to the spec, skeptical of it.** Implement what `requirements.md` actually asks. If the plan and the requirements disagree, or either contradicts the repo's documented constraints, stop and surface it — do not paper over it in code.
- **Test-first.** Where the project mandates TDD, write the failing test that fails for the right reason before the implementation. Behavior changes ship with tests in the same change.
- **Minimal and local.** Smallest change that satisfies the requirement; extend the package that owns the concern; no speculative abstraction, no scope creep beyond `plan.md`.
- **Safety and correctness over convenience** when the domain is safety-critical — follow the repo's failure-direction and error-handling rules exactly.

## Subagent delegation

Run expensive, self-contained work in a **`general-purpose` subagent** (via the `Agent`/`Task` tool) and keep orchestration in the main loop. The split is fixed:

- **Main loop owns** (never delegate):
  - Every `AskUserQuestion` gate (subagents cannot prompt the user): missing/invalid spec files (Step 0), a spec-vs-requirements contradiction (Step 2), an ambiguous implementation fork (Step 3), a failing gate unrelated to the change (Step 5), and the pre-push confirmation (Step 7).
  - **Invoking the `/simplify` and `/codex-review` skills** (Step 4 and Step 5) — the Skill tool runs in this conversation; it cannot be launched from inside a subagent.
  - The implementation edits themselves stay in the main loop when they are tightly coupled across files (the common case for a coherent feature); delegate only a self-contained, well-bounded task group.
  - The final commit/push (Step 7) and the Step 8 report.
- **Delegate to a `general-purpose` subagent** (each returns a compact result):
  - **Step 1** — read the spec trio, `CLAUDE.md`, the nearest existing package code/tests, and any ADRs the plan references; return a structured brief (relevant conventions, the files each task group will touch, the test patterns to mirror). Keeps the bulky reading out of the main context.
  - **Step 5 verification** — run the project's gate (`task ci`, etc.) and return pass/fail plus only the failing output.

Give each subagent a self-contained prompt: the exact spec paths, the commands to run, and the precise result shape to return.

## Step 0 — Resolve and validate the spec directory

The skill's argument is `<spec-dir>` (e.g. `specs/APP-731`).

- If no argument is given, infer it from the current branch: a branch `specs/<name>` maps to spec dir `specs/<name>`. If you cannot infer a single unambiguous directory, stop and ask which spec to implement — do not guess.
- Confirm `<spec-dir>` exists and contains all three of `requirements.md`, `plan.md`, `validation.md`. If any is missing, stop and tell the user which — an incomplete spec is not implementable. Offer to run `/feature-spec` first.
- Run `git status --short`. If the working tree carries unrelated uncommitted changes, stop and ask how to proceed (commit/stash/abort) — don't fold someone else's work into this change.
- Confirm you are on a feature branch, not the default branch. Resolve the default branch:
  ```bash
  git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null \
    || (git show-ref --verify --quiet refs/heads/main && echo main) \
    || (git show-ref --verify --quiet refs/heads/master && echo master)
  ```
  If `HEAD` is on that default branch, stop and ask the user to name (or let you create) a feature branch before implementing — this skill ends by pushing, and pushing straight to the default branch is almost never intended.

## Step 1 — Build the implementation brief (subagent)

Delegate a read-only pass that returns everything needed to implement without re-reading mid-flight:

- Read `<spec-dir>/requirements.md`, `<spec-dir>/plan.md`, `<spec-dir>/validation.md` in full.
- Read `CLAUDE.md` and any ADRs / sibling specs the plan cites.
- For each task group in `plan.md`, identify the package(s) and files it will touch and the nearest existing code and test patterns to mirror.

The subagent returns: the ordered task-group list, the per-group target files, the conventions that bind (layering rules, TDD requirement, logging/observability gates, safety rules), and the validation criteria from `validation.md` restated as a checklist. The main loop holds this brief as the plan of record.

## Step 2 — Reconcile spec, plan, and repo rules before writing code

With the brief in hand, sanity-check it as a principal engineer would:

- Does `plan.md` actually cover every requirement in `requirements.md`? Note gaps.
- Does any task group conflict with a documented constraint (layering, dependency policy, safety direction)? 
- Are the `validation.md` criteria sufficient to prove the requirements, and are they testable as written?

If you find a genuine contradiction or a requirement the plan does not cover, **stop and surface it via `AskUserQuestion`** before writing code — offer the options you see (e.g. follow the plan, follow the requirement, adjust scope). Implementing through a known contradiction is the one thing a principal engineer does not do silently.

## Step 3 — Implement the plan, task group by task group

Work through `plan.md` in order (it is ordered so each group is independently coherent). For each group:

1. **Test first** where the project mandates TDD and the group changes behavior: write the failing test(s) that fail for the right reason, asserting against the `requirements.md`/`validation.md` contract. Verify they fail before implementing.
2. **Implement** the smallest change that makes the tests pass and satisfies the requirement. Stay inside the package that owns the concern; obey the layering/import rules from the brief.
3. **Refactor** locally once green. Add godoc/contract docs the repo requires on new exported identifiers.
4. Run the touched package's tests (e.g. `go test ./that/pkg -race -count=1`, or the repo's equivalent) before moving on, so you never stack a second group on a red first one.

When a single implementation choice is genuinely ambiguous and the alternatives trade off (an API shape, sync vs async, where a seam goes), stop and ask via `AskUserQuestion` rather than guessing — but only for real forks, not routine decisions a principal engineer just makes.

Keep edits minimal and traceable to a task group. Do not implement beyond `plan.md`'s scope; note any out-of-scope idea for later instead of building it.

## Step 4 — Simplify the changed code (`/simplify`)

Once the implementation is functionally complete and the touched-package tests pass, invoke the **`/simplify`** skill (via the Skill tool, in the main loop) to clean up the new and modified code for reuse, simplification, efficiency, and altitude. `/simplify` is a quality pass only — it does not hunt for bugs (that's the next step) — so it applies its cleanups directly to the working tree. Let it finish before reviewing.

## Step 5 — Independent review (`/codex-review`) and verify

1. Invoke the **`/codex-review`** skill (via the Skill tool, in the main loop). It auto-detects the scope (your uncommitted changes), runs codex's independent review, and — by its own contract — **validates every finding against the actual code and the project rules**, marking each accept/reject/defer, fixing only the accepted ones, and running the repo's gate at the end. Do not blindly apply codex output; that adjudication is exactly what `/codex-review` is built to do, so let it do it and review its disposition table.
   - If `/codex-review` reports that codex is unavailable or errored, follow its own stop-and-ask path; do not silently skip the review.
2. After `/codex-review` returns, run the project's **format, lint, build, and full test** gates yourself to confirm the combined result (implementation + simplify + review fixes) is green — prefer the repo's single full-CI target, in priority order:
   ```bash
   task ci          # if Taskfile.yml defines it (this repo: lint + test + test:sim + build + arch-lint)
   make ci / make test
   npm test / pnpm test / yarn test
   ```
   Delegate the gate run to a subagent that returns pass/fail plus only the failing output. If a gate fails because of the change, fix forward (looping back through the relevant step) — never hand off or commit red. If it fails for a reason unrelated to the change (pre-existing red), stop and ask whether to proceed, fix it, or abort.

## Step 6 — Confirm the validation criteria are met

Re-read `<spec-dir>/validation.md` and walk its checklist against what now exists: each named test present and passing, each metric/behavior demonstrable, the "done when" signal actually green. If any criterion is unmet, the spec is not done — return to Step 3 for the gap. Only proceed to commit when every validation criterion is satisfied (or the user has explicitly accepted a documented deferral).

## Step 7 — Commit and push

With everything green and validation satisfied:

1. Review the staged diff (`git status` + `git diff`) so the commit contains exactly the intended change and nothing stray.
2. Commit following the **repo's own commit conventions** — match the recent `git log` message style (this repo prefixes subjects with the ticket key, e.g. `APP-731: <summary>`) and include any required trailers defined by the environment/repo. Group into one or more logical commits if the plan landed as distinct slices.
3. Confirm the push target with `AskUserQuestion` if there is any ambiguity (new branch with no upstream, a protected branch, a fork remote). Then push:
   ```bash
   git push -u origin <current-branch>   # first push sets upstream
   ```
   Do not push to the default branch. Do not open a PR unless the user asks — pushing the branch is where this skill stops.

## Step 8 — Report

State, per the repo's handoff checklist if it has one:

- **What changed** — the task groups implemented, in the user's terms, and the files touched.
- **Spec coverage** — each `requirements.md` requirement and `validation.md` criterion, marked satisfied / deferred (with reason).
- **Simplify** — what `/simplify` cleaned up.
- **Review** — `/codex-review`'s finding count and accept/reject/defer breakdown, with one-line reasons for rejections.
- **Checks** — which gates ran (format/lint/build/test) and any skipped, with why.
- **Commit & push** — the commit(s) and the branch pushed.
- **Remaining risk** — deferred items and anything review/validation could not cover, especially around safety, ordering, concurrency, performance, or architecture boundaries.

## Stop-and-ask conditions (use AskUserQuestion; never silently proceed)

- `<spec-dir>` is missing or lacks any of the three spec files (Step 0).
- The working tree carries unrelated changes, or `HEAD` is on the default branch (Step 0).
- `plan.md`/`requirements.md` contradict each other or a documented repo constraint (Step 2).
- A real implementation fork with trade-offs (Step 3).
- `/codex-review` reports codex is unavailable (Step 5, defer to that skill's own gate).
- A verification gate fails for a pre-existing reason unrelated to the change (Step 5).
- Any ambiguity about the push target (Step 7).
