---
name: sync-spec-ticket
description: Apply a requested change to a feature's spec files under specs/<name>/ AND to the Jira ticket (title + description) associated with that spec, keeping the two in sync. Takes the spec target (a branch name, a specs/<name>/ path, or the current branch) plus a description of the change to make, and optionally the Jira ticket key. Resolves the spec directory, identifies/confirms the Jira ticket (input key, else Jira search, else ask), edits the spec files, drafts the matching Jira title/description, runs codex (OpenAI Codex CLI) headlessly to review the spec diff and the drafted ticket text for consistency, validates every codex finding before acting, folds accepted findings into both the files and the ticket draft, and pushes a single confirmed Jira update. Uses general-purpose subagents for the codex run and finding adjudication, and AskUserQuestion for every clarification and the outward-facing Jira write. Invoke manually when a spec changed and its tracking ticket must follow (or vice versa).
---

# Sync spec ↔ ticket skill

Apply one requested change consistently across **two surfaces**: the planning docs under `specs/<name>/` and the **Jira ticket** that tracks that work (its title and description). The change can originate from either side — a spec edit that the ticket must reflect, or a ticket-text revision the specs must absorb. Output is: the edited spec files, a confirmed Jira title/description update, the raw codex review, a per-finding disposition table (accept / reject / defer with evidence), and the corrective edits folded into both surfaces.

The repo does **not** store a spec→ticket mapping (the `SEC-1`/`EVAL-3`-style tokens in the specs are internal requirement IDs, not Jira keys). The ticket is therefore supplied as input, discovered by search, or asked for — never assumed.

If the repo has a `CLAUDE.md`, read it first — it is authoritative for conventions and wins over any codex suggestion that contradicts it.

## Two identifiers, one input

- `<spec-target>` — what to edit. Accept a branch name (`specs/2026-06-08-discovery-artifacts` or the bare `2026-06-08-discovery-artifacts`), a `specs/<name>/` directory path, or nothing (fall back to the current branch). Resolve it to a concrete `specs/<name>/` directory in Step 0.
- `<ticket-key>` — the Jira issue to update (e.g. `CAR-42`). Supplied as input, else resolved in Step 2.

## Subagent delegation

Run the expensive, self-contained steps in a **`general-purpose` subagent** (via the `Agent`/`Task` tool), and keep orchestration in the main loop. The split is fixed:

- **Main loop owns** (never delegate): the spec-target resolution (Step 0), the change-intent gathering (Step 1), every `AskUserQuestion` gate (ticket confirmation in Step 2, ambiguous/scope-changing fixes in Step 6, the final Jira-write confirmation in Step 7), **writing the spec files** (Step 3 and the Step 6 corrections — they depend tightly on the gathered intent), **the `editJiraIssue` write** (Step 7 — an outward-facing, hard-to-reverse action), and the Step 8 report. Subagents cannot prompt the user and must never push to Jira.
- **Delegate to a `general-purpose` subagent** (each returns a compact result, keeping verbose output out of the main context):
  - **Step 5** — run the `codex exec --sandbox read-only …` review of the spec diff plus the drafted ticket text and return the raw findings verbatim (also written to the scratch file). The codex transcript stays in the subagent.
  - **Step 6** — hand the findings plus the Step 1 intent and the project rules to a subagent that adjudicates each finding against the actual changed files and returns the accept/reject/defer disposition table with evidence. The main loop applies the edits and owns any follow-up question.

Give each subagent a self-contained prompt: the exact command(s) to run, the spec file paths and ticket draft, and the precise shape of the result to return. Serialize the chain (Step 5 → 6); the rest is main-loop work.

## Step 0 — Resolve the spec target

Resolve `<spec-target>` to a concrete `specs/<name>/` directory:

- If a `specs/<name>/` path or a branch name was given, strip any leading `specs/` to get `<name>` and check that `specs/<name>/` exists.
- If nothing was given, derive `<name>` from the current branch: `git rev-parse --abbrev-ref HEAD`, strip the leading `specs/`. If the current branch is not under `specs/`, or the derived directory does not exist, **stop and ask** (AskUserQuestion) which spec to operate on — list the `specs/*/` directories as options.
- If the resolved directory does not exist or holds no `.md` files, stop and ask the user to confirm the target.

