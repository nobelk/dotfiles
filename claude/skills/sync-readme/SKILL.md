---
name: sync-readme
description: Generate or refresh the repository's README.md for future engineers and product managers by analyzing the codebase, spec files, the docs/ folder and other documentation, the tests, and the project's own lint/format/build/test/run commands — then verifying those commands actually work before documenting them. Produces a README with six sections (project overview, brief file structure, verified lint/format/build/test/run instructions, ASCII diagrams of the critical workflows, critical conventions/pitfalls, and the project's coding styles), then runs codex (OpenAI Codex CLI) headlessly to review the README, validates every codex finding against the actual repo, and folds the ones that hold up back into the file. Invoke manually when the README is missing, stale, or after a change that alters how the project is built, tested, or run.
---

# Sync README skill

Write a README.md that a new engineer or a product manager can trust on day one. The defining
constraint: **every command in the README must have been run in this skill's own session and
documented with the outcome actually observed** — the lint/format/build/test/run instructions are
*verified*, not transcribed from whatever the existing README or docs claim. A command that fails,
or that you could not run, is reported as such (with its prerequisite caveat) or omitted — never
presented as working.

Output is a created-or-updated `README.md` at the repo root containing the six required sections,
reviewed by codex (OpenAI Codex CLI) with each finding adjudicated before any edit, plus a short
final report of what was verified, what was assumed, and the codex review outcome.

If the repo has a `CLAUDE.md`, an `AGENTS.md`, or `specs/`, read them first — they are
authoritative for conventions, layering rules, and the canonical command list, and they win over
any codex suggestion or doc that contradicts them.

## Subagent delegation

Run the expensive, self-contained steps in **`general-purpose` subagents** (via the `Agent`/`Task`
tool) and keep orchestration in the main loop. The split is fixed:

- **Main loop owns** (never delegate): every `AskUserQuestion` gate (Step 0 overwrite confirmation,
  Step 2 a command that hangs or looks destructive, Step 4 codex-unavailable, Step 6 ambiguous
  finding), the final decision on what each README section says, and the Step 7 report. Subagents
  cannot prompt the user — anything that might stop-and-ask stays here.
- **Delegate to `general-purpose` subagents** (each returns a compact structured result, keeping
  verbose file dumps and command output out of the main context):
  - **Step 1** — fan out parallel readers: one over the source tree + entry points, one over
    `specs/`, one over `docs/` and other documentation (`*.md`, `CONTRIBUTING`, ADRs), one over the
    test suite. Each returns a tight summary, not raw file contents. Dispatch these in **one
    message** so they run concurrently — they are independent.
  - **Step 5** — run the `codex exec --sandbox read-only …` review of the README and return the raw
    findings verbatim (also written to the scratch file). The codex transcript stays in the subagent.
  - **Step 6** — hand the findings plus the Step 1 summaries and the Step 2 verified-command log to a
    subagent that adjudicates each finding and returns the accept/reject/defer disposition table.

Keep **Step 2 (command verification) in the main loop** — it runs real build/test commands whose
output you must see, and a hanging or destructive command must be able to stop and ask the user.

Give each subagent a self-contained prompt: exactly what to read or run, and the precise shape of
the result to return.

## Step 0 — Establish context and the command surface

1. Find the repo root (`git rev-parse --show-toplevel`) and confirm `README.md`'s presence there.
   If it already exists, this is an **update**, not a fresh write — read it now so you preserve any
   still-accurate, hard-won content (badges, license, links) and only correct what is wrong or
   stale. If a substantial README exists and the user did not explicitly ask to regenerate it, use
   `AskUserQuestion` to confirm update-in-place vs. full rewrite before overwriting.
2. Identify the **command runner** and the real verbs, in this order of authority:
   - A task runner the repo standardizes on — `Taskfile.yml` (`task <verb>`), `Makefile`
     (`make <target>`), `justfile`, `package.json` scripts, `pyproject.toml`/`tox`, `Cargo.toml`,
     `go.mod`, etc. **Read the actual runner file** to get the real verb names; do not assume
     `make test` exists.
   - `CLAUDE.md` / `AGENTS.md` / `CONTRIBUTING.md` "Commands" sections — often list the canonical
     wrappers (e.g. `task lint` = ruff + mypy). These name *what to run*; Step 2 confirms they work.
   - The CI workflow (`.github/workflows/*`, `.gitlab-ci.yml`) — the ground truth for the gate
     sequence when docs and runner disagree.
   Record the candidate commands for each of: **lint, format, build, test, run**. Some projects
   fold these (lint includes format-check; build is implicit for interpreted languages) — note
   which are N/A rather than inventing one.

## Step 1 — Analyze the repository (fan-out)

Dispatch the parallel reader subagents described above. Together they must surface:

- **Overview** — what the project *is* and the problem it solves, in language a product manager
  understands: the domain, the primary user-facing capability, the current build stage/version, and
  what is explicitly out of scope. Prefer `specs/mission.md`, `specs/roadmap.md`, the existing
  README intro, and package metadata over guessing from code.
- **File structure** — the top-level directories and their one-line responsibilities. Brief: the
  major modules and where the entry point lives, not an exhaustive `tree`.
- **Critical workflows** — the 1–3 flows that matter most (the request/data path, the build/release
  path, the core domain loop). You need enough detail to draw an accurate ASCII diagram in Step 3 —
  capture the real component names and the direction of data flow, not a generic box diagram.
- **Conventions, pitfalls, and coding style** — the rules a newcomer would violate by accident:
  architectural dependency rules, the testing/coverage gate, security or config invariants,
  environment caveats (e.g. a shadowed tool, a port collision), and the formatting/typing/lint
  standard the code actually follows (line length, strict typing, naming). Pull these from
  `CLAUDE.md`, lint/formatter config, and the dominant pattern in the code — and confirm the style
  claims against an actual source file, not just the config.

Subagents read excerpts and return summaries; do not pull whole files into the main context.

## Step 2 — Verify the commands actually work (the load-bearing step)

This is what separates this skill from transcription. For each candidate command from Step 0, **run
it** from the repo root and record the real outcome. Sequence matters and so does safety:

1. **Setup/deps first** if the project needs it (`task setup`, `npm ci`, `uv sync`, `go mod
   download`) — without it, lint/build/test may fail for the wrong reason. If setup is heavy or
   requires network/credentials and the environment can't support it, note that and continue with
   whatever does run.
2. Run **format-check, lint, build, test, and the run/help command** (prefer a non-blocking form for
   the app itself — `--help`, `--version`, a `--dry-run`, or a fast smoke target — rather than
   launching a long-lived server). Capture exit code and a short tail of output for each.
3. Classify each command:
   - **verified** — ran, exited success → document it exactly as run.
   - **verified-fails** — ran, exited non-zero for a real reason → document the command *and* the
     caveat (e.g. "requires a running Postgres", "needs `ANTHROPIC_API_KEY`"), so the README is
     honest rather than wrong.
   - **unverified** — could not run here (network/secret/hardware/time) → either omit or mark
     clearly as unverified with the reason. Never present an unrun command as confirmed.

Safety gates (use `AskUserQuestion`, do not silently proceed):
- A command appears **destructive** (`down`, `clean`, `reset`, `prune`, `drop`, anything that tears
  down state or deletes data) — confirm before running, or skip it and document from the runner file.
- A command **hangs** (a server, a watcher) — interrupt it; document it as "starts a long-running
  process" rather than waiting.

Keep a tidy verified-command log (command → status → caveat). It is both the source for the README's
instructions section and an input the Step 6 adjudicator uses to reject any codex claim about
commands that contradicts what you actually observed.

## Step 3 — Write (or update) README.md

Create or update `README.md` at the repo root. Match the repo's existing tone and any house Markdown
conventions. Include these six sections (use the project's real names, not these labels verbatim):

1. **Project overview** — a few sentences a PM and an engineer both get value from: what it is, the
   problem it solves, current stage/version, and scope boundaries. Lead with this.
2. **Project file structure** — a brief annotated tree of the top-level directories with one-line
   responsibilities. Keep it short; link deeper docs rather than inlining them.
3. **Lint / format / build / test / run** — the **verified** commands from Step 2, copy-pasteable,
   in the order a newcomer needs them (setup → run → test → lint/format → build). Carry forward each
   command's caveat (prerequisites, env vars, services). Mark anything unverified as such. Include
   the single fresh-clone bring-up line if the project has one.
4. **Critical workflows (ASCII diagrams)** — render the Step 1 flows as ASCII diagrams. Use real
   component/module names and show data direction; one diagram per critical workflow (typically the
   core domain loop and the build/release or request path). Keep them legible in a fixed-width
   terminal — boxes and arrows, not art. Add a one-line caption under each.
5. **Critical conventions & pitfalls** — the rules and gotchas from Step 1 as a scannable list: the
   architectural invariants, the blocking gates, the environment caveats, the security/config rules.
   Frame each as "do X / don't Y, because Z" so it is actionable.
6. **Coding style** — the standards the code actually follows: language version, formatter + line
   length, typing strictness, lint rule set, naming conventions, and the priority order when
   requirements conflict if the project documents one.

Be accurate over comprehensive. If a fact could not be verified, either leave it out or label it.

### ASCII diagram guidance

Draw what the code does, not a generic template. A workable shape:

```
  ┌──────────┐     ┌─────────────┐     ┌───────────┐
  │  caller  │────▶│  component  │────▶│  datastore │
  └──────────┘     └─────────────┘     └───────────┘
       label on the edge says what flows
```

Prefer the actual port/adapter/service names from Step 1. If a flow has concurrent branches that
fuse (e.g. two retrieval legs → fusion), show the split and the join — that structure is exactly the
"critical workflow" worth a diagram.

## Step 4 — Hand off to codex for review

Get an independent second-model review of the README just written. The README is new/edited Markdown
rather than a code diff, so plain `codex exec` fits better than `codex exec review`. Run it
headlessly from the repo root via the Step 5 subagent:

```bash
codex exec --sandbox read-only "<instructions>"
```

With `<instructions>`:

> Review README.md at the repo root for a new engineer and a product manager. Also read CLAUDE.md,
> AGENTS.md, the task runner file (Taskfile.yml / Makefile / package.json), and specs/ if they exist
> — the README must be consistent with them. Check for: commands that don't exist or are named wrong
> versus the actual runner, build/test/run instructions that would fail or are missing a prerequisite,
> an inaccurate or misleading project overview, a file-structure section that doesn't match the real
> tree, ASCII workflow diagrams that misrepresent the actual data flow or component names, missing
> critical conventions/pitfalls, wrong coding-style claims, and internal contradictions. For each
> finding output a numbered item with: the README section, the issue, and the suggested change.
> Output findings only — do not rewrite the document.

- Capture stdout verbatim to a scratch file (e.g. `/tmp/codex-readme-review-<repo>.md`) so Step 6 is
  auditable. Do **not** commit this file.
- Verify `codex exec --help` if the command errors — the CLI evolves. If `codex` is not installed or
  errors, do not silently skip: tell the user the codex review failed and use `AskUserQuestion` to
  offer alternatives (retry, substitute a self-review pass against Step 1/Step 2 findings, or report
  the README as-is without the second-model pass).

## Step 5 — (delegated) run the review

Covered by the Step 4 command, dispatched to a `general-purpose` subagent that returns the raw
findings verbatim. The lengthy codex transcript stays in the subagent.

## Step 6 — Validate every finding and update the README

Do **not** apply codex's comments blindly — they are hypotheses to adjudicate, not instructions. For
each numbered finding:

1. Re-read the cited README passage and the underlying reality (the runner file, the source, the
   Step 2 verified-command log).
2. **A finding about a command is decided by the Step 2 log, not by codex's assertion** — if you ran
   the command and saw it succeed, a codex claim that it is wrong is **rejected** with that evidence;
   if codex correctly flags a command you marked verified-fails/unverified, **accept** and fix the
   wording.
3. Check the finding against `CLAUDE.md` / specs constraints — a finding that contradicts a
   documented project rule is rejected, however plausible.
4. Mark a disposition:
   - **accept** — real inaccuracy or gap; update the affected section.
   - **reject** — factually wrong, hallucinated, or contradicts the verified log / a project rule;
     note why with a citation.
   - **defer** — real but out of scope for a README (belongs in CONTRIBUTING/docs); note where.

Apply accepted edits. If an accepted fix is **ambiguous** (more than one reasonable wording with
different meaning) or would change a claim the user explicitly set, resolve it with
`AskUserQuestion` in the main loop — never in the subagent. Re-run any command a finding caused you
to change, so the README stays verified.

## Step 7 — Final report

State:

- **README** — created or updated, and which of the six sections changed.
- **Commands** — the verified / verified-fails / unverified breakdown, and anything that could not be
  run here and why.
- **Codex findings** — total count and the accept/reject/defer breakdown, with one-line reasons for
  rejections (or that the review was skipped and why).
- **Remaining risk** — unverified instructions, assumptions made for the overview, and anything a
  human should confirm.

Do **not** commit — leave `README.md` for the user to review and commit themselves, unless they ask.

## Stop-and-ask conditions (use AskUserQuestion; do not silently proceed)

- A substantial README already exists and the user did not specify update vs. full rewrite (Step 0).
- A command to verify looks destructive or hangs (Step 2).
- `codex` is unavailable or its review errors (Step 4).
- An accepted finding's fix is ambiguous or would change a user-set claim (Step 6).

## Notes

- "Verified" means *run in this session*. Never upgrade an unrun command to verified because the docs
  or the old README asserted it works — that assertion is exactly what this skill exists to check.
- Keep diagrams and the file-structure tree **brief**; the README is an on-ramp, not a manual. Link
  to `docs/`, `specs/`, and `CLAUDE.md` for depth instead of duplicating them.
- For a polyglot or monorepo, scope to the primary package unless the user asks for all; note the
  scope in the overview.
