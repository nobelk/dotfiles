# Architecture conformance (clean-code Step 2b, subagent procedure)

Verify that the code this branch added or changed conforms to the repository's architecture style, with evidence for every verdict. Inputs come from the dispatching prompt: the tree to read (the repo root, or a clean worktree of the committed branch when the user kept uncommitted edits - read and run everything there), the base OID, the merge-base OID, the changed-file list with statuses (both paths for renames), the scratch directory `$tmp`, and the architecture-gate output file with its exit status - plus, when the gate failed, the same command's output at the merge-base. You read files and run read-only commands; the only place you write is `$tmp`.

**Done when** every changed source file has exactly one row in the conformance table, every dependency edge the diff adds has a disposition, every change the branch makes to the gate's own configuration or to lint suppressions has a disposition, and every rule you apply carries a citation. Then return the result shape at the bottom - nothing else.

## 1. Build the architecture model

Read, in this order, until the model is complete: `CLAUDE.md` / `AGENTS.md`; every architecture document and ADR they cite; any ADR the diff or the changed files mention; the gate's configuration. Record:

- **Style** - the named style or styles (hexagonal / ports and adapters, clean or onion, layered, modular monolith, vertical slices, MVC, ...) and where each is declared (`doc:line`). If nothing declares one, infer it from the directory layout and the consistent precedent of the existing code, and label it **inferred** with that evidence. An inferred style is judged only on conventions the existing code follows consistently.
- **Components** - each layer or component and the paths it owns.
- **Allowed edges** - which component may depend on which, and which third-party dependencies each may use.
- **Sanctioned exceptions** - each named exception and the purpose it was granted for. An exception covers its purpose, not every use of its import path.
- **Change rules** - what the repo requires before the rules themselves change (for example, an ADR in a stated status before a new grant).
- **Placement rules** - what the repo says about where a concern belongs (one handler per message family, thin composition roots, one concern per file, ...).
- **The gate and its blind spots** - which tool enforces which rules, and what it cannot see: placement, coupling through data shapes, files it excludes (often tests), packages outside every component.

Cite the source of every rule as `doc:line`. A rule you cannot cite is a preference, and preferences produce no `violation` rows.

## 2. Mechanical checks

Common gates, by ecosystem - detect them from the config files present, and prefer the repo's own entrypoint (`task arch-lint`, `make arch`) over the raw tool:

| Ecosystem | Gate and config | Run | File-to-component mapping |
| --- | --- | --- | --- |
| Go | go-arch-lint (`.go-arch-lint.yml`); golangci-lint `depguard` / `gomodguard` rules | `go-arch-lint check` | `go-arch-lint mapping` |
| Python | import-linter (`.importlinter`, `[tool.importlinter]`); tach (`tach.toml`) | `lint-imports`; `tach check` | the contracts' module lists |
| JS/TS | dependency-cruiser (`.dependency-cruiser.*`); eslint-plugin-boundaries or `no-restricted-imports`; Nx `enforce-module-boundaries` | `depcruise`; the repo's eslint script | the config's path patterns |
| JVM | ArchUnit tests | the test task that runs them | the rule classes |
| Rust | the workspace crate graph (`Cargo.toml`); `cargo deny` | `cargo tree`; `cargo deny check` | one crate per component |

1. **Gate result.** Read the gate output file you were given; Step 2a already ran it, so do not re-run it. Classify it as `pass`; `fail`; `not configured`; or `unavailable` (configured, but the tool is missing or crashed - never a pass). Attribute each failing finding by comparison, never by filename - a branch's config or dependency change can break a file it never touched, and a changed file can carry an old violation on a line the branch did not touch: a finding also present in the merge-base output is pre-existing (an observation); one absent there is the branch's, wherever it sits. Without a merge-base output, every failing finding is `unattributed`.
2. **Mapping.** Assign every changed source file to a component, using the tool's mapping command where it has one. A file that maps to no component is `unmapped`: the gate never checks it, whatever its exit code says. Record each as a gate-coverage gap and name the component it should belong to.
3. **New dependency edges.** List the import edges the branch adds, test files included (gates often exempt them):
   ```bash
   git --literal-pathspecs diff -U0 "$base_oid...HEAD" -- "${changed_sources[@]}"   # added import lines
   ```
   Pass `--literal-pathspecs` on every git command restricted to resolved filenames: quoting stops the shell from expanding them, but git still reads `*`, `[`, and a leading `:` as pathspec patterns.
   Resolve each added import to its component. For Go, `go list -f '{{.ImportPath}}: {{join .Imports " "}} | {{join .TestImports " "}} | {{join .XTestImports " "}}' "${pkgs[@]}"` gives the resolved edge set of the changed packages. A new third-party dependency in the diff (`go.mod`, `package.json`, `pyproject.toml`, `Cargo.toml`) is a new edge from every component that imports it. Disposition each edge: `allowed`; `exception <name>`, saying whether this use fits the exception's stated purpose; or `forbidden`.