Record the spec file list (typically `requirements.md`, `plan.md`, `validation.md`, plus any extras like `mttr-baseline.md`) — it is the edit scope for everything below.

## Step 1 — Gather the change intent

Establish exactly *what* to change before touching anything. In parallel, read the resolved spec files and (if present) `specs/roadmap.md`, `specs/mission.md`, `specs/tech-stack.md`, and `CLAUDE.md` for the constraints the edit must respect.

- If the user's invocation already states the change clearly, restate it back in one line and proceed.
- If the change is vague or could be applied several ways, call `AskUserQuestion` **once** to pin it down — scope of the edit, which files/sections it touches, and any decision the change hinges on. Tailor options to what the specs actually contain; generic options are useless.

Decide the change's **origin**: spec-led (specs are the source of truth; the ticket must mirror them) or ticket-led (a ticket revision must flow into the specs). This sets which surface seeds the other in Steps 3–4.

## Step 2 — Identify and confirm the Jira ticket

Resolve `<ticket-key>` in this order, and **always confirm before editing**:

1. **Input key given** — fetch it (`mcp__claude_ai_Atlassian__getJiraIssue`) and confirm the summary matches this spec via AskUserQuestion (show the current summary).
2. **No key** — search Jira for candidates (`mcp__claude_ai_Atlassian__searchJiraIssuesUsingJql`) using terms from the spec's `requirements.md` title/context and the feature `<name>`. Present the top matches as AskUserQuestion options (issue key + summary each); include an "Enter a different key" path. Use `getAccessibleAtlassianResources` / `getVisibleJiraProjects` first if the cloud id or project is unknown.
3. **No confident match** — ask the user for the ticket key directly. Do not invent or guess a key.

Once confirmed, fetch the ticket's **current** title and description and record them — they are the before-state for the Step 7 diff. If the user explicitly says no ticket exists yet, stop and ask whether to create one (`createJiraIssue`) or skip the Jira side entirely; do not create tickets unprompted.

> The MCP Atlassian tools are deferred — load their schemas with `ToolSearch` (e.g. `select:mcp__claude_ai_Atlassian__getJiraIssue,mcp__claude_ai_Atlassian__editJiraIssue,mcp__claude_ai_Atlassian__searchJiraIssuesUsingJql,mcp__claude_ai_Atlassian__getAccessibleAtlassianResources,mcp__claude_ai_Atlassian__getVisibleJiraProjects`) before calling them — including the accessible-resources and visible-projects lookups Step 2 uses when the cloud id or project is unknown. If the Atlassian MCP server is not connected or auth fails, tell the user and use AskUserQuestion to offer alternatives (retry after they connect it, proceed with the spec edits only, or abort) — never silently skip the Jira side.

## Step 3 — Apply the spec edits

Edit the resolved spec files to implement the Step 1 intent (skip if the change is purely ticket-led and the specs already match — note that). Keep edits minimal and consistent with the surrounding doc style. Do **not** commit. Preserve the cross-file consistency the specs already maintain (scope items in `plan.md` mirrored in `requirements.md`, validation criteria that actually verify the requirements).

Capture the spec diff (`git diff -- specs/<name>/`) — it is the review subject and the basis for the ticket draft.

## Step 4 — Draft the matching Jira title and description

From the now-updated specs (spec-led) or from the Step 1 ticket revision (ticket-led), draft the **new** ticket title and description:

- **Title** — concise, reflecting the feature/phase as the specs now describe it.
- **Description** — mirror the spec's context, scope (in/out), key decisions, and the "done when" / validation signal. Match the format the ticket already uses (note whether the instance expects Atlassian Document Format vs. wiki markup vs. plain text — preserve whatever `getJiraIssue` returned).

This is a **draft only** — hold it in the working notes. Nothing is pushed to Jira until Step 7. Drafting before review (rather than pushing now) keeps the live ticket out of a half-corrected state if codex surfaces a real problem.

## Step 5 — Codex review of the changes

Get an independent second-model review of both surfaces together. Delegate to a `general-purpose` subagent that runs codex headlessly from the repo root over the changed spec files, and also feeds it the drafted ticket text:

```bash
codex exec --sandbox read-only "<instructions>"
```

