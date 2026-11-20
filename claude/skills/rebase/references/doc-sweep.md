# Documentation and spec staleness sweep

You are the doc-sweep reader for rebase Step 3. The main loop gave you the repo path, `<fork-point>` (where the branch left the input's history), `<pre-rebase-sha>` (the branch's tip before the rebase), `<input-sha>` (the tip it was rebased onto; `<input>` below means that side), and the conflict list. HEAD is the rebased tree. Read only: the main loop makes every edit.

A rebase leaves prose stale silently, because no test fails on it. The highest-yield failures are a decision record that `<input>` has already overtaken, and an enumeration that was complete before the rebase and is one short after it.

**Done when** every candidate document has been checked against the rebased tree and you return:

- the candidate set, as a list of paths;
- each stale statement: file:line, what it says, the rebased-tree evidence that contradicts it (file:line or command output), whether it is a doc fix or a code bug, and the proposed fix;
- each place where a doc and the code disagree and which one is wrong is a product question, not an editorial one: mark it `needs user decision` with both readings.

An empty list of stale statements is a valid result; return the candidate set anyway, so the report can show what was checked.

## Build the candidate set

Build it from the branch's side, which keeps it bounded even when the branch is far behind: a doc goes stale through this rebase only when it relates to something the branch changed. Doc files are `*.md`, `*.rst`, `*.txt`, and `*.adoc`.

- Docs the branch changed (`git diff --name-only <fork-point> <pre-rebase-sha> -- '*.md' '*.rst' '*.txt' '*.adoc'`), and doc files in the conflict list.
- Docs anywhere in the tree that name a file the branch changed, or an identifier it adds, renames, or removes (`rg -l '<TypeName>|<path/fragment>' --glob '*.{md,rst,txt,adoc}'`). A spec neither side edited still goes stale when the thing it describes moves.
- Docs `<input>` added or changed (`git diff --name-only <fork-point> <input-sha> -- <the same globs>`) that cover the branch's area: they name a file, identifier, or spec the branch touches. Decision records (ADRs, specs) among them matter most.
- The godoc and docstrings on the branch's changed code, and the repo's convention files (README, `CLAUDE.md` / `AGENTS.md`, the ADR index, the changelog).

## Check each candidate against the rebased tree

Check against the code as it is now, not against what the doc used to say.

- **Decision records `<input>` overtook.** An ADR or spec `<input>` merged may accept a decision the branch's own spec contradicts, or record a validation line that cannot pass once this branch lands. Read those records in full. Two accepted records must not disagree: where both are now true of different phases, propose scoping each one explicitly.
- **Enumerations and counts.** "Every kind", "all N families", "the four rules", case tables, exhaustive switches mirrored in prose. Derive each set from the rebased code (`rg` the type's variants, the enum's members, the config's keys) and diff it against the doc. A rebase that adds one variant leaves every enumeration of that set one short, including enumerations inside *tests* that claim exhaustiveness.
- **Behavioral claims.** A sentence asserting what the code does ("the worker drains rather than crashing", "this decorator covers every inbound path") is a claim to verify. Trace the code path and confirm it still behaves that way after `<input>`'s changes. A claim that no longer holds is either a doc fix or a code bug: say which.
- **Cross-references and identifiers.** ADR numbers and statuses, ticket keys, file paths, package, type, and function names, line-anchored pointers, links between specs. `<input>` may have renumbered an ADR, moved a type between layers, or promoted a `proposed` record to `accepted`.
- **Scope and phase statements.** A spec's intro, its decisions section, and its requirement rows often state what this phase owns. `<input>` may have already delivered part of it, changed what the next phase needs, or moved a type that a row's layering edges describe.
- **Stale by omission.** A doc can be wrong by saying nothing: a new variant, failure mode, or config key `<input>` added that the branch's table or failure matrix has no row for.
