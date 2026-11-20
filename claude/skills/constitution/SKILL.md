---
name: constitution
description: "Writes or revises the project constitution - specs/mission.md, specs/tech-stack.md, and specs/roadmap.md - from the repo's README.md and a grilling session with the user, then has codex review the three files and folds the valid findings back in. tech-stack.md carries the engineering standards and quality gates that /spec plans against and /code enforces; roadmap.md is a dependency-ordered list of very small, independently shippable phases that /spec picks up one at a time. Leaves the files uncommitted. Use when starting a new project, bootstrapping specs/ before the first /spec, or whenever the user asks for a constitution, mission statement, tech-stack doc, engineering standards, or implementation roadmap for the repo - including refreshing an existing one after the project's direction changed."
---

# Constitution skill

Write the three documents every later stage stands on:

- `specs/mission.md` - why the project exists, who it is for, what it will and will not do.
- `specs/tech-stack.md` - what it is built with, and the engineering standards and quality gates that follow from that.
- `specs/roadmap.md` - the implementation order, as **very small phases**.

This is the first of three stages:

| Stage | Writes | Where |
|---|---|---|
| `/constitution` | `specs/{mission,tech-stack,roadmap}.md` | the default branch |
| `/spec` | `specs/<name>/{requirements,plan,validation}.md` for one phase | a `specs/<name>` branch |
| `/code` | the code and tests for that phase | the same branch, as one PR |

The later stages treat these files as a contract. `/spec` takes the next unstarted phase and plans it inside the mission's scope and the tech stack's standards. `/code` holds every implementer to those standards and runs the gates named here. A vague line here becomes a guess in every phase, so precision matters more than polish.

The flow: read the repo → grill the user on the decisions → write → codex review → adjudicate → report. The files are left **uncommitted** for the user to read and commit.

The main loop owns everything that talks to the user or rests on their decisions: the grilling, the writing, every question, and the final call on each review finding. Subagents take the bulky, self-contained work: the repo survey, the codex run, and the adjudication of a long list of findings. Give each one a self-contained prompt with absolute paths, the exact commands, and the result shape you want back.

## Step 1 - Read the repo

