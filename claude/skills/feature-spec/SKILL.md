---
name: feature-spec
description: Scaffold the planning docs for the next roadmap phase — creates a specs/<name> git branch in its own git worktree (reusing a worktree that already has the branch), gathers scope/key-decision/validation answers in one grouped AskUserQuestion, writes specs/<name>/{plan.md, requirements.md, validation.md}, then codex-reviews the specs and folds validated findings back in. Takes a git branch name as the argument (auto-prefixed with specs/; derived from specs/roadmap.md if omitted). Invoke manually when starting a new feature.
---

# Feature spec skill

Scaffold the planning docs for the next phase on the roadmap. Output is three files under `specs/<name>/`, written **after** gathering inputs from the user via a single `AskUserQuestion` call, then reviewed by codex (OpenAI Codex CLI) with validated findings folded back into the files.

Two related identifiers, derived from one input:
- `<branch-name>` — the git branch, **always** namespaced under `specs/` (e.g. `specs/2026-05-05-firefly`).
- `<name>` — `<branch-name>` with the leading `specs/` stripped; names the docs directory `specs/<name>/`. Stripping the prefix avoids `specs/specs/...` nesting.

## Subagent delegation

Run the expensive, self-contained steps in a **`general-purpose` subagent** (via the `Agent`/`Task` tool), and keep orchestration in the main loop. The split is fixed:

- **Main loop owns** (never delegate): branch-name normalization and the **worktree discovery/creation** (Step 0/2), the single grouped `AskUserQuestion` (Step 3) and any later stop-and-ask, **writing the three spec files** in Step 4 (they depend tightly on the just-gathered answers), and the Step 7 report. Subagents cannot prompt the user, so every gate stays here.
- **Delegate to a `general-purpose` subagent** (each returns a compact result):
  - **Step 5** — launch the `/codex:adversarial-review --background` review of the three spec files, poll `/codex:status` to completion, fetch `/codex:result <job-id>`, and return the raw findings verbatim (also written to the scratch file). The codex transcript stays in the subagent.
  - **Step 6** — split the findings into disjoint batches (~3–5 each; if two findings contradict each other, put them in the same batch so one subagent resolves the conflict) and launch one adjudication subagent per batch **in a single message**, each getting the Step 3 answers and the mission/tech-stack constraints and returning its slice of the accept/reject/defer disposition table. The main loop merges the slices, applies non-decision edits, and routes any finding that would change a user decision back through `AskUserQuestion` here — never in a subagent.

Give each subagent a self-contained prompt: the exact command to run, the spec file paths, and the precise result shape to return.

**Parallelize by default.** When delegated tasks have no data dependency, dispatch them as multiple `Agent`/`Task` calls in a **single message** so they run concurrently — never run independent subagents one at a time across turns. The Step 5 codex run → Step 6 adjudication is a serial chain (findings must exist before adjudication), but **within** Step 6 the adjudication batches fan out in parallel; and the Step 1 roadmap/mission/tech-stack reads are independent — fan them out in one message (whether read in the main loop or as parallel reader subagents).

## Step 0 — Read and normalize the branch name input

The skill accepts a **git branch name** as its argument (e.g. `2026-05-05-firefly`, `specs/auth-revamp`).

- If an argument is provided, normalize it: if it does not already start with `specs/`, prepend `specs/` to form `<branch-name>` (so `feat-x` becomes `specs/feat-x`). Skip the slug-derivation step in Step 2.
- If no argument is provided, fall back to deriving `<branch-name>` as `specs/<today>-<feature-name>` per Step 2.
- Validate the normalized name with `git check-ref-format --branch "<branch-name>"`. If invalid, stop and ask the user for a corrected name — do not silently sanitize.
- **Worktree discovery** — run `git worktree list --porcelain` and look for a `branch refs/heads/<branch-name>` entry:
  - A worktree already has the branch checked out → reuse it: record its root as the working directory for every subsequent step and skip creation in Step 2.
  - No worktree has it, but the branch exists locally (`git show-ref --verify --quiet refs/heads/<branch-name>`) → use `AskUserQuestion` to ask whether to attach it to a new worktree, pick a different name, or delete it and recreate fresh.
  - Neither exists → Step 2 creates the branch inside a new worktree.

## Step 1 — Read the roadmap and supporting docs

