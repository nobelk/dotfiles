# global agent instructions

- Never use the em dash "—". Use plain dash "-" instead.
- When writing commit messages, NEVER auto-add your agent name as co-author, and NEVER add agent session-link trailers (e.g. "Claude-Session: ..."). Commit messages carry no agent metadata at all.
- Never manually modify CHANGELOG.md files or any files that are auto-generated
- When making technical decisions, do not give much weight to development cost. Instead, prefer quality, simplicity, robustness, scalability, and long term maintainability.
- When doing bug fixes, first check if a unit test or a functional test or an integration test could be used (existing or new) that would cover the issue/scenario. Then fix the issue and verify that the test fails without the fix and passes when the fix is made.
- When performing end-to-end test of a product, verify the UI rigorously with pixel perfection to identify all issues if it is not directly related to what you are doing.
- Apply that same high standard to engineering excellence: format, lint, test failures, and test flakiness.  If you identify any issues, event if it is not caused by what you are working on right now, still raise it.
- Always write pull request (PR) descriptions so they are clear, accurate, and concise, and use bullet points to convey the reason for making the change. Use codex to review the PR description before posting it, and validate its findings before applying them. Never include the "created by Claude" / generated-with-Claude attribution phrase in the PR description.
- Always review your own code changes before handoff to ensure the code is clean: remove duplication the change introduced (reuse or extract shared logic using standard software engineering design patterns) and follow standard idiomatic programming practices for the language. This self-review covers only your own changes, never refactoring of untouched code.

## LLM coding behavioral guidelines

Adapted from Andrej Karpathy's guidelines to reduce common LLM coding mistakes. They bias toward caution over speed - for trivial tasks, use judgment. Merge with project-specific instructions; the project rule wins on conflict.

1. Think before coding: don't assume, don't hide confusion, surface tradeoffs. State assumptions explicitly and ask when uncertain; if multiple interpretations exist, present them instead of picking one silently; if a simpler approach exists, say so and push back when warranted; if something is unclear, stop, name what's confusing, and ask.
2. Simplicity first: minimum code that solves the problem, nothing speculative. No features beyond what was asked, no abstractions for single-use code, no unrequested "flexibility" or "configurability", no error handling for impossible scenarios ("impossible" means ruled out by the type system or API contract - never skip required error, cancellation, or resource-cleanup handling). If you write 200 lines and it could be 50, rewrite. Self-check: "Would a senior engineer say this is overcomplicated?" If yes, simplify.
3. Surgical changes: touch only what you must; clean up only your own mess. Don't "improve" adjacent code, comments, or formatting; don't refactor things that aren't broken; match existing style even if you'd do it differently. Remove imports/variables/functions that YOUR changes made unused; if you notice unrelated dead code, mention it - don't delete it. The test: every changed line traces directly to the user's request.
4. Goal-driven execution: define success criteria and loop until verified. Transform tasks into verifiable goals: "add validation" becomes "write tests for invalid inputs, then make them pass"; "fix the bug" becomes "write a test that reproduces it, then make it pass" when a suitable automated test path exists (per the bug-fix rule above) - otherwise state how the fix was verified. For multi-step tasks, state a brief plan with a verification check per step - strong success criteria let you loop independently.

These guidelines are working if: fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