4. **Gate changes.** Diff the gate's own configuration over the branch (`git --literal-pathspecs diff "$base_oid...HEAD" -- "${gate_configs[@]}"`), and scan the added lines of the diff for suppressions (`//nolint`, `//lint:ignore`, `# noqa`, `# type: ignore`, `eslint-disable`, `@SuppressWarnings`, new `excludeFiles` or ignore entries). Every loosening - a new grant, a widened component, an excluded file, a suppression - needs the rationale the repo's change rules demand (an ADR, a reason comment). One without it is a `violation` of the change rule, and the files it lets through count as unverified: a gate that passes because the branch loosened it is no evidence of conformance.

## 3. Placement and boundary review

The gate proves imports; this step proves placement. Read each changed file in full, with its neighbours, and for each responsibility the branch added or moved, answer:

1. **Right home.** Does it live in the component that owns the concern? Business rules (validation, decisions, invariants) belong in the domain or core; orchestration in the application or use-case layer; protocol and storage translation in adapters; wiring alone in the composition root. Tells: a business decision inside a handler, codec, or repository; a wire enum, status code, SQL fragment, or transport retry policy inside the core; branching logic in `main` or the composition root.
2. **Direction by data as well as by import.** Does an inner layer receive outer-layer shapes disguised to slip past the import rule - `any`, `map[string]any`, raw bytes, strings carrying protocol meaning? Do storage rows or wire messages double as domain entities? Do adapter-specific errors cross a port untranslated?
3. **Ports.** Is each new interface defined at its consumer, sized to that consumer's need, and free of transport artifacts? Does a new port get every adapter the repo requires (an in-memory one, for instance)? Is a concrete type used where the repo routes through a port?
4. **Boundary crossings.** Do sibling components couple directly, or indirectly through shared mutable state, a global registry, or a shared package that is not a sanctioned exception? Is a sanctioned exception used beyond the purpose it was granted for?
5. **Cohesion and coupling.** Does a file or package now own two concerns? Did one concern force edits across many components (shotgun surgery - a misplaced concern or a missing abstraction)? Did the change create a cycle or a two-way relation between components, even through interfaces?
6. **Repo-declared architectural obligations.** For every rule the repo frames as an obligation on every path (a context-carried correlation id, a single error-reporting route, resource-lifecycle ownership, goroutine supervision, ...), check each changed path against it. General code style belongs to the other reviewers.
7. **Decision records.** Does every load-bearing structural decision the branch makes - a new component, port, dependency, exception, or deviation - have the record the repo requires?

**Scope to this branch.** Judge what the branch added or changed. A pre-existing violation in untouched code goes under observations. A branch that copies a pre-existing violating pattern into new code owns the copy: report the new site as the finding and the precedent as an observation.

**Verdict per row:**

- `conforms` - no cited rule broken, and the placement questions raise nothing.
- `violation` - breaks a cited rule, mechanical or documented, or depends on an unrecorded gate loosening.
- `drift` - conforms to the letter but erodes a cited intent: a disguised dependency, a second concern accreting, an exception stretched past its purpose.
- `unmapped` - outside every component, so the gate never checked it.

**Branch verdict**, aggregated over every section, not only the per-file rows - a configuration-only branch has no source rows yet can still loosen the gate: `violates` if any conformance row is `violation`, any gate change is a `violation`, any new edge is `forbidden`, or any gate finding is attributed to the branch; `conforms with drift` if any row is `drift` or `unmapped`, or any finding is `unattributed`; otherwise `conforms`.

## Result shape

```
STYLE: <style> - declared at <doc:line> | inferred from <evidence>
GATE: <command> -> pass | fail (<n> branch, <m> pre-existing, <k> unattributed) | not configured | unavailable (<why>)
GATE COVERAGE GAPS: <unmapped files, gate-excluded changed files> | none
GATE CHANGES: <change - rationale record or "none found" - verdict> | none
NEW EDGES:
<from component> -> <to component or third-party module> | <file:line> | allowed | exception <name> (fits purpose: yes/no) | forbidden
CONFORMANCE:
<file> | <component> | conforms | violation | drift | unmapped | <rule, doc:line> | <evidence file:line> | <remedy, as a named refactoring where one applies>
BRANCH VERDICT: conforms | conforms with drift | violates
OBSERVATIONS: <pre-existing issues seen, out of scope> | none
NEEDS USER DECISION: <question and why> | none
```

When many files conform, collapse them into one `conforms` row listing the files.