In parallel, read whichever of these exist:
- `specs/roadmap.md` — identify the next unstarted phase (the feature to spec).
- `specs/mission.md` — product north star; informs scope decisions.
- `specs/tech-stack.md` — informs tech choices in `plan.md`.

If `specs/roadmap.md` is missing, stop and ask the user what feature to spec out — don't fabricate a phase.

If `specs/mission.md` or `specs/tech-stack.md` is missing, note it and proceed with what you have.

## Step 2 — Resolve the branch name and create the branch in its worktree

If the user supplied a branch name in Step 0, use the normalized `specs/`-prefixed form as `<branch-name>` and skip the slug derivation below.

Otherwise, derive `<branch-name>` as `specs/<today>-<feature-name>`:
- `<feature-name>`: kebab-case, ≤4 words, derived from the phase name on the roadmap.
- `<today>`: the local date in `YYYY-MM-DD`.

Resolve the default branch:

  ```bash
  git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null \
    || (git show-ref --verify --quiet refs/heads/main && echo main) \
    || (git show-ref --verify --quiet refs/heads/master && echo master)
  ```

  `<base>` is a remote-tracking ref (`origin/main`) when `origin/HEAD` is set, else the local
  `main`/`master` fallback — both are valid start points for `git worktree add`. (Don't strip
  `origin/`: a bare `main` fails in clones with no local default branch.)

Define `<wt-path>` as `<repo-parent>/<repo-dirname>-worktrees/<slug>`, where `<slug>` is `<branch-name>` with `/` replaced by `-` (e.g. repo `~/sources/app` + branch `specs/2026-07-29-x` → `~/sources/app-worktrees/specs-2026-07-29-x`). Never nest a worktree inside the repo's own working tree.

Then create or attach the worktree, **branching on what Step 0 found**:
- Branch is new (the common case) → `git worktree add <wt-path> -b <branch-name> <base>` — creates the branch and its worktree in one step. The current checkout (and any uncommitted work in it) is left untouched, so no stash/dirty-tree gate is needed.
- Step 0 found a worktree that already has the branch → nothing to create; use that worktree's root (from Step 0) and skip ahead to Step 3.
- The branch exists unattached and the user chose **attach it** → `git worktree add <wt-path> <branch-name>`.
- The user chose **delete it** (the destructive option in the Step 0 `AskUserQuestion`, so no second confirmation) → `git branch -D <branch-name>` followed by
  `git worktree add <wt-path> -b <branch-name> <base>`.

Finally `cd` to the worktree root — every subsequent step (the spec-file writes, the codex review, the gates) runs from there, `specs/<name>/` is written under it, and subagent prompts carry absolute paths inside the worktree.

## Step 3 — Gather spec inputs (one grouped AskUserQuestion)

Before writing any files, call `AskUserQuestion` **once** with these three questions. Tailor each question's options to what you learned in Step 1 — generic options are useless.

1. **Scope** — header `"Scope"`. What is in vs. out for this phase? Offer 2-4 concrete options (e.g., `"MVP: just import + list"`, `"Full: import + list + edit + delete"`). Lead with the recommended option and label it `(Recommended)`.
2. **Key decision** — header `"Key decision"`. Surface the most consequential open choice you spotted (library, data model, sync vs. async, auth strategy, etc.). Offer 2-4 distinct options with the trade-off in each option's `description`.
3. **Validation** — header `"Validation"`. How do we know this is done? Offer 2-4 options (e.g., `"Unit + integration tests"`, `"Manual QA checklist"`, `"Staging soak + metrics"`).

Do **not** write to disk before this call returns. The answers seed the three files.

## Step 4 — Write the three files

Create `specs/<name>/` (where `<name>` is `<branch-name>` without the leading `specs/`) with:

### `requirements.md`
- **Context** — 2-4 sentences linking this phase to the roadmap, mission, and tech-stack constraints.
- **Scope** — `In:` / `Out:` bullet lists, populated from the Scope answer.
- **Decisions** — bullets capturing the Key-decision answer plus any constraints inherited from mission/tech-stack.

### `plan.md`
A series of **numbered task groups**. Each group:
- Short header (e.g., `## 1. Schema migration`).
- A few sub-bullets describing actual code/migrations/tests.

Order so each group can land as its own commit/PR. Group 1 should be the smallest viable slice that's mergeable on its own.

### `validation.md`
- **Success criteria** — populated from the Validation answer.
- **Checklist** — concrete checkboxes: tests to add, manual checks, metrics/dashboards to confirm.
- **Done when** — one line naming the binary signal (test passes, metric crosses threshold, etc.).

