---
name: implement-spec
description: Implement a feature spec end to end as a principal software engineer — resolves the specs/<name> branch to its git worktree (reusing an existing worktree, else creating branch and worktree as needed) and works there, reads the spec trio plus the repo's conventions, implements plan.md test-first to satisfy requirements.md, validates against validation.md, runs the /simplify and /codex-review skills on the result, verifies with the project's gates, then commits and pushes the branch. Takes a spec directory containing plan.md, requirements.md, and validation.md as the argument (inferred from a specs/<name> branch if omitted). Invoke manually when a spec under specs/<name>/ is ready to build.
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
- **Test-first (TDD) whenever possible.** Write the failing test that fails for the right reason before the implementation - by default, not only where the project mandates it. Skip TDD only for changes with no testable behavior (docs; generated output whose generator inputs are what get tested), and name each skipped case and its reason in the Step 8 report. Behavior changes ship with tests in the same change, and tests meet the same clean-code bar as production code.
- **Clean code.** Small, single-purpose functions at one level of abstraction; intention-revealing names; no duplication *introduced by the change* - extract logic you would otherwise copy (deliberate test duplication that keeps a case readable is fine); comments only for the non-obvious *why*.
- **Clean architecture.** Preserve the repo's established dependency structure; where it defines layering rules, keep dependencies pointing inward, define interfaces at the consumer boundary, and keep domain logic free of transport/DB/framework concerns; new code lands in the package that owns the concern.
- **Standard design patterns.** Prefer well-known patterns (Ports & Adapters, Strategy, Repository, Functional Options, …) over bespoke abstractions - but only where an abstraction removes real duplication or isolates a dependency. Name the pattern in the report/PR so reviewers recognize it; never contort code identifiers or comments to carry the pattern name.
- **Idiomatic style.** Precedence: documented repo rules, then the surrounding code's established idiom, then the language community's conventions (Effective Go, PEP 8, …) - in production code and tests alike, without cleaning up unrelated legacy code.
- **Minimal and local.** Smallest change that satisfies the requirement; extend the package that owns the concern; no speculative abstraction, no scope creep beyond `plan.md`. If meeting a documented repo constraint would force a refactor wider than the plan's scope, stop and ask - neither creep the scope silently nor ship structure you know is wrong.
- **Safety and correctness over convenience** when the domain is safety-critical — follow the repo's failure-direction and error-handling rules exactly.

## Subagent delegation

Run expensive, self-contained work in a **`general-purpose` subagent** (via the `Agent`/`Task` tool) and keep orchestration in the main loop. The split is fixed:

- **Main loop owns** (never delegate):
  - Every `AskUserQuestion` gate (subagents cannot prompt the user): missing/invalid spec files (Step 0), a spec-vs-requirements contradiction (Step 2), an ambiguous implementation fork (Step 3), a failing gate unrelated to the change (Step 5), and the pre-push confirmation (Step 7).
  - **Invoking the `/simplify` and `/codex-review` skills** (Step 4 and Step 5) — the Skill tool runs in this conversation; it cannot be launched from inside a subagent.
  - The implementation edits themselves stay in the main loop when they are tightly coupled across files (the common case for a coherent feature); delegate only a self-contained, well-bounded task group - and give that subagent's prompt the principal-engineer posture standards, the TDD requirement, and the group's scope limits, with the result shape including the changed files and red-then-green test evidence.
  - The final commit/push (Step 7) and the Step 8 report.
- **Delegate to a `general-purpose` subagent** (each returns a compact result):
  - **Step 1** — read the spec trio, `CLAUDE.md`, the nearest existing package code/tests, and any ADRs the plan references; return a structured brief (relevant conventions, the files each task group will touch, the test patterns to mirror). Keeps the bulky reading out of the main context.
  - **Step 5 verification** — run the project's gate (`task ci`, etc.) and return pass/fail plus only the failing output.

Give each subagent a self-contained prompt: the exact spec paths, the commands to run, and the precise result shape to return.

