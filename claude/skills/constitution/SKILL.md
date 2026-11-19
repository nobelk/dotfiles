---
name: constitution
description: Writes (or revises) the project constitution - specs/mission.md, specs/tech-stack.md, and specs/roadmap.md - from the repo's README.md and a grilling session with the user, then has codex review the three files, adjudicates every finding (accept / reject / defer), and folds the valid ones back in. The roadmap is a dependency-ordered list of very small, independently shippable phases that /feature-spec can pick up one at a time. Leaves the files uncommitted. Use when starting a new project, bootstrapping specs/ before the first /feature-spec, or whenever the user asks for a constitution, mission statement, tech-stack doc, or implementation roadmap for the repo - including refreshing an existing one after the project's direction changed.
---

# Constitution skill

Write the three documents every later planning step stands on:

- `specs/mission.md` - why the project exists, who it is for, what it will and will not do.
- `specs/tech-stack.md` - what it is built with, and the conventions and gates that follow from that.
- `specs/roadmap.md` - the high-level implementation order, as **very small phases**.

`/feature-spec` reads all three: it takes the next unstarted roadmap phase, derives its branch name from the phase name, and checks its plan against the mission and tech stack. Whatever this skill writes is the contract that skill builds on, so precision matters more than polish.

The flow is: gather facts → grill the user on the decisions → write → codex review → adjudicate and fix → report. The files are left **uncommitted** for the user to read and commit themselves.

## Subagent delegation

- **Main loop owns** (never delegate): the grilling session (the Skill tool runs in this conversation, and subagents cannot prompt the user), writing the three files (they depend tightly on the settled decisions), every `AskUserQuestion`, adjudicating findings that touch a settled decision, and the final report.
- **Delegate to subagents:**
  - **Step 1 repo survey** - an `Explore` subagent that inventories the existing code (see Step 1). Launch it in the same message as your own README/specs reads.
  - **Step 4 codex review** - a `general-purpose` subagent that launches codex, waits under the deadline, and returns the raw findings verbatim (or `codex failed: <reason>`). The codex transcript stays out of the main context.
  - **Step 5 adjudication**, only when there are more than ~8 findings: split them into disjoint batches of 3-5 (contradictory findings share a batch) and launch one subagent per batch in a single message. Each gets the settled-decision list and returns its slice of the disposition table.

Give each subagent a self-contained prompt with absolute paths, the exact commands, and the result shape you want back.

## Step 0 - Locate the project and detect the mode