## Step 5 — Codex review of the spec files via `/codex:adversarial-review --background`

Get an independent second-model review of the three files just written through the **`/codex:adversarial-review --background`** flow. This skill uses adversarial-review rather than plain `/codex:review` because the review needs **custom focus text** — it must judge the three spec docs against the roadmap/mission/tech-stack, which `/codex:review` cannot carry. The three new untracked spec files are the working-tree change the review scopes over; the focus text below names them. `--background` detaches the run; recover it with `/codex:status` (progress) and `/codex:result <job-id>` (findings). Run it from the worktree root (the Step 2 `cd` already put you there):

```bash
/codex:adversarial-review --background "<focus>"
```

With `<focus>`:

> Review these planning documents: specs/<name>/requirements.md, specs/<name>/plan.md, specs/<name>/validation.md. Also read specs/roadmap.md, specs/mission.md, and specs/tech-stack.md if they exist — the specs must be consistent with them. Review for: internal contradictions between the three files, scope items in plan.md missing from requirements.md (and vice versa), validation criteria that don't actually verify the stated requirements, ambiguous or untestable acceptance criteria, missing edge cases or risks, and conflicts with the roadmap/mission/tech-stack. For each finding output a numbered item with: file, the issue, and the suggested change. Output findings only — do not rewrite the documents.

Concretely this launches the codex-companion runtime detached (`node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" adversarial-review "--background <focus>"` with `run_in_background: true`, where `${CLAUDE_PLUGIN_ROOT}` is the codex plugin root).
- **Do not block the launching turn.** After launching, poll `/codex:status` until the job finishes, then read `/codex:result <job-id>`. Capture that output verbatim to a scratch file (e.g. `/tmp/codex-spec-review-<name>.md`) so Step 6 is auditable. Do **not** commit this file.
- If `codex` is not installed, the launch fails, or `/codex:status` reports the job errored, do not silently skip: tell the user the codex review failed and use AskUserQuestion to offer alternatives (retry, substitute a self-review pass, or skip the review and report the files as-is).

## Step 6 — Validate the findings and update the specs

Do **not** apply codex's comments blindly — they are hypotheses to adjudicate, not instructions. For each numbered finding:

1. Re-read the cited spec passage and confirm the issue is real.
2. Check it against the user's Step 3 answers — a finding that contradicts a scope, key-decision, or validation choice the user explicitly made is **rejected**, however plausible.
3. Check it against `specs/mission.md` / `specs/tech-stack.md` constraints.
4. Mark a disposition:
   - **accept** — real gap or contradiction; update the affected file(s).
   - **reject** — factually wrong, restates a deliberate scope cut, or contradicts a user decision; note why.
   - **defer** — valid but belongs to a later phase or needs a user decision; note where it should go.

Apply the accepted findings to the spec files, keeping each edit traceable to its finding number. If an accepted finding would change a decision the user made in Step 3 (e.g. widen scope, swap the key decision), do not edit — surface it via AskUserQuestion first. Present the full disposition table to the user.

## Step 7 — Report

Print the three file paths and a one-sentence summary of each, plus the codex review outcome: total findings and the accept/reject/defer breakdown with one-line reasons for rejections (or that the review was skipped and why). Do **not** commit — leave the files staged-or-unstaged for the user to review and commit themselves.

## Notes

- "Today" = local system date, not commit timestamps (only used in the fallback slug derivation).
- The branch is always `specs/<name>` and the docs directory is always `specs/<name>/` — same `<name>`, derived once in Step 0/2; keep them in sync. If `<name>` itself contains further slashes (e.g. `specs/feat/auth`), the spec directory nests accordingly (`specs/feat/auth/`).
- If the project already has a `specs/<name>/` directory, use `AskUserQuestion` to ask whether to overwrite, append, or pick a different name. Run this check **before Step 4 writes the files**; if the user picks a different name, loop back through the Step 0 name normalization and branch-existence check so the branch and `specs/<name>/` names stay in sync.
- If the user runs this skill on a branch that isn't the default branch, warn them — they may have meant to run it after merging their current work.
- The skill never removes worktrees. When a feature is merged and done, the user cleans up with `git worktree remove <wt-path>` (then `git worktree prune`); mention this in the Step 7 report when a worktree was created.
