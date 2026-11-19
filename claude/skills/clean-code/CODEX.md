# Codex review of the plan (clean-code Step 5a, subagent procedure)

Run one codex review of the simplification plan and return its findings verbatim. Inputs come from the dispatching prompt: the repo root, the plan path, the base OID, the spec path (or "none found"), the settled decisions `D1...Dn`, and the scratch directory `$tmp`. You write only under `$tmp`; the plan and the code are read-only to you.

**Done when** you return exactly one of:

```
STATUS: completed
RESULT FILE: <$tmp path holding the raw result>
FINDINGS:
<the findings verbatim, or exactly "No findings">
```

```
STATUS: failed
REASON: codex absent | launch failed | dead pid | stalled | deadline | completed with error | unusable result
DETAIL: <the error text or the last log lines, a few lines at most>
```

## Commands

The `/codex:*` entries are Claude Code slash commands with `disable-model-invocation: true` - they cannot be called, and they are not shell commands. Check availability with `command -v codex`, then run the companion script the plugin wraps, from the repo root:

```bash
# Resolve the script and record its path (version dir varies; sort -V so 1.0.10 beats 1.0.9):
ls -d ~/.claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs 2>/dev/null | sort -V | tail -1

node "$companion" adversarial-review --background --base "$base_oid" -- "$focus" < /dev/null   # launch with run_in_background: true
node "$companion" status                                        # lists this repo's jobs: take $job_id from it
node "$companion" status "$job_id" --wait --json                # poll (4-minute bounded waits); shows pid and logFile
node "$companion" result "$job_id"                              # findings
node "$companion" cancel "$job_id"                              # abandon
```

Pass the focus as its **own argument after `--`**, never bundled into a single `"--background <focus>"` string: the companion re-parses a combined string with its own option parser, so quotes get rewritten and focus text containing `--base` or `--scope` turns into options. Use `adversarial-review` rather than `review` - only it carries custom focus text. Pass `--base "$base_oid"` every time: the plan is still uncommitted, so the companion's automatic scope would see a dirty tree and supply only the working-tree diff - the plan file and any retained dirt - instead of the branch's changes.

The companion returns structured findings rendered as Markdown: a `Findings:` list, or the line `No material findings.` when the list is empty. Return the findings list verbatim; a completed result showing `No material findings.` is a passing review, and you return exactly `No findings` for it. The direct `codex exec` path below returns free text, in which the focus asks for an explicit "No findings". If no companion path resolves (plugin not installed), run a direct one-shot instead: `timeout -k 10 600 codex exec --sandbox read-only -o "$tmp/codex-result.md" "$focus" < /dev/null`. The `< /dev/null` is required: with stdin not a terminal, as in any background run, `codex exec` prints "Reading additional input from stdin..." and waits on it until the timeout kills it. If `codex` itself is absent, return `failed: codex absent` at once.

## Focus text

Fill the placeholders from the dispatching prompt:

> Review the simplification plan in <plan-path> - it is not committed yet, so read it from disk; any supplied diff covers only the committed branch - against the actual code it describes (the branch's changes vs <base-oid>), the spec at <spec-path> (or note that none was found), and the repo's standards in CLAUDE.md / AGENTS.md and the architecture documents, ADRs, and architecture-gate configuration they cite. The user's decisions for this pass were: <settled decisions>.
> First, the architecture section: for each conformance row and dependency edge the plan reports, check that the cited rule exists and says what the plan claims, that the file's component assignment is right, and that the verdict follows; then look for what it missed - a dependency edge, gate-configuration change, or lint suppression the branch added; a responsibility placed in the wrong layer; an interface defined at its implementer instead of its consumer; a sanctioned exception used beyond its purpose.
> Second, the refactor verdicts: for each unit marked Leave or Polish, is there a structural finding it ignores; for each marked Refactor, does the payoff justify the change.
> Third, for each numbered item: does the cited code actually have the problem claimed; is the named standard really what it violates; is the proposed change genuinely behavior-preserving, or would it alter behavior in an edge case; would it introduce a speculative abstraction, over-engineer a simple path, or trade duplication for coupling; is the sequencing sound, and are the dependencies between groups right. Check the correctness items and any accepted spec drift against the spec's acceptance criteria specifically.
> Then look for what the plan missed: duplication, non-idiomatic constructs, untestable or non-hermetic tests, and organization problems in the changed files that no item covers. Also check the test-gap register against the real tests - items claimed to be pinned by existing tests that are not.
> Output findings only, numbered, each citing the plan item ID, plan section, or file:line it concerns - and if you find nothing, say exactly "No findings" rather than returning an empty response. Do not rewrite the plan.

Save the result verbatim to a file under `$tmp` so the adjudication is auditable.

## Deadline and liveness

The review is the second opinion, never the critical path:

- Hard deadline: **10 minutes** for the whole review, not per attempt.
- The job is **dead now** if its `pid` is not alive (`ps -p "$pid"`) while status still says `running`.
- The job is **stalled** if its log file has been silent for **5 or more minutes**.
- A job that reports **completed but errored**, or whose result is **absent, truncated, or unreadable**, is a failed review. A review that completes and reports **no findings** is a *passing* review - require an explicit statement of it (`No material findings.` from the companion, "No findings" from a direct run) rather than inferring it from an empty file.

On death, stall, deadline, or an unusable result: run the companion's own `cancel`, then return `failed` with the reason. The companion owns its state directory, so leave the files under it alone. Make exactly one attempt: the main loop's fallback is deterministic and costs less than a second stall.
