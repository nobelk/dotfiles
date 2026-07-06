---
name: jira-planner
description: Translate an architecture design document into an executable, milestone-driven Jira delivery plan (Milestones → Epics → User Stories) sized for a team of 3-4 engineers on 2-week sprints, then publish it to a Jira board. Takes the path to the architecture design document as the first argument (asks via AskUserQuestion if omitted or ambiguous) and an optional target Jira project key as the second argument (resolved via AskUserQuestion before publishing if omitted). Analyzes the current codebase — fanned out across parallel general-purpose subagents, one per component cluster — to mark already-implemented stories, epics, and milestones as completed (with defined roll-up rules), assigns stable IDs (M1, M1-E1, M1-E1-S1) for dependency references, includes cross-cutting epics (CI/CD, observability, security, testing, production readiness), and writes the plan to jira_plan.md in the current directory (updating an existing plan in place: stable IDs are preserved; statuses are re-derived from the codebase, with manual-status conflicts flagged). After writing, runs `/codex:adversarial-review --background` on jira_plan.md, validates each finding, and folds accepted findings back into the plan — routing scope/product decisions through AskUserQuestion. Finally, after explicit user confirmation, creates the epics, stories, issue links, and blockers on the target Jira board via the Atlassian MCP tools and writes the plan-ID → Jira-key mapping back into jira_plan.md. Never invents ungrounded requirements — inferences are labeled "Assumption:" and gaps are listed under "Clarifications Needed". Invoke manually when an architecture/design doc is ready to be broken down into a Jira delivery plan, or to refresh an existing plan against the codebase.
---

# Jira planner skill

Act as a senior technical program manager translating an architecture design document into an executable Jira delivery plan for a development team of 3-4 software engineers. The flow is: plan → write `jira_plan.md` → codex review with validated findings folded back in → publish the plan to a Jira board. The plan file is reconciled against what the current codebase already implements.

## Subagent delegation

Run the expensive, self-contained steps in **`general-purpose` subagents** (via the `Agent`/`Task` tool) and keep orchestration in the main loop:

- **Main loop owns** (never delegate): every `AskUserQuestion` gate, writing/editing `jira_plan.md`, and all Jira writes in Step 7 — subagents cannot prompt the user, and outward-facing writes need the main loop's confirmation gates.
- **Delegate**: the Step 2 codebase analysis, the Step 6 codex run, and the Step 6 finding adjudication. Give each subagent a self-contained prompt with exact commands, file paths, and the precise result shape to return.

**Parallelize by default.** When delegated tasks have no data dependency, dispatch them as multiple `Agent`/`Task` calls in a **single message** so they run concurrently — never run independent subagents one at a time across turns. Concretely: **Step 2 fans out** — for a non-trivial codebase, split the Step 1 component/capability list into clusters and launch one analysis subagent per cluster in one message (each returns its slice of the implemented/partial evidence list; the main loop merges them). **Step 6 adjudication fans out** — split the codex findings into disjoint batches and adjudicate them in parallel subagents, keeping contradictory findings in the same batch. The Step 6 codex run → adjudication → apply path is otherwise a serial chain. **Step 7 Jira writes never parallelize**: issue creation is outward-facing and dependency-ordered (epics before stories before links), so it stays strictly sequential in the main loop. Parallel subagents are read-only — none of them writes `jira_plan.md` or touches Jira.

## Step 0 — Resolve inputs

The skill accepts up to two whitespace-separated arguments: `<architecture-doc-path> [jira-project-key]`. If a path contains spaces, the user should quote it. A second token matching a Jira project key pattern (`^[A-Z][A-Z0-9_]*$`, e.g. `PLAT`) is the target Jira project; anything else is a malformed invocation to clarify with the user.

- If a document path is provided, verify the file exists and is readable. If not, stop and ask the user for the correct path — do not guess.
- If no argument is provided, look for likely candidates (e.g. `docs/`, `specs/`, `*.md` files whose name or heading suggests an architecture/design doc). If exactly one strong candidate exists, confirm it with the user via `AskUserQuestion`; if several or none, ask the user to pick/supply the path.
- If the Jira project key is omitted, do not block here — resolve it in Step 7.
- The output path is always **`jira_plan.md` in the current working directory**.
- If `jira_plan.md` already exists, use `AskUserQuestion` to ask whether to **overwrite**, **update in place**, or **abort**.
  - **Update in place** means: read the existing plan first; keep the stable IDs of items whose scope is unchanged (never renumber surviving items — new items get the next free ID within their parent); re-derive every Status from the fresh Step 2 codebase analysis, but never downgrade an item the user manually marked completed without flagging it in the Step 8 report; preserve any existing plan-ID → Jira-key mapping table so already-published items are updated rather than duplicated in Step 7; carry forward still-open "Clarifications Needed" entries and drop resolved ones; regenerate all other content from the current architecture doc.

