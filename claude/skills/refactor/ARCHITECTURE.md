# Architecture conformance (refactor Step 1)

Establish what architecture the repository declares, and where the code in scope has drifted from it, with a citation for every rule and evidence for every verdict. Inputs: the workspace root, `<merge-base>`, the in-scope file list, and the baseline output of the architecture gate when the repo has one. This procedure reads and runs read-only commands; it changes nothing.

**Done when** every in-scope production file has a row in the conformance table (a test file only when it breaks a rule; a file that breaks two rules gets a row for each) and every dependency edge the branch added has a disposition.

## 1. Build the model

Read, until the model is complete: `CLAUDE.md` / `AGENTS.md`; the architecture and design documents they cite (`docs/design/`, `docs/architecture*`, `specs/tech-stack.md`); the ADRs that touch the in-scope files (`specs/adr/`, `docs/adr/`); the gate's configuration. Record:

- **Style** - the named style (hexagonal, clean, layered, modular monolith, vertical slices, MVC, ...) and where it is declared, as `doc:line`. When nothing declares one, infer it from the directory layout and the consistent precedent of the existing code, and label it **inferred**: an inferred style is judged only on what the existing code does consistently.
- **Components** - each layer or component and the paths it owns.
- **Allowed edges** - which component may depend on which, and which third-party dependencies each may use.
- **Placement rules** - what the repo says about where a concern lives.
- **Sanctioned exceptions** - each one and the purpose it was granted for.
- **The gate and its blind spots** - which tool enforces which rule (go-arch-lint, depguard, import-linter, tach, dependency-cruiser, ArchUnit, a repo script), and what it cannot see: placement, coupling through data shapes, excluded files.

A rule you cannot cite is a preference, and preferences produce no `violation` rows.

## 2. Mechanical checks

1. **Gate result** - from the baseline run: `pass`, `fail`, `not configured`, or `unavailable` (configured but the tool is missing: never a pass). Attribute each failure by comparison: run the same command in a throwaway worktree at `<merge-base>` (`git worktree add --detach <tmp>/base <merge-base>`, removed afterwards with `git worktree remove --force`); a failure also present there predates the branch.
2. **New edges** - the imports the branch added (`git diff -U0 <merge-base>...HEAD`), each resolved to its component and marked `allowed`, `exception <name>`, or `forbidden`. This judges the edge alone: an allowed import used to reach a misplaced responsibility is a `drift` row in the conformance table.
3. **Loosened gates** - changes the branch made to the gate's own configuration, and suppressions it added (`//nolint`, `# noqa`, `# type: ignore`, `eslint-disable`, ...). A gate that passes because the branch loosened it is no evidence of conformance.

## 3. Placement review

The gate proves imports; this proves placement. Read each in-scope file in full, with its neighbours:

1. **Right home.** Business rules (validation, decisions, invariants) in the domain or core; orchestration in the application layer; protocol and storage translation in adapters; wiring alone in the composition root. Tells: a business decision inside a handler, codec, or repository; a status code, SQL fragment, or wire enum inside the core.
2. **Direction by data as well as by import.** An inner layer receiving outer-layer shapes disguised as `any`, maps, raw bytes, or strings with protocol meaning; storage rows or wire messages doubling as domain entities; adapter errors crossing a port untranslated.
3. **Ports.** Each interface defined at its consumer and sized to that consumer's need; a concrete type used where the repo routes through a port.
4. **Boundary crossings.** Sibling components coupling directly, or through shared mutable state, a global registry, or an unsanctioned shared package.
5. **Cohesion.** A file or package that now owns two concerns; one concern that forced edits across many components.

## Result shape

```
STYLE: <style> - declared at <doc:line> | inferred from <evidence>
GATE: <command> -> pass | fail (<n> from this branch, <m> pre-existing) | not configured | unavailable (<why>)
NEW EDGES: <from> -> <to> | <file:line> | allowed | exception <name> | forbidden
CONFORMANCE:
<file> | <component> | conforms | violation | drift | <rule, doc:line> | <evidence file:line> | <remedy, as a named refactoring>
VERDICT: conforms | conforms with drift | violates
OBSERVATIONS: <pre-existing issues outside the scope> | none
```

`violation` breaks a cited rule. `drift` keeps to the letter but erodes a cited intent: a disguised dependency, a second concern accreting, an exception stretched past its purpose. Collapse conforming files into one row.
