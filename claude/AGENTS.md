# global agent instructions

- Never use the em dash "—". Use plain dash "-" instead.
- When writing commit messages, NEVER auto-add your agent name as co-author
- Never manually modify CHANGELOG.md files or any files that are auto-generated
- When making technical decisions, do not give much weight to development cost. Instead, prefer quality, simplicity, robustness, scalability, and long term maintainability.
- When doing bug fixes, first check if a unit test or a functional test or an integration test could be used (existing or new) that would cover the issue/scenario. Then fix the issue and verify that the test fails without the fix and passes when the fix is made.
- When performing end-to-end test of a product, verify the UI rigorously with pixel perfection to identify all issues if it is not directly related to what you are doing.
- Apply that same high standard to engineering excellence: format, lint, test failures, and test flakiness.  If you identify any issues, event if it is not caused by what you are working on right now, still raise it.