## Step 1 — Read the architecture document in full

Read the entire document before planning. Identify:

- All components, services, and modules
- Integrations and external dependencies (third-party services, other teams)
- Data flows and data models
- Non-functional requirements (performance, security, availability, observability)
- **Implicit work** the document assumes but does not state: testing, observability, deployment/CI-CD, security and secrets management, data migration, documentation, production readiness

If the document is too large to read at once, read it in sections — never plan from a partial read.

## Step 2 — Analyze the current codebase (project status)

Analyze the code in the current directory to identify features that are **already implemented**. Delegate this to **`general-purpose` subagents** when the codebase is non-trivial: split the components/integrations/flows extracted in Step 1 into clusters (by subsystem or directory) and launch **one subagent per cluster in a single message so they run in parallel** — wall-clock time is the slowest cluster, not the sum. Give each a self-contained prompt naming only its cluster's components and require this exact return shape: a markdown list where each entry is `<capability> — implemented | partial — <file:line references> — <one-line evidence>`. For a trivially small codebase (a handful of files), read it directly in the main loop instead.

This analysis feeds the Status fields in Steps 3 and 5, using three values: **✅ Completed**, **🔶 Partially completed**, and blank (not started).

- **Story status**: ✅ if the story's scope is fully implemented (cite the implementing code in one line), 🔶 if partially (note what remains), blank otherwise.
- **Epic status (roll-up)**: ✅ if all of its stories are ✅; 🔶 if at least one story is ✅ or 🔶 but not all ✅; blank if no story has started.
- **Milestone status (roll-up)**: same rule applied over its epics.

## Step 3 — Build the plan structure

Produce a milestone-driven plan with three levels: **Milestones → Epics → User Stories**.

### 3.1 Milestones

Organize the work into 3-6 sequential milestones, each a meaningful, demoable increment of value (e.g. "M1: Foundational Infrastructure & CI/CD," "M2: Core Service MVP," "M3: External Integrations," "M4: Production Hardening"). For each milestone provide:

- Milestone name and one-sentence goal
- Exit criteria (what must be true to consider it done)
- Approximate duration in sprints, assuming 2-week sprints and 3-4 engineers working in parallel
- Key risks and dependencies
- Status: per the roll-up rule in Step 2

### 3.2 Epics (standard Jira format)

Each milestone contains 2-5 epics, sized so 3-4 engineers can complete one in roughly 2-4 sprints. For each epic provide:

- Epic Title (short, outcome-oriented)
- Epic Summary (1-2 sentences)
- Business / Technical Value (why this matters)
- Scope: In / Out (bullet list each)
- Success Criteria (measurable)
- Dependencies (other epics, external teams, third-party services)
- Assumptions
- Labels / Components (suggested)
- Status: per the roll-up rule in Step 2

### 3.3 User Stories (standard Jira format, large-grain)

Each epic contains 3-8 large-grain user stories. "Large-grain" means each story represents roughly 3-8 engineer-days — meaningful vertical slices, not tasks. Do not decompose to the sub-task level. For each story provide:

- Story Title
- User Story statement: "As a `<persona>`, I want `<capability>`, so that `<benefit>`." Use realistic personas drawn from the architecture (end user, admin, downstream service, on-call engineer, etc.), not just "As a developer."
- Description / Context (2-4 sentences tying it to the architecture)
- Acceptance Criteria in Given/When/Then format, 3-6 per story, covering happy path, key edge cases, and relevant non-functional requirements (performance, security, observability)
- Technical Notes (APIs, data models, libraries, or design decisions from the architecture doc)
- Dependencies (other stories by ID)
- Suggested Story Points on a Fibonacci scale (1, 2, 3, 5, 8, 13) calibrated for a mid-level engineer
- Definition of Done checklist items beyond the AC (tests, docs, monitoring, code review, deployed to staging)
- Status: **✅ Completed** / **🔶 Partially completed** / (blank = not started), per the Step 2 codebase analysis

## Step 4 — Constraints and quality bar

- Assign stable IDs: `M1`, `M1-E1`, `M1-E1-S1`, etc., so dependencies can be referenced cleanly.
- Sequence work to respect technical dependencies; explicitly flag anything that blocks parallelization by 3-4 engineers.
- Include cross-cutting epics the architecture implies but does not always state: CI/CD setup, observability (logs/metrics/traces), security and secrets management, testing strategy, performance/load testing, documentation, production readiness.
- Do not invent requirements not grounded in the document; when you must infer, label it "**Assumption:**" and state why.
- If the document is ambiguous or missing information needed to plan (SLAs, data volumes, auth model, deployment target, etc.), list open questions under "Clarifications Needed" at the end rather than guessing silently.
- Keep language crisp and ticket-ready — an engineer should be able to pick up any story and start work without the architecture doc to disambiguate intent.