Finding facts is your job; only decisions go to the user. Work from the repository root (`git rev-parse --show-toplevel`, or the current directory outside git). The constitution belongs on the default branch, so if the checkout is on another branch (a session still inside a phase's worktree, for instance), say so and ask where to write before going on. Then, in one message:

- Read `README.md`, the primary statement of intent. If there is none, ask the user for a two-or-three-sentence pitch and seed from that.
- Read `CLAUDE.md` / `AGENTS.md` and the architecture or convention docs they cite. Rules stated there are facts the tech stack must agree with, not questions for the user.
- Read any existing `specs/mission.md`, `specs/tech-stack.md`, and `specs/roadmap.md`. None means **create mode**. Any means **revise mode**: they are the starting point, not something to replace.
- Launch an `Explore` subagent (medium thoroughness) to report, with file citations:
  - languages, frameworks, and their **pinned versions** from the manifests;
  - storage, messaging, and external services the code or config touches;
  - build, lint, format, and test commands (task files, package scripts, CI workflows);
  - deployment and infrastructure signals (Dockerfiles, compose files, IaC, pipelines);
  - the top-level layout, any visible architecture style, and the existing test conventions;
  - what already works today, so the roadmap doesn't plan it again.

An empty or README-only repo is a valid answer; the survey then just says so.

In revise mode, also find where each phase stands. A phase is `done` once its PR has merged, which leaves a `specs/<name>/` directory on the default branch. A phase is **in flight** when an `origin/specs/*` branch's copy of the roadmap marks it `in progress`; the default branch still shows it as `not started`. Fetch those branches (`git fetch --prune origin '+refs/heads/specs/*:refs/remotes/origin/specs/*'`), list them with `git for-each-ref refs/remotes/origin/specs/`, and read each copy with `git show <ref>:specs/roadmap.md`.

Where the README and the code disagree (the README promises Postgres, the code uses SQLite), that is a decision. Raise it in the grilling session instead of resolving it silently.

## Step 2 - Grill the user (`grilling` skill)

Invoke **`mattpocock-skills:grilling`** with the Skill tool and run its session to completion.

Seed the design tree from the README, the survey, and (in revise mode) the existing files, so every question and recommended answer is specific to this project. The tree covers at least:

- **Mission**
  - The problem, and who has it. Primary users vs. secondary ones.
  - The one-paragraph pitch: what the project does for those users.
  - Success measures: how we will know it is working (observable, ideally measurable).
  - Non-goals: what it deliberately will not do. They matter as much as the goals, because they let later specs cut scope without re-litigating.
  - Principles: the tie-breakers for future trade-offs (e.g. "offline-first beats feature breadth").
- **Tech stack**
  - Each layer's choice (language, framework, storage, messaging, UI, infra, CI), each with its trade-off. What the survey found already in use is a fact unless the user wants to change it.
  - Engineering standards: the architecture style and its dependency rule, the repo layout, the test-first policy and test levels, and style precedence. Recommend the defaults listed in Step 3 wherever the repo's docs are silent.
  - The quality gates every phase must pass, as exact commands.
  - Hard constraints: must-use and must-not-use technologies, platforms, licenses, budgets.
- **Roadmap**
  - The first end-to-end slice (the walking skeleton): the thinnest path that proves the stack works together.
  - The MVP boundary: which phase makes the project useful to its primary user.
  - Ordering: dependencies first, then the riskiest assumptions, then value.
  - Phase size: default to the "very small" rule in Step 3 unless the user says otherwise.
  - In revise mode: what changed in direction, and what it means for the phases in flight.

Ask only questions whose answer changes a document. In revise mode, grill on gaps, contradictions, and the user's intended changes; a decision the existing files already record stays settled unless the README or the survey puts it in doubt.

**Done when** the frontier is empty and the user confirms you share an understanding. Then list the **settled decisions** in the conversation as `D1`, `D2`, .... Step 3 writes from this list, and Step 5 checks every codex finding against it. Write nothing under `specs/` until then.

## Step 3 - Write the three files

Create `specs/` if needed. In revise mode, edit the existing files rather than regenerating them: keep wording the user didn't ask to change, and keep phase numbers and names stable, because `/spec` derived branch and directory names from them.

Write for the next agent that reads these files cold: concrete nouns, no marketing, every claim traceable to a settled decision, the README, or the repo.

### `specs/mission.md`

```markdown
# Mission

<One-paragraph pitch: what this project is, for whom, and why it matters.>

## Problem
<Who hurts, how, and what they do today instead.>

## Users
- **<Primary user>** - <what they need from this project>
- **<Secondary user>** - ...

## Goals
1. <Outcome> - measured by <observable signal>.
2. ...

## Non-goals
- <What we deliberately won't do> - <one-line reason>.

## Principles
- <Tie-breaker for future trade-offs>.
```

### `specs/tech-stack.md`

```markdown
# Tech stack

<One paragraph: the shape of the system. Add a small ASCII diagram if there is more than one runtime component.>

## Stack
| Layer | Choice | Version | Why |
|-------|--------|---------|-----|
| Language | ... | ... | ... |

## Architecture and conventions
<Architecture style and its dependency rule (what may import what, where interfaces are defined), the repo layout (which directory owns which concern), when a design pattern is warranted, and style precedence.>

## Testing and quality gates
<The test-first policy, what each test level (unit / integration / e2e) covers and where it lives, and the exact gate commands every phase must pass, in order: format, lint, build, test (e.g. `task ci`).>

## Infrastructure and delivery
<Where it runs, how it's built and deployed, environments.>

## Constraints
- <Must-use / must-not-use, platform, licensing, budget>.

## Deferred decisions
- <Decision> - decided in Phase <N> because <why it can wait>.
```

**Architecture and conventions** and **Testing and quality gates** are the project's engineering standards: `/spec` plans against them, and `/code` hands them to every implementer and reviewer. Write them as rules an agent can follow and a reviewer can check ("domain packages import nothing from `adapters/`"), not as aspirations ("clean architecture"). Where the repo's docs and the user are silent, the defaults are:

- **Dependencies point inward.** Keep the repo's existing boundaries; interfaces are defined by the code that consumes them, and domain logic stays free of transport, storage, and framework concerns.
- **Test-first.** A behavior change starts with a failing test through a public interface, and ships with its tests.
- **Plain code before patterns.** Reach for an abstraction only when it removes real duplication or isolates a dependency, and then use the well-known pattern (Strategy, Repository, Ports & Adapters, Functional Options, ...) rather than a bespoke one.
- **Style precedence.** Documented repo rules, then the surrounding code's idiom, then the language community's conventions.

Versions: copy pinned versions from the manifests. For a choice not yet in the repo, write `latest stable at adoption` or a floor the user named rather than a made-up number. A section that is genuinely empty (no infrastructure yet) keeps its heading and a one-line note saying so.

### `specs/roadmap.md`

The roadmap sets the implementation order, not the design; the detail belongs in each phase's `/spec`. Its phases are **very small**, because each one becomes one spec, one branch, and one reviewable PR. Big phases produce specs nobody can review and PRs nobody can merge.

A phase is small enough when **all** of these hold:
- **One capability.** It delivers one observable thing a user, operator, or developer can do or verify. If the name needs an "and", split the phase.
- **Vertical, not horizontal.** It cuts end to end through whatever layers it needs. "Set up the database" on its own is a layer, not a phase. The exception is the walking skeleton, which may be mostly plumbing because proving the plumbing is its capability.
- **One PR.** Its `/spec` plan would hold roughly 2-5 task groups, and a reviewer could read the whole change in one sitting.
- **Independently verifiable.** It has a binary "Done when" (a test passes, a command produces an output, a demo works) that doesn't depend on a later phase.
- **Leaves the system working.** After it merges, the default branch builds, passes its gates, and does something it couldn't do before.

Order the phases: **Phase 1 is the walking skeleton** (build, test, and CI gates green, plus the thinnest end-to-end path through the chosen stack). After that come dependencies before dependents, the riskiest assumptions as early as their dependencies allow, and then value. Mark the phase where the MVP is reached.

Keep phase names short (four words at most) and distinctive: `/spec` turns them into kebab-case branch names.

```markdown
# Roadmap

<Two or three sentences: the strategy behind this order, and where the MVP lands.>

Status values: `not started` · `in progress` · `done`. `/spec` sets `in progress` and `/code` sets `done`, both on the phase's branch, so this file on the default branch shows `done` once the phase's PR has merged.

## Phase 1 - Walking skeleton
- **Status:** not started
- **Delivers:** <the one capability>
- **Scope:** <2-4 bullets of what's in; name what's explicitly out if it's tempting>
- **Depends on:** -
- **Done when:** <binary signal>

## Phase 2 - <Name>
...

## Later
- <Ideas that are in the mission but not yet sequenced; one line each, no phase numbers.>
```

In revise mode, `done` phases and phases in flight keep their number, name, and text: an edit beside an in-flight phase's `Status:` line would conflict with the flip its branch carries. If the direction changed, adjust or reorder only the phases that are `not started` and not in flight, and tell the user about any phase in flight that the change affects.

Before moving on, check the files against each other: every goal is served by at least one phase (or appears under `Later`), no phase works against a non-goal, every technology a phase relies on appears in the stack table, and every gate command exists in the repo or is delivered by Phase 1. Fix what you find now, so codex can spend its review on harder problems.

## Step 4 - Codex review (in a subagent)

Get an independent second-model review. Launch a `general-purpose` subagent and point it at `references/codex-review.md` in this skill's directory, which holds its instructions. Give it:

- `<dir>`: the repo root.
- `<tag>`: `constitution-<random>`.
- `<scratch>`: `/tmp/codex-constitution-<repo-dirname>.md`.
- `<focus>`:

> Review this project's constitution: specs/mission.md, specs/tech-stack.md, specs/roadmap.md. Also read README.md, CLAUDE.md / AGENTS.md if present, and the repo's build manifests and CI config. Review only these three files; ignore other working-tree changes. Look for: contradictions among the three files or with README.md; mission goals no roadmap phase serves, and phases that serve no goal or work against a non-goal; technologies a phase relies on that are missing from tech-stack.md; tech-stack claims (choices, versions, gate commands) that contradict the repo's actual manifests or CI; engineering standards too vague for an implementer to follow or a reviewer to check; roadmap phases that are too large (more than one capability, not shippable as one PR, horizontal layers instead of vertical slices, or a "Done when" that is missing, not binary, or depends on a later phase); phases out of dependency order or risky assumptions left needlessly late; a Phase 1 that isn't a walking skeleton; vague or unmeasurable goals; and gaps that would force a later feature spec to guess. For each finding, output a numbered item with the file, the issue, and the suggested change. Output findings only; do not rewrite the files.

If it returns `codex failed`, tell the user and `AskUserQuestion`: **retry the codex review**, **substitute a self-review** (one or two adversarial `general-purpose` subagents given the same focus text, whose findings go through Step 5 the same way), or **skip the review**. The report names the option taken.

## Step 5 - Adjudicate the findings and finalize

Codex's findings are hypotheses, not instructions. With more than about 8, split them into batches of 3-5 (contradictory findings share a batch) and launch one subagent per batch in a single message, each with the settled-decision list; the final call on each finding stays here. For each finding:

1. Re-read the cited passage and confirm the problem is real. Discard findings about text or files that don't exist.
2. Check factual claims against the repo (manifests, CI, the survey) rather than taking codex's word or your own memory.
3. Give it a disposition:
   - **accept** - a real gap, contradiction, or oversized phase. Edit the file(s), keeping each edit traceable to its finding number.
   - **reject** - wrong, already handled, or only preferring a different choice than one the user made, however plausible it sounds. Say why.
   - **defer** - valid but not constitution-level (it belongs in a phase's spec), or it needs a user decision that can wait. Say where it goes.

A finding you would otherwise accept that changes a settled decision (a new non-goal, a different stack choice, a moved MVP), or one showing that a decision rests on a wrong fact or is unsafe, is the user's call. Reopen that branch of the design tree with the grilling skill, update the decision list, and then edit. Splitting an oversized phase is an ordinary accept, unless the split moves the MVP line or changes what a phase in flight covers.

After the edits, re-run the Step 3 cross-file check, since a fix in one file often leaves another stale.

## Step 6 - Report

Leave the three files uncommitted. Report:

- The three file paths, each with a one-sentence summary, plus the phase count and the MVP phase.
- In revise mode: what changed in each file, and which phases were left untouched because they are `done` or in flight.
- The codex outcome: total findings and the accept / reject / defer breakdown, with a one-line reason for each rejection and a destination for each deferral (or which Step 4 option was taken and why).
- Any README/code disagreement the user resolved, if the README now needs updating to match.
- Next step: commit the three files and get them onto the default branch (a direct push, or a merged PR), then run `/spec`. `/spec` cuts its worktree from `origin/<default>`, so it only sees a constitution that has landed there.