**Parallelize by default.** When delegated tasks have no data dependency, dispatch them as multiple `Agent`/`Task` calls in a **single message** so they run concurrently — never run independent subagents one at a time across turns. Concretely: Step 1's reads (spec trio, `CLAUDE.md`, per-package code/tests, ADRs) are independent — fan them out as parallel reader subagents in one message. **Implementation itself stays serial**: Step 3 works through `plan.md` in order, running each group's tests before starting the next, because the ordered groups typically build on one another and can race through shared artifacts (lockfiles, codegen, migrations, golden files, public API surfaces) even when their source files look disjoint — do not parallelize task-group implementation. The `/simplify` and `/codex-review` invocations and the final verify are likewise sequential — each consumes the prior step's result.

## Step 0 — Resolve and validate the spec directory

The skill's argument is `<spec-dir>` (e.g. `specs/APP-731`).

- If no argument is given, infer it from the current branch: a branch `specs/<name>` maps to spec dir `specs/<name>`. If you cannot infer a single unambiguous directory, stop and ask which spec to implement — do not guess.
- Derive the feature branch from the spec dir: `<branch>` is `specs/<name>` for spec dir `specs/<name>`.
- **Worktree discovery** — run `git worktree list --porcelain` and look for a `branch refs/heads/<branch>` entry, then branch on what you find:
  - A worktree already has `<branch>` checked out → `cd` to that worktree's root and run **every** subsequent step from there — the reads, the implementation edits, the `/simplify` and `/codex-review` invocations, the gates, and the commit/push. (The Skill tool and the gates inherit the session's working directory, so this `cd` is load-bearing, not cosmetic.)
  - `<branch>` exists locally but no worktree has it → attach it: `git worktree add <wt-path> <branch>`, then `cd <wt-path>`.
  - `<branch>` does not exist → resolve the default branch:
    ```bash
    git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null \
      || (git show-ref --verify --quiet refs/heads/main && echo main) \
      || (git show-ref --verify --quiet refs/heads/master && echo master)
    ```
    and create the branch inside a fresh worktree: `git worktree add <wt-path> -b <branch> <base>`, then `cd <wt-path>`.

  `<wt-path>` follows the same convention as `/feature-spec`: `<repo-parent>/<repo-dirname>-worktrees/<slug>`, where `<slug>` is `<branch>` with `/` replaced by `-`; never nest a worktree inside the repo's own working tree. Working in the branch's dedicated worktree also guarantees `HEAD` is never the default branch — this skill ends by pushing, and pushing straight to the default branch is almost never intended.
- Confirm `<spec-dir>` exists **inside the worktree** and contains all three of `requirements.md`, `plan.md`, `validation.md`. If any is missing, stop and tell the user which — an incomplete spec is not implementable. Offer to run `/feature-spec` first.
- Run `git status --short` **in the worktree**. If it carries unrelated uncommitted changes (possible when reusing an existing worktree), stop and ask how to proceed (commit/stash/abort) — don't fold someone else's work into this change.

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

1. **Test first (TDD)** whenever the group changes behavior a test can express (per the posture): write the failing test(s) that fail for the right reason, asserting against the `requirements.md`/`validation.md` contract. Verify they fail before implementing - and that the failure is the new test, not a pre-existing red in the package. Follow the repo's test idioms (e.g. table-driven cases named for the boundary they exercise).
2. **Implement** the smallest change that makes the tests pass and satisfies the requirement. Stay inside the package that owns the concern; obey the layering/import rules from the brief.
3. **Refactor** locally once green, applying the posture's clean-code, pattern, and idiom standards to the changed code. Add godoc/contract docs the repo requires on new exported identifiers.
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
- **Commit & push** — the commit(s), the branch pushed, and the worktree path the work lives in.
- **Remaining risk** — deferred items and anything review/validation could not cover, especially around safety, ordering, concurrency, performance, or architecture boundaries.

## Stop-and-ask conditions (use AskUserQuestion; never silently proceed)

- `<spec-dir>` is missing or lacks any of the three spec files (Step 0).
- The resolved worktree carries unrelated uncommitted changes (Step 0).
- `plan.md`/`requirements.md` contradict each other or a documented repo constraint (Step 2).
- A real implementation fork with trade-offs (Step 3).
- `/codex-review` reports codex is unavailable (Step 5, defer to that skill's own gate).
- A verification gate fails for a pre-existing reason unrelated to the change (Step 5).
- Any ambiguity about the push target (Step 7).