## Step 5 — Write jira_plan.md

Write the plan to `jira_plan.md`, in this order:

1. **Executive Summary** (5-8 bullets)
2. **Milestone Overview table** (ID, name, goal, sprints, status)
3. **Detailed Milestones / Epics / Stories** (full fields per Step 3, with completion status per Step 2)
4. **Cross-Milestone Dependency Map**
5. **Clarifications Needed**
6. **Jira Mapping** (plan ID → Jira issue key/URL; empty until Step 7 runs, preserved across update-in-place runs)

## Step 6 — Codex review of the plan

Have codex (OpenAI Codex CLI) review `jira_plan.md`, then validate and address its comments:

1. **Run the review in a `general-purpose` subagent**: launch `/codex:adversarial-review --background` targeting `jira_plan.md` (review focus: completeness against the architecture doc, dependency/sequencing correctness, epic/story sizing, ID stability and referential integrity, ticket-readiness of acceptance criteria, and whether completion statuses are plausible given the codebase evidence). The subagent polls `/codex:status` to completion, fetches `/codex:result <job-id>`, and returns the raw findings verbatim.
2. **Adjudicate each finding in parallel**: split the findings into disjoint batches (one per plan section, or ~3–5 findings each) and launch one adjudication subagent per batch **in a single message**. Each returns an accept/reject/defer disposition table with one-line evidence per finding, validated against the architecture doc and the Step 2 codebase analysis — codex comments are input, not orders. If two findings contradict each other, put them in the same batch so one subagent resolves the conflict.
3. **Apply accepted findings** to `jira_plan.md` in the main loop. Any finding that requires a scope, priority, or product decision — or whose validity you cannot determine from the documents — goes to the user via `AskUserQuestion`; never guess silently.
4. If codex is unavailable or the review fails, say so explicitly and use `AskUserQuestion` to ask whether to proceed to Step 7 without the review or stop.

## Step 7 — Create the Jira issues on the board

Publish the plan to Jira using the Atlassian MCP tools (`mcp__claude_ai_Atlassian__*`; load them via ToolSearch first if deferred). If the Atlassian MCP server is not connected, stop and tell the user — do not attempt REST calls with guessed credentials.

1. **Resolve the target project**: use the Step 0 project key if given; otherwise call `getVisibleJiraProjects` and present the candidates via `AskUserQuestion`. Verify the key exists before proceeding.
2. **Discover project metadata**: fetch the project's issue types (`getJiraProjectIssueTypesMetadata`) and available link types (`getIssueLinkTypes`). If the project has no Epic issue type, or milestones need representing, use `AskUserQuestion` to decide the mapping (e.g. milestones as labels `M1`/`M2` vs. fixVersions; epics as another container type).
3. **Confirm before writing** — this is an outward-facing, hard-to-reverse action. Present a summary via `AskUserQuestion`: target project, number of epics/stories/links to create, and how to handle ✅/🔶 items (skip, create-and-transition-to-Done, or create as open). Do not create anything until the user confirms.
4. **Create in dependency order**:
   - Epics first (`createJiraIssue`), recording each plan ID → Jira key as you go.
   - Stories next, linked to their parent epic, carrying over the story statement + description + acceptance criteria + technical notes into the issue description, story points where the project supports them, suggested labels, and the plan ID (as a label like `plan-M1-E1-S1` or in the description) for traceability.
   - Links last: for every dependency in the plan, create an issue link (`createIssueLink`) using the project's "Blocks" link type (blocker blocks blocked); fall back to the closest available type from `getIssueLinkTypes` and note any substitution in the report.
   - If the plan's Jira Mapping table already has a key for an item (update-in-place rerun), update that issue (`editJiraIssue`) instead of creating a duplicate.
5. **Record the mapping**: after each successful create, append the plan ID → Jira key/URL to the Jira Mapping section of `jira_plan.md`. If a creation fails mid-run, stop, keep the mapping of everything created so far, and report exactly what exists on the board and what remains.

## Step 8 — Report

Tell the user: the `jira_plan.md` path; milestone/epic/story counts; how many items were marked completed/partially completed from the codebase analysis; the codex findings disposition (accepted/rejected/deferred counts); the Jira keys created or updated (with the target project), link count, and any link-type substitutions or failures; the number of open clarifications; and — when updating in place — any items whose existing manual status conflicted with the fresh codebase analysis. Do not paste the whole plan into the chat.
