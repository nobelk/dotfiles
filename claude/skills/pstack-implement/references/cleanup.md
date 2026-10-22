# Cleanup rules (deslop, comments, prose)

Adapted from pstack `no-comments`, Comment Sicko, `unslop`, and the Opening a PR playbook in `cursor/plugins` (commit `eb4db2b`, MIT, copyright Lauren Tan; see `PSTACK-LICENSE`). pstack's `/deslop` ships in a separate plugin; the code rules below stand in for it.

## Code slop (deslop)

Remove from the branch diff, and only from lines this branch added or changed:

- Narrating comments and phase banners (`// Step 1: load`, `// now we validate`).
- Commented-out code.
- Guards, try/catch blocks, nil checks, and fallbacks for states the types or the boundary already rule out.
- Dead compatibility paths, unused parameters, unused imports, debug prints, stray TODOs.
- One-caller wrappers and pass-through helpers that add a layer without hiding anything.
- Edits unrelated to the spec (drive-by reformatting, renames outside scope).

A verify or test script narrates nothing. Its assertion and log strings name the step, as in `assert(ok, 'persisted across restart')`.

## Comments (no-comments reviewer)

Comments are judged by a fresh subagent that did not write them. It reports and edits only comments; it never writes application code. Only these comments survive:

- Legal or license headers.
- Non-obvious behavior forced by an external dependency, platform, vendor, or protocol that this repo cannot reshape.
- `prettier-ignore`-style directives, and lint suppressions whose rule is faulty, pedantic, or style-only.
- Doc comments that define a public API contract, and doc comments the repo's own rules require.
- Issue or RFC links that explain a constraint the code cannot express.

Everything else goes. A surprise in this repo's own code is not a keep: delete the comment and flag the exact symbol `MUST KILL` with the reshape that makes the behavior obvious (rename, extract, type, restructure). A suppression that hides a real correctness or safety rule is a `MUST KILL` too. `IMPORTANT`, `do not remove`, and long justifications are a scent: read the code they guard and keep the comment only when a keep clause is proven true today. When in doubt, the comment dies.

The main loop then inspects the report: rejects any edit outside comments or outside scope, fixes accepted `MUST KILL` flags at the root cause within scope, and reports the rest open. When a comment states a real constraint ("do not change wording"), encode it as a type, test, or lint when that is cheap and in scope, then delete the comment.

## Prose (unslop and technical writing)

Applies to commit bodies, the PR title and body, spec checkbox notes, and the final report.

- Short declarative sentences, one idea each. Active voice with a named actor.
- No em dashes. No colon as a mid-sentence connector; a colon before a list is fine.
- Plain words: "use" not "leverage", "is" not "serves as", "help" not "facilitate".
- No AI vocabulary (crucial, delve, enhance, pivotal, robust, seamless, showcase, underscore, landscape), no "not just X but Y", no forced groups of three, no superficial "-ing" tails ("ensuring...", "highlighting...").
- No chatbot phrases, hedging stacks, generic conclusions, decorative emoji, or bold on every noun.
- Say what the code does, with a mechanism or a number, not how it feels.
- Write whole sentences with articles. No arrows or invented abbreviations.
- Every claim carries its evidence or its label in the same sentence: measured, inferred, or guess.

## PR title and body

Title: Conventional Commits `type(scope): subject`, imperative, no trailing period, naming the real symbol when one carries the change. The repo's own convention wins when it differs.

Body: a one-minute briefing for a reviewer who has the diff, under about 40 lines. `##` headings in this order; drop a section with nothing to say:

- `## Why`: the problem and approach, 1 to 3 sentences. Link the spec directory.
- `## What changed`: 1 to 3 bullets, one per task group or theme.
- `## Scope`: always. What it covers and what it deliberately leaves out (deferred findings, inconclusive checks).
- `## Tradeoffs`: only rejected alternatives a reviewer would ask about.
- `## Blast Radius`: 1 to 2 sentences on who or what it touches and why that is safe or risky.
- `## Verification`: 1 to 3 bullets, each a real run and its outcome. Perf: one number with unit, `before -> after`. Name any gate not run or check marked inconclusive.

Full SHAs, review recitals, and file-by-file lists stay out of the body.