Work from the repository root (`git rev-parse --show-toplevel`; if it isn't a git repo, the current directory). Then:

- **README.md** - read it. It is the primary statement of intent. If there is none, don't stop: ask the user for a two-or-three-sentence pitch and use that as the seed instead.
- **Existing constitution** - check for `specs/mission.md`, `specs/tech-stack.md`, `specs/roadmap.md`.
  - None exist → **create mode**.
  - Any exist → **revise mode**. Read them; they are the starting point, not something to replace. Also list `specs/*/` directories: each one is a phase `/feature-spec` has already specced, which tells you which roadmap phases are in flight or done.
- **Agent docs** - read `CLAUDE.md` / `AGENTS.md` and any architecture or convention docs they cite. Rules stated there are facts the tech stack must agree with, not questions for the user.

## Step 1 - Gather the facts (your job, not the user's)

The grilling skill's rule applies here in full: finding facts is your job; only decisions go to the user. Before the first question, know what the repo already settles.

Launch an `Explore` subagent (medium thoroughness) to report, with file citations:
- Languages, frameworks, and their **pinned versions** from manifests (`go.mod`, `package.json`, `Cargo.toml`, `pyproject.toml`, `pubspec.yaml`, ...).
- Storage, messaging, and external services the code or config touches.
- Build, lint, format, and test commands (Makefile, Taskfile, justfile, package scripts, CI workflows).
- Deployment and infrastructure signals (Dockerfiles, compose files, IaC, CI/CD pipelines).
- Top-level layout and any visible architecture style (layered, hexagonal, monorepo packages, ...).
- What is already built - capabilities that work today, so the roadmap doesn't plan them again.

An empty or README-only repo is a valid answer; the survey then just says so.

When the README and the code disagree (README promises Postgres, code uses SQLite), that is a decision for the user. Raise it in the grilling session instead of resolving it silently.

## Step 2 - Grill the user (`grilling` skill)

Invoke **`mattpocock-skills:grilling`** with the Skill tool and run its session to completion. This is the skill `/grill-me` loads. Call it by this name, because `/grill-me` sets `disable-model-invocation` and the Skill tool refuses it.

Seed the design tree from the README, the survey, and (in revise mode) the existing files, so every question and recommended answer is specific to this project. Generic questions waste the user's time. The tree must cover at least:

- **Mission**
  - The problem, and who has it. Primary users vs. secondary ones.
  - The one-paragraph pitch: what the project does for those users.
  - Success measures: how we will know it is working (observable, ideally measurable).
  - Non-goals: what it deliberately will not do. These matter as much as the goals, because they are what lets later specs cut scope without re-litigating.
  - Principles: the tie-breakers for future trade-offs (e.g. "offline-first beats feature breadth").
- **Tech stack**
  - Each layer's choice (language, framework, storage, messaging, UI, infra, CI), each with its trade-off. Anything the survey found already in use is a fact unless the user wants to change it.
  - Architecture style and repo layout.
  - Testing strategy and the quality gates every phase must pass.
  - Hard constraints: must-use and must-not-use technologies, platforms, licenses, budgets.
- **Roadmap**
  - The first end-to-end slice (the walking skeleton): the thinnest path that proves the stack works together.
  - The MVP boundary: which phase makes the project useful to its primary user.
  - Ordering: dependencies first, then the riskiest assumptions, then value.
  - Phase size: confirm the user's appetite. Default to the "very small" rule in Step 3 unless they say otherwise.
  - In revise mode: which phases are done or in progress (check them against the `specs/*/` directories), and what changed in direction.

Ask only questions whose answer changes a document. In revise mode, grill on gaps, contradictions, and the user's intended changes. Don't re-ask decisions the existing files already record, unless something (new README content, the survey) puts them in doubt.

**Done when** the frontier is empty and the user confirms you share an understanding. Then list the **settled decisions** in the conversation as `D1`, `D2`, .... Step 3 writes from this list, and Step 5 checks every codex finding against it.

Write nothing under `specs/` until the session is done.

## Step 3 - Write the three files

Create `specs/` if needed. In revise mode, edit the existing files rather than regenerating them: keep wording the user didn't ask to change, and keep phase numbers and names stable, because `/feature-spec` branch and directory names were derived from them.

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
<Architecture style, dependency rules, repo layout, naming and style precedence.>

## Testing and quality gates
<Test strategy (unit / integration / e2e) and the exact gate commands every phase must pass, e.g. `task ci`.>

## Infrastructure and delivery
<Where it runs, how it's built and deployed, environments.>

## Constraints
- <Must-use / must-not-use, platform, licensing, budget>.

## Deferred decisions
- <Decision> - decided in Phase <N> because <why it can wait>.
```

Versions: copy pinned versions from manifests. For a choice not yet in the repo, don't make up a version number. Write `latest stable at adoption` or a deliberate floor the user named. Leave out a section only if it is genuinely empty (e.g. no infrastructure yet), and leave a one-line note saying so.

### `specs/roadmap.md`

The roadmap sets the high-level implementation order, not the design. The detail belongs in each phase's `/feature-spec`. Its phases are **very small**, because each one becomes a single feature spec, one branch, and one reviewable PR. Big phases produce specs nobody can review and PRs nobody can merge.

A phase is small enough when **all** of these hold:
- **One capability.** It delivers one observable thing a user, operator, or developer can do or verify. If the name needs an "and", split the phase.
- **Vertical, not horizontal.** It cuts end to end through whatever layers it needs. "Set up the database" on its own is a layer, not a phase. The exception is the walking skeleton, which is allowed to be mostly plumbing because proving the plumbing is its capability.
- **One PR.** Its `/feature-spec` plan would hold roughly 2-5 task groups, and a reviewer could read the whole change in one sitting.
- **Independently verifiable.** It has a binary "Done when" (a test passes, a command produces an output, a demo works) that doesn't depend on a later phase.
- **Leaves the system working.** After it merges, main builds, passes its gates, and does something it couldn't do before.

Order the phases: **Phase 1 is the walking skeleton** (build, test, and CI gates green, plus the thinnest end-to-end path through the chosen stack). After that come dependencies before dependents, the riskiest assumptions as early as their dependencies allow, and then value. Mark the phase where the MVP is reached.

Keep phase names short (four words at most) and distinctive: `/feature-spec` turns them into kebab-case branch names.

```markdown
# Roadmap

<Two or three sentences: the strategy behind this order, and where the MVP lands.>

Status values: `not started` · `in progress` · `done`. Update a phase's status as its feature spec lands.

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

In revise mode, phases already marked `done` keep their number, name, and text. If the direction changed, adjust or reorder unstarted phases only, and tell the user about any in-progress phase the change affects.

Before moving on, check the files against each other yourself: every goal is served by at least one phase (or appears under `Later`), no phase works against a non-goal, and every technology a phase relies on appears in the stack table. Fix what you find now so codex can spend its review on harder problems.

## Step 4 - Codex review (adversarial review, in a subagent)

Get an independent second-model review through the codex plugin's **adversarial review**. It accepts custom focus text, and plain `review` doesn't. The `/codex:*` slash commands set `disable-model-invocation`, so the subagent runs the companion script those commands wrap, from the repo root:

```bash
ls -d ~/.claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs 2>/dev/null | sort -V | tail -1   # -> <companion>
# Bash tool with run_in_background: true
CODEX_COMPANION_SESSION_ID=constitution-<random> timeout -k 10 660 node "<companion>" adversarial-review --background --scope working-tree -- "<focus>"
CODEX_COMPANION_SESSION_ID=constitution-<random> node "<companion>" status --json   # this launch's job id
node "<companion>" status <job-id> --wait --timeout-ms 240000 --json                 # repeat until finished
node "<companion>" result <job-id>
```

Shell variables don't persist between Bash calls, so substitute the resolved `<companion>` path and the tag literally. Pass each flag as its own argument and `<focus>` as a single argument after `--`, because the companion re-splits a combined string and can mangle it.

`<focus>`:

> Review this project's constitution: specs/mission.md, specs/tech-stack.md, specs/roadmap.md. Also read README.md, CLAUDE.md / AGENTS.md if present, and the repo's build manifests and CI config. Review only these three files; ignore other working-tree changes. Look for: contradictions among the three files or with README.md; mission goals no roadmap phase serves, and phases that serve no goal or work against a non-goal; technologies a phase relies on that are missing from tech-stack.md; tech-stack claims (choices, versions, gate commands) that contradict the repo's actual manifests or CI; roadmap phases that are too large (more than one capability, not shippable as one PR, horizontal layers instead of vertical slices, or a "Done when" that is missing, not binary, or depends on a later phase); phases out of dependency order or risky assumptions left needlessly late; a Phase 1 that isn't a walking skeleton; vague or unmeasurable goals; and gaps that would force a later feature spec to guess. For each finding, output a numbered item with the file, the issue, and the suggested change. Output findings only; do not rewrite the files.

Rules for the subagent:
- **Capture** the result verbatim to `/tmp/codex-constitution-<repo-dirname>.md`, so Step 5 can be audited, and return the findings. Never write the scratch file inside the repo.
- **Deadline.** Allow 10 minutes from launch. The job has stalled if its `pid` is dead while status still says running, or if its `logFile` has been silent for 5 minutes. On a stall or the deadline, `cancel <job-id>` and return `codex failed: <reason>`.
- **No companion, or not a git repo** (`--scope working-tree` needs git): fall back to `timeout -k 10 600 codex exec --sandbox read-only --skip-git-repo-check -o /tmp/codex-constitution-<repo-dirname>.md "<focus>" < /dev/null`. The `< /dev/null` matters: without a terminal on stdin, `codex exec` waits on it until the timeout kills it. A non-zero exit or an empty output file means `codex failed`.

If codex fails, don't skip the review silently. Tell the user and `AskUserQuestion` with these options: **retry the codex review**, **substitute a self-review** (one or two adversarial `general-purpose` subagents given the same focus text, whose findings go through Step 5 the same way), or **skip the review**. The report names the option taken.

## Step 5 - Validate the findings and finalize

Codex's comments are hypotheses, not instructions. For each numbered finding:

1. Re-read the cited passage and confirm the problem is real. Discard hallucinated quotes, and findings about files or lines that don't exist.
2. Check it against the settled decisions. A finding that only disputes a decision the user made is **rejected**, however plausible it sounds. A finding showing that a decision rests on a wrong fact, or is unsafe, goes back to the user (below).
3. Check factual claims against the repo (manifests, CI, the survey) rather than taking codex's word or your own memory.
4. Give it a disposition:
   - **accept** - a real gap, contradiction, or oversized phase; edit the file(s).
   - **reject** - wrong, already handled, or contradicts a user decision; say why.
   - **defer** - valid but not constitution-level (it belongs in a phase's feature spec), or it needs a user decision that can wait; say where it goes.

Apply accepted findings, keeping each edit traceable to its finding number. If an accepted finding would change a settled decision (a new non-goal, a different stack choice, a reordered MVP), don't edit on your own. Reopen that branch of the design tree with the grilling skill, get the user's answer, update the decision list, and then edit.

Splitting an oversized phase into smaller ones is a normal accept, not a decision change, unless the split moves the MVP line or changes what an in-progress phase covers.

After the edits, re-run the Step 3 cross-file check, since fixes in one file often leave another stale.

## Step 6 - Report

Leave the three files uncommitted. Report:
- The three file paths, each with a one-sentence summary, plus the phase count and the MVP phase.
- In revise mode: what changed in each file, and which phases kept their `done` / `in progress` status.
- The codex outcome: total findings and the accept / reject / defer breakdown, with a one-line reason for each rejection and a destination for each deferral (or which Step 4 fallback was used and why).
- Any README/code disagreements the user resolved, if the README now needs updating to match.
- Next step: review and commit the files, then run `/feature-spec` to spec Phase 1 (or the next unstarted phase).
