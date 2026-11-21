# Clean code principles (refactor Steps 1, 2, and 6)

Code is clean if it can be understood easily - by everyone on the team. Clean code can be read and enhanced by a developer other than its original author. With understandability comes readability, changeability, extensibility and maintainability.

Cite a rule by its id (`F6`, `N5`, `SM2`) in every finding and plan item.

## Applying the rules

The rules serve the definition above; they are not a checklist to maximize.

- **A finding needs evidence and a payoff.** Name the site (`file:symbol`), what a reader or the next change pays for it today, and what the remedy buys. A rule broken at no cost to anyone is not a plan item.
- **Precedence** (this is what G1 means): the repo's documented rules, then the surrounding code's established idiom, then the language community's conventions, then this list.
- **Read each rule through the language.** D2 in Go is usually an interface or a function value, not a class hierarchy. O9 has no meaning in a language without methods. T1 is one behavior per test: a table-driven test with one assertion per case satisfies it, and so does a single `cmp.Diff` over a struct.
- **When rules pull apart, G2 wins.** A two-branch `if` is simpler than a strategy hierarchy; three short lines are simpler than a helper used once. A remedy that adds more than it removes is itself SM4.
- **Smells are symptoms.** SM1-SM3 and SM6 describe how the code hurts. Trace each to its root cause (G4), which is nearly always a design, object, or function rule, and plan the fix there.
- **Duplication is repeated knowledge**, not repeated characters. Two blocks that look alike but change for different reasons stay apart.

## General rules

- **G1.** Follow standard conventions.
- **G2.** Keep it simple stupid. Simpler is always better. Reduce complexity as much as possible.
- **G3.** Boy scout rule. Leave the campground cleaner than you found it.
- **G4.** Always find root cause. Always look for the root cause of a problem.

## Design rules

- **D1.** Keep configurable data at high levels.
- **D2.** Prefer polymorphism to if/else or switch/case.
- **D3.** Separate multi-threading code.
- **D4.** Prevent over-configurability.
- **D5.** Use dependency injection.
- **D6.** Follow Law of Demeter. A class should know only its direct dependencies.

## Understandability tips

- **U1.** Be consistent. If you do something a certain way, do all similar things in the same way.
- **U2.** Use explanatory variables.
- **U3.** Encapsulate boundary conditions. Boundary conditions are hard to keep track of. Put the processing for them in one place.
- **U4.** Prefer dedicated value objects to primitive type.
- **U5.** Avoid logical dependency. Don't write methods which works correctly depending on something else in the same class.
- **U6.** Avoid negative conditionals.

## Names rules

- **N1.** Choose descriptive and unambiguous names.
- **N2.** Make meaningful distinction.
- **N3.** Use pronounceable names.
- **N4.** Use searchable names.
- **N5.** Replace magic numbers with named constants.
- **N6.** Avoid encodings. Don't append prefixes or type information.

## Functions rules

- **F1.** Small.
- **F2.** Do one thing.
- **F3.** Use descriptive names.
- **F4.** Prefer fewer arguments.
- **F5.** Have no side effects.
- **F6.** Don't use flag arguments. Split method into several independent methods that can be called from the client without the flag.

## Comments rules

- **C1.** Always try to explain yourself in code.
- **C2.** Don't be redundant.
- **C3.** Don't add obvious noise.
- **C4.** Don't use closing brace comments.
- **C5.** Don't comment out code. Just remove.
- **C6.** Use as explanation of intent.
- **C7.** Use as clarification of code.
- **C8.** Use as warning of consequences.

## Source code structure

- **S1.** Separate concepts vertically.
- **S2.** Related code should appear vertically dense.
- **S3.** Declare variables close to their usage.
- **S4.** Dependent functions should be close.
- **S5.** Similar functions should be close.
- **S6.** Place functions in the downward direction.
- **S7.** Keep lines short.
- **S8.** Don't use horizontal alignment.
- **S9.** Use white space to associate related things and disassociate weakly related.
- **S10.** Don't break indentation.

## Objects and data structures

- **O1.** Hide internal structure.
- **O2.** Prefer data structures.
- **O3.** Avoid hybrids structures (half object and half data).
- **O4.** Should be small.
- **O5.** Do one thing.
- **O6.** Small number of instance variables.
- **O7.** Base class should know nothing about their derivatives.
- **O8.** Better to have many functions than to pass some code into a function to select a behavior.
- **O9.** Prefer non-static methods to static methods.

## Tests

- **T1.** One assert per test.
- **T2.** Readable.
- **T3.** Fast.
- **T4.** Independent.
- **T5.** Repeatable.

## Code smells

- **SM1.** Rigidity. The software is difficult to change. A small change causes a cascade of subsequent changes.
- **SM2.** Fragility. The software breaks in many places due to a single change.
- **SM3.** Immobility. You cannot reuse parts of the code in other projects because of involved risks and high effort.
- **SM4.** Needless Complexity.
- **SM5.** Needless Repetition.
- **SM6.** Opacity. The code is hard to understand.