With `<instructions>`:

> Review these changed planning documents: specs/<name>/*.md (focus on the working-tree diff). Also read specs/roadmap.md, specs/mission.md, specs/tech-stack.md, and CLAUDE.md if present — the edits must stay consistent with them. Separately, here is the drafted Jira ticket title and description that must match the updated specs: "<title>" / "<description>". Review for: internal contradictions introduced by the edit, scope items now in one file but missing from the others, validation criteria that no longer verify the stated requirements, the drafted ticket text disagreeing with the updated specs (missing scope, wrong done-criterion, stale title), and conflicts with the roadmap/mission/tech-stack. For each finding output a numbered item with: surface (spec file:section or ticket-title/ticket-description), the issue, and the suggested change. Output findings only — do not rewrite anything.

- Capture stdout verbatim to a scratch file (e.g. `/tmp/codex-sync-<name>.md`) so Step 6 is auditable. Do **not** commit it.
- If `codex` is unavailable or errors, verify flags against `codex exec --help`; if it still fails, tell the user and use AskUserQuestion to offer alternatives (retry, substitute a self-review pass, or proceed without the codex review).

## Step 6 — Validate the findings and fold them into both surfaces

Do **not** apply codex's comments blindly — they are hypotheses to adjudicate. Delegate the adjudication to a `general-purpose` subagent, then act on its table in the main loop. For each numbered finding:

1. Re-read the cited spec passage or ticket-draft line and confirm the issue is real.
2. Check it against the Step 1 intent — a finding that contradicts a change the user explicitly asked for is **rejected**, however plausible.
3. Check it against `CLAUDE.md` / `roadmap.md` / `mission.md` / `tech-stack.md`.
4. Mark a disposition:
   - **accept** — real gap, contradiction, or spec↔ticket mismatch; fix the affected surface.
   - **reject** — factually wrong, restates a deliberate choice, or contradicts the user's intent; note why with a citation.
   - **defer** — valid but out of scope for this change or needs a user decision; note where it belongs.

Apply accepted findings: edit the spec files for spec-surface findings, and revise the held ticket **draft** for ticket-surface findings — keeping the two consistent (a spec fix usually implies a matching ticket-draft fix). Keep each edit traceable to its finding number. If an accepted finding would change a decision the user made in Step 1 (widen scope, swap an approach), do **not** edit — surface it via AskUserQuestion first. Present the full disposition table to the user.

## Step 7 — Confirm and push the single Jira update

Show the user the **before → after** of the ticket title and description (the before-state from Step 2, the final draft from Steps 4/6) and confirm via `AskUserQuestion` before writing — this is an outward-facing change to a live system. Offer: push the update, edit the draft further, or skip the Jira write (leave only the spec edits).

On approval, push exactly one update with `mcp__claude_ai_Atlassian__editJiraIssue` (load its schema via `ToolSearch` first). Use the cloud id and issue key from Step 2 and the format the instance expects. Pushing once, after review and confirmation, avoids churning the ticket's history with intermediate states. If the write fails, report the error and the intended payload — do not retry blindly or leave the user thinking it succeeded.

## Step 8 — Report

State:

- **Spec target** — which `specs/<name>/` files were edited and the one-line intent.
- **Ticket** — the key, how it was identified (input / search / asked), and the before→after title.
- **Codex findings** — total count and the accept/reject/defer breakdown, with one-line reasons for rejections (or that the review was skipped and why).
- **What changed** — spec edits and the Jira update, each mapped to its finding number where applicable.
- **Jira write** — pushed, skipped (and why), or failed (with the error).

Do **not** commit the spec edits — leave them for the user to review and commit. The Jira write is the only thing that lands live, and only after explicit confirmation.

## Stop-and-ask conditions (use AskUserQuestion; do not silently proceed)

- The spec target cannot be resolved or is ambiguous (Step 0).
- The change intent is vague or multi-valued (Step 1).
- No confident Jira ticket match, or the matched summary doesn't fit the spec (Step 2).
- The Atlassian MCP server is unavailable or auth fails (Step 2).
- `codex` is unavailable or its review errors (Step 5).
- An accepted finding would change a user decision or is invasive (Step 6).
- Always before the `editJiraIssue` write (Step 7).
