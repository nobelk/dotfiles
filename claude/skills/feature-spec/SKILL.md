---
name: feature-spec
description: Scaffold planning docs for the next roadmap phase. Takes a git branch name as input (falls back to YYYY-MM-DD-feature-name derived from specs/roadmap.md if omitted). The feature branch is always created under the specs/ namespace (specs/<name>); names without the prefix are auto-prepended. Reads specs/roadmap.md, specs/mission.md, and specs/tech-stack.md, creates the branch, then asks the user one grouped AskUserQuestion (scope, key decision, validation) before writing specs/<name>/{plan.md, requirements.md, validation.md}. After writing, runs codex (OpenAI Codex CLI) headlessly to review the spec files, validates each review finding, and updates the specs where findings hold up. Invoke manually when starting a new feature.
---

# Feature spec skill

Scaffold the planning docs for the next phase on the roadmap. Output is three files under `specs/<name>/`, written **after** gathering inputs from the user via a single `AskUserQuestion` call, then reviewed by codex (OpenAI Codex CLI) with validated findings folded back into the files.

Two related identifiers, derived from one input:
- `<branch-name>` — the git branch, **always** namespaced under `specs/` (e.g. `specs/2026-05-05-firefly`).
- `<name>` — `<branch-name>` with the leading `specs/` stripped; names the docs directory `specs/<name>/`. Stripping the prefix avoids `specs/specs/...` nesting.

## Step 0 — Read and normalize the branch name input

The skill accepts a **git branch name** as its argument (e.g. `2026-05-05-firefly`, `specs/auth-revamp`).

- If an argument is provided, normalize it: if it does not already start with `specs/`, prepend `specs/` to form `<branch-name>` (so `feat-x` becomes `specs/feat-x`). Skip the slug-derivation step in Step 2.
- If no argument is provided, fall back to deriving `<branch-name>` as `specs/<today>-<feature-name>` per Step 2.
- Validate the normalized name with `git check-ref-format --branch "<branch-name>"`. If invalid, stop and ask the user for a corrected name — do not silently sanitize.
- If a branch with that name already exists locally (`git show-ref --verify --quiet refs/heads/<branch-name>`), stop and ask the user whether to switch to it, pick a different name, or delete it.

## Step 1 — Read the roadmap and supporting docs

In parallel, read whichever of these exist:
- `specs/roadmap.md` — identify the next unstarted phase (the feature to spec).
- `specs/mission.md` — product north star; informs scope decisions.
- `specs/tech-stack.md` — informs tech choices in `plan.md`.

If `specs/roadmap.md` is missing, stop and ask the user what feature to spec out — don't fabricate a phase.

If `specs/mission.md` or `specs/tech-stack.md` is missing, note it and proceed with what you have.

## Step 2 — Resolve the branch name and create the branch

If the user supplied a branch name in Step 0, use the normalized `specs/`-prefixed form as `<branch-name>` and skip the slug derivation below.

Otherwise, derive `<branch-name>` as `specs/<today>-<feature-name>`:
- `<feature-name>`: kebab-case, ≤4 words, derived from the phase name on the roadmap.
- `<today>`: the local date in `YYYY-MM-DD`.

Before branching:
- Run `git status --short`. If the working tree is dirty, stop and ask the user how to proceed (commit/stash/abort) — don't carry uncommitted changes onto the new branch.
- Resolve the default branch:

  ```bash
  git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's@^origin/@@' \
    || (git show-ref --verify --quiet refs/heads/main && echo main) \
    || (git show-ref --verify --quiet refs/heads/master && echo master)
  ```

Then: `git switch -c <branch-name> <base>`.

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

## Step 5 — Codex review of the spec files

Get an independent second-model review of the three files just written. Run codex headlessly from the repo root with an explicit file list (the specs are new untracked markdown, not a code diff, so plain `codex exec` fits better than `codex exec review`):

```bash
codex exec --sandbox read-only "<instructions>"
```

With `<instructions>`:

> Review these planning documents: specs/<name>/requirements.md, specs/<name>/plan.md, specs/<name>/validation.md. Also read specs/roadmap.md, specs/mission.md, and specs/tech-stack.md if they exist — the specs must be consistent with them. Review for: internal contradictions between the three files, scope items in plan.md missing from requirements.md (and vice versa), validation criteria that don't actually verify the stated requirements, ambiguous or untestable acceptance criteria, missing edge cases or risks, and conflicts with the roadmap/mission/tech-stack. For each finding output a numbered item with: file, the issue, and the suggested change. Output findings only — do not rewrite the documents.

- Capture stdout verbatim to a scratch file (e.g. `/tmp/codex-spec-review-<name>.md`) so Step 6 is auditable. Do **not** commit this file.
- If `codex` is not installed or the command errors, do not silently skip: tell the user the codex review failed and use AskUserQuestion to offer alternatives (retry, substitute a self-review pass, or skip the review and report the files as-is).

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
- If the project already has a `specs/<name>/` directory, stop and ask the user whether to overwrite, append, or pick a different name.
- If the user runs this skill on a branch that isn't the default branch, warn them — they may have meant to run it after merging their current work.
