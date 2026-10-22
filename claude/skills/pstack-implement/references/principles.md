# pstack principles (condensed)

Adapted from the pstack principle skills in `cursor/plugins` (commit `eb4db2b`, MIT, copyright Lauren Tan; see `PSTACK-LICENSE`). Each entry names **when** it applies and the **rule**. Cite a principle by its name in decisions, the decision log, and the final report, and name the specific choice it changed.

## Core

- **Laziness Protocol.** When sizing a diff or tempted to add an abstraction, layer, or flag. Make the smallest change that solves the problem. Put each repeated choice behind one source of truth.
- **Foundational Thinking.** Before writing logic. Get the data shape right first: define core types, trace every access pattern, pick structures that match the dominant path. Scaffold first (shared types, test infrastructure) when every later group benefits. Ask what concurrent actors share; if anything, isolate it.
- **Redesign from First Principles.** When a requirement lands in an existing design. Build what you would have built if the requirement had been there from day one, then deliver it incrementally. Propagate it through types, docs, and examples.
- **Attack the Premise.** When two fixes that share one premise fail the same gate. Write the premise down as one sentence and test it directly before the next fix.
- **Subtract Before You Add.** When sequencing an addition. Remove dead code, redundant validators, and stub references first. No speculative guards beyond what the spec demands.
- **Minimize Reader Load.** When shaping code that is hard to trace. Count layers between question and answer and the hidden state a reader holds. Inline one-caller wrappers and pass-through layers. Prefer pure functions and locals. Test: a new reader answers "where does X come from?" and "what can change X?" in 30 seconds.
- **Outcome-Oriented Execution.** In a planned rewrite or migration. Converge on the target architecture. Planned, scoped breakage between task groups is fine; throwaway compatibility code is not. Full verification at the end.
- **Experience First.** On product or scope tradeoffs. Choose the consumer's experience over implementation convenience. The consumer can be an end user, a colleague importing the library, or the next maintainer.
- **Exhaust the Design Space.** On a novel interaction or architectural decision. Produce 2 to 3 structurally distinct candidates and compare before committing.
- **Build the Lever.** On any non-trivial work, one-off or repeated: edits, migrations, analyses, checks. Write the codemod, script, generator, or rerunnable check that does or proves it instead of working by hand; the tool is the artifact a reviewer reruns. Do the first unit by hand, then build the tool and prove it reproduces that unit. Skip only for a couple of obvious edits. Applying this principle produces a file; commit it when the work outlives the session.

## Architecture

- **Model the Domain.** When logic is stateful, branches a lot, or repeats a shape assumption. Encode the domain in a structure: a state machine over scattered booleans, a typed model over loose parameters, a table or discriminated union over branching spread across files, a module organized around one body of knowledge rather than execution order. The sign you skipped it: a new feature that adds one more branch to an existing if/else chain, or a second boolean that must stay in sync with the first.
- **Boundary Discipline.** When wiring validation, error handling, or adapters. Validate and parse at system boundaries (CLI, config, network, external APIs). Trust internal types. Keep business logic in pure functions with no framework dependencies. Do not re-export transport or storage types.
- **Type System Discipline.** When designing types or signatures. Make illegal states unrepresentable, brand semantic primitives, parse external data at the boundary, handle every variant exhaustively, derive types from the authoritative schema.
- **Make Operations Idempotent.** For commands, lifecycle steps, and loops that can crash or retry. Read current state, compare to goal, apply only the difference. Anything a run leaves behind must be recognizable as stale by the next run.
- **Migrate Callers Then Delete Legacy APIs.** When a new internal API replaces an old one with no external consumers. Migrate every caller and delete the old path in the same change.
- **Separate Before Serializing Shared State.** When concurrent actors might write the same file, branch, key, or object. Give each actor its own target first. Serialize structurally only when one shared writer is a real invariant.

## Verification

- **Prove It Works.** Before declaring anything done. Check the real artifact: run the command, read the stored value, drive the UI, inspect the diff. Never accept a proxy, a self-report, or "it compiles". Script the check when you can, and keep its output as evidence.
- **Fix Root Causes.** When debugging. Reproduce first. Ask "why" until the answer is a wrong decision in code. A guard is a fix only when the state it handles is legitimate. Find every instance of the same fault.
- **Sequence Verifiable Units.** For multi-step work and commit order. Each unit ends in a checkable state; verify it before starting the next. Order commits so the sequence proves itself: failing test, then the fix; subtraction, then the reshape; scaffold, then the feature.
- **Test Behavior, Not Implementation.** When writing, changing, or keeping a test. Assert what the code's users observe through their interface. A good test fails when the behavior breaks and survives a refactor of the internals. Derive expected values from the requirement, not from running the code.
- **Explain the Number.** Before reporting or acting on a measured number. Name the limiter ("why not double?"), rule out errors, skipped or cached work, untuned sides, and noise. Keep run count, spread, and limiter with the number.

## Delegation

- **Guard the Context Window.** When outputs, files, or fan-out grow. Route bulk reading to subagents and keep summaries and file pointers in the main thread.
- **Never Block on the Human.** When tempted to ask "should I do X?" about reversible work. Do X, show the result, and let the human course-correct. Product direction and irreversible actions still go to the human.

## Meta

- **Encode Lessons in Structure.** When writing the same instruction a second time. Make it a type, lint, test, runtime check, or script instead of more prose.
