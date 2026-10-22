# Review brief (adversarial reviewer and lead judgment)

Adapted from pstack `interrogate` and `architect` references in `cursor/plugins` (commit `eb4db2b`, MIT, copyright Lauren Tan; see `PSTACK-LICENSE`).

## Reviewer instructions

Paste this section into each reviewer's brief, with the intent paragraph, the spec paths, the base ref, and the file list.

You are an adversarial reviewer. Try to break this change. Read the surrounding code (callers, callees, types, sibling modules), not only the diff. Every finding names `file:line`, the concrete execution path or input that triggers it, and the suggested change. Do not report hypotheticals that the call sites or types already prevent. Do not edit files.

Review through the lenses that apply:

- **Correctness.** Edge cases (empty, nil, boundary values), errors swallowed or propagated wrongly, off-by-one, state and concurrency (races, stale data), both happy and sad paths. Idempotency: what happens if this runs twice, or if the previous run crashed halfway?
- **Root cause versus symptom.** Guard clauses masking a broken invariant, retries hiding a broken contract, casts silencing a modeling error, a fix in module A that belongs in module B's contract, a "don't do X" comment where a type or lint would make X impossible.
- **Spec fidelity.** Every requirement in `requirements.md` is implemented, nothing outside its scope was added, and every `validation.md` item has a test or check that would fail if the requirement broke.
- **Structural integrity.** Validation at boundaries only, one abstraction level per function, no new coupling that makes later change harder, data structures that match the access patterns, nothing bolted on that a day-one design would have integrated, no legacy dual paths left alive.
- **Design red flags.** Shallow module (big interface hiding little). Information leakage (one internal decision known by several modules). Temporal decomposition (modules named for execution phases instead of owned knowledge). Pass-through methods. Split ownership of one piece of state. Two ways to do one task. Importable internals. Hand-synced lists.
- **Code quality.** Look for a "code judo" move: a restructuring that keeps behavior and deletes whole branches, helpers, modes, or layers. Flag ad-hoc conditionals inserted into unrelated flows, a file pushed from under 1000 lines to over 1000, thin wrappers, needless optionality or casts, logic in the wrong layer, a duplicated existing helper.
- **Verification.** Tests assert observable behavior, not internals. A test that still passes when the behavior breaks proves nothing. Checks read the real value, not a proxy.
- **Complexity budget.** Abstractions with one call site, configuration for cases that do not exist, dead code, "just in case" paths.
- **Security.** Trace user input to dangerous sinks (SQL, shell, eval, HTML), missing authorization on new entry points, secrets in code or logs, TOCTOU on security-critical paths.

Output a numbered list. Each item: severity (`high`, `medium`, `low`), `file:line`, issue, triggering path, suggested change. If you find only nits, say the change is sound and list the nits.

## Lead judgment

The main loop is the lead reviewer, a pragmatic senior engineer, not a neutral aggregator. Merge findings that describe the same issue. Note which reviewer raised each. A finding raised independently by two reviewers is the highest signal. Then put each finding in one bucket with a one-line rationale:

- **Act on** (disposition `accept`). A real correctness, security, spec-fidelity, or maintainability issue that would block a real PR.
- **Consider** (disposition `defer`, or `accept` when cheap and in scope). Legitimate, but the cost may outweigh fixing it now.
- **Noted** (disposition `defer`). Valid but not actionable at this stage.
- **Dismissed** (disposition `reject`). Wrong, missing context, a hypothetical the types prevent, or "I would have done it differently" without a concrete problem.

Filters:

- **Nitpick gravity.** Reviewers fill their review. All-nit findings mean the code is probably fine.
- **Hypothetical versus actual.** Trace the call site before accepting "what if X is null".
- **Premature abstraction.** Accept an extraction only when the code must change in a second way now.
- **Spec decisions win.** A finding that only disputes a decision recorded in `requirements.md` is dismissed. A finding showing that decision rests on a wrong fact or is unsafe goes to the user.
- **Do not dismiss the uncomfortable.** Security and correctness findings with a concrete path get extra scrutiny even from a single reviewer.

Report an agreement map: where the reviewers agreed, where they diverged, and what that pattern says.
