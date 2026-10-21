---
name: why
description: "Trace why code has its shape (design rationale, past tradeoffs, regressions, threshold origins) with a cited, confidence-tiered answer drawn from design records, git/PR history, tickets, docs, chat, and telemetry."
disable-model-invocation: true
---

# Why

Investigate the motivation and intent behind code: what forces led to its shape. Answering what the code does at runtime is a different job; read the code for that.

Ported from the pstack `why` skill (`cursor/plugins` at `ce649c03`, MIT, see `LICENSE`), adapted for Claude Code and for repos that record rationale in ADRs and per-ticket specs.

## Operating Posture

Operate as a **careful, cautious, and precise investigator**. Be honest about what you know vs what you're inferring. Read `references/epistemics.md` for the confidence framework and phrasing guide. The synthesizer must follow it.

Every agent in this skill is **read-only**: it searches, fetches and reads, and leaves every system exactly as it found it.

## Step 1. Understand the Target and the Question

The **target** is usually a chunk of code, a pattern, a feature, or a named design decision. The **question** is usually a design rationale, a tradeoff, a motivating edge case, an external constraint, dead code, or a broad history sweep.

If the target is vague, make your best guess from conversation context (open files, recent edits, what was just discussed). State your interpretation in one line so the user can redirect, then proceed.

## Step 2. Establish the Code Anchor

Build the seed context inline: file paths and line ranges, key symbols, the commits touching the target, their PR numbers, and their ticket keys.

```bash
git blame -L <start>,<end> <file>          # last-touch commits
git log --follow --oneline -20 -- <file>   # recent history through renames
git log -1 --format=%B <commit>            # full message of one commit
gh pr list --state merged --search <sha> --json number,title   # PR for a commit with no (#N) suffix
gh pr view <number> --json title,body,author,createdAt,mergedAt,labels,closingIssuesReferences,commits,comments,reviews
```

- **PR numbers**: squash-merge subjects end in `(#1234)`.
- **Ticket keys**: subjects and branch names often start with a key such as `APP-1234:`; match `[A-Z][A-Z0-9]+-[0-9]+`.
- **Squash flattening**: a squash commit hides the branch's own commits. Read the PR's `commits` list for the step-by-step story.

The anchor is done when every commit that shaped the target lines has its PR and ticket key recorded, or a note that it has none.

## Step 3. Read the Design Records

Read the repo's own rationale inline before spawning anyone, because it is the strongest and cheapest evidence:

- **ADRs**: find the directory (`specs/adr/`, `docs/adr/`, or `rg -l -i 'architecture decision' --glob '*.md'`), then `rg -l` the target's symbols, package names and file paths across it. Note each hit's `Status:` and follow any supersession link to the current record.
- **Per-ticket specs**: for each ticket key from Step 2, read a matching `specs/<KEY>/` (plan, requirements, validation) if present.
- **Other in-repo docs**: `CLAUDE.md`, `docs/`, and `CHANGELOG.md` lines that name the target.

Add every hit, quoted with its path, to the anchor.

## Step 4. Choose the Depth

Answer inline (skip Steps 5 to 7) only when all three hold:

1. A design record from Step 3 states the rationale for this specific target in its own words (Direct tier).
2. Its status is accepted or validated, and the code still matches it.
3. The question is about design intent, not a regression, incident, or the origin of a number.

An inline answer still uses the Output Format, lists every category it did not search as "Not searched: answered directly by <record>", and offers the full investigation in one line. Otherwise run the full investigation: document the null, don't skip the search.

## Step 5. Discover the Sources

Map the tools this session has to the seven evidence categories in `references/source-playbook.md`. Read the tool names in context, including deferred tools listed in system reminders (load a deferred tool's schema with `ToolSearch` before calling it). One MCP can serve two categories (Atlassian covers both the ticket tracker and long-form documents); give each category its own investigator.

- A plugin that exposes only `authenticate` / `complete_authentication` is **not signed in**. Record it as a gap and tell the user which one to sign in to; leave sign-in to the user.
- For Atlassian, resolve the `cloudId` once with `getAccessibleAtlassianResources` and pass it to both investigators. Read the `scopes` it returns: a product with no matching read scope (no `*jira*` scope for Jira, no `*confluence*` scope for Confluence) is **not usable**. Record it as a gap naming the missing scope, and spawn no investigator for it.
- Source control is always available through git and `gh`.

## Step 6. Spawn Parallel Investigators

Spawn one investigator per category that has a usable source, all in a single message so they run concurrently, each owning exactly one category: `Agent` with `subagent_type: "general-purpose"` and `model: "sonnet"`.

Each investigator's prompt is `references/investigator-prompt.md` filled in, plus:
- the category playbook from `references/sources/` (index: `references/source-playbook.md`)
- `references/sources/incident-postmortem.md` **if the target code looks defensive** (null checks, retry logic, timeout handling, rate limiting, feature flags, egress guards, OOM handlers)
- the code anchor, the design-record quotes, and the user's original question

Wait for every investigator's completion notification before Step 7.

### When to skip an investigator

Only with an **explicit, written justification** that goes in the final Sources Consulted. Two valid reasons:

- **No usable source** for that category in this session (missing, or not signed in). Flag it as a gap, not a choice.
- **The source is provably irrelevant**, not just "probably irrelevant." A high bar: "Error tracking skipped. Target is a build-time script with no runtime code path."

## Step 7. Synthesize

Spawn one synthesizer: `Agent` with `subagent_type: "general-purpose"` and no `model` override. It gets:
1. The investigator findings, including null results and skipped categories with reasons
2. The code anchor and the design-record quotes
3. The user's original question
4. `references/epistemics.md`
5. `references/synthesizer-prompt.md`

## Step 8. Present

Present the synthesizer's output to the user. You may lightly edit for clarity or add context from the conversation, but **keep the confidence language as written**.

## Output Format

The structure in `references/synthesizer-prompt.md`: The Question, The Code in Question, What We Found, What We Can Reasonably Infer, Competing Hypotheses, What We Don't Know, Sources Consulted, Confidence Summary. Keep the confidence separation intact, and keep Sources Consulted as one line per category, including the ones that returned nothing or were skipped, with the reason.

If the `why` question is a precursor to changing this code, end with a Preserve / Change / Avoid / Risk constraint set derived from the findings.

## Common Failure Modes

- **Recency bias.** The most recent commit is rarely the whole story. The current shape is often the accretion of many earlier decisions. Trace back.
- **Record drift.** An ADR or spec states intent at the time it was written. Check its status, later supersessions, and whether the code still matches before treating it as the answer.
