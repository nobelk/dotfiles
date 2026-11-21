# Codex review of the plan (refactor Step 5, subagent procedure)

Run one codex review of the refactor plan and return what it found. Inputs come from the dispatching prompt: the workspace root, the plan path, `<merge-base>`, the path of `CLEAN_CODE.md`, the architecture documents the plan cites, the branch's spec when it has one, the settled decisions `DEC-1...DEC-n`, and the scratch directory `<tmp>`. You write only under `<tmp>`; the plan and the code are read-only to you.

**Done when** you return exactly one of:

```
STATUS: completed
RESULT FILE: <tmp>/codex-result.md
VERDICT: <the result's Verdict line, and its summary paragraph>
FINDINGS:
<the result's Findings list verbatim, or exactly "No findings">
```

```
STATUS: failed
REASON: codex absent | launch failed | dead pid | stalled | deadline | completed with error | unusable result
DETAIL: <the error text or the last log lines, a few lines at most; "none" when there is neither>
```

## Focus text

Write the focus to `<tmp>/focus.txt` with the Write tool, filling the placeholders, and pass it to the commands below as `"$(cat "<tmp>/focus.txt")"`. Typed inline between double quotes, its backticks would run as shell commands.

> Review <plan-path>, a plan for refactoring this branch so that it conforms to the repository's architecture and to the clean code principles in <clean-code-path>. The plan is not committed, so read it from disk. The code it covers is what the branch changed: `git diff <merge-base>...HEAD`. The architecture is declared in <architecture-docs>. The behavior the branch is meant to have is specified in <spec-path, or "no spec">.
> Architecture: for each conformance row, does the cited rule exist and say what the plan claims, is the file assigned to the right component, and does the verdict follow. Then what the plan missed: a dependency edge the branch added, a responsibility in the wrong layer, an interface defined at its implementer.
> For each plan item: does the cited code have the problem claimed; is the cited principle really what it breaks; is the planned change behavior-preserving in every edge case, or would it alter what a caller observes; do the named tests actually pin the behavior it touches, so that a mistake would turn them red; does the remedy leave the code simpler, or does it trade one smell for another (a speculative abstraction, an extra layer, coupling in place of duplication).
> Across the plan: is the order safe, with each item's prerequisites before it; is any behavior change hidden inside a refactor item; did a finding with a real payoff get skipped, or one with none get planned.
> Report findings only, each naming the plan item it concerns and quoting the code location in its body, with a suggested change. Do not edit any file.
> The user's settled decisions follow. Report one only if it rests on a fact that is wrong, not because you would have chosen differently.
> <DEC-1...DEC-n, one per line>

## Commands

The `/codex:*` entries are Claude Code slash commands with `disable-model-invocation: true`: they cannot be called, and they are not shell commands. Check `command -v codex` (absent: return the `failed` block with `REASON: codex absent` at once), then run the companion script the plugin wraps, from the workspace root:

```bash
# Resolve the script and record its path as <companion> (the version dir varies; sort -V so 1.0.10 beats 1.0.9):
ls -d ~/.claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs 2>/dev/null | sort -V | tail -1

timeout -k 10 600 node "<companion>" adversarial-review --scope working-tree -- "$(cat "<tmp>/focus.txt")"   # Bash run_in_background: true
node "<companion>" status                                        # this session's jobs: take the newest running adversarial review as <job-id>
node "<companion>" status "<job-id>" --wait --timeout-ms 100000  # a wait that fits the Bash tool's default timeout; repeat it
node "<companion>" status "<job-id>" --json                      # job.pid (the launch process; null once finished) and job.logFile
node "<companion>" result "<job-id>" > "<tmp>/codex-result.md"   # the rendered review
node "<companion>" cancel "<job-id>"                             # abandon
```

- The review runs in the foreground of the launch command, so the Bash tool's `run_in_background: true` is what detaches it, and the `timeout` is what bounds it. A review typically takes three to five minutes.
- Pass the focus as its **own argument after `--`**: the companion re-parses a lone combined string with its own option parser. Use `adversarial-review`, the only review that carries focus text.
- `--scope working-tree` makes the uncommitted plan part of the reviewed change. The companion inlines it only below 24 KB, which is why the focus says to read it from disk.
- The `--wait` call exits 0 whether the job finished or the wait ran out. Read the job's status word (`completed`, `running`, `failed`) from its output, and issue the wait again while it says `running` and the deadline allows: a review usually needs two to four of them.
- The companion renders the review in its own shape: a heading and `Target:` line, a `Verdict:` line, a summary, then `Findings:` with one `- [severity] title (plan lines)` entry per finding, its detail and a `Recommendation:` beneath, and session trailers at the end. Return the entries with their recommendations and leave the trailers out. `No material findings.` in place of the list is a passing review; return exactly `No findings` for it.
- The companion leaves an idle broker process behind for the plugin's session-end hook to stop. It belongs to the plugin; leave it and the files under the plugin's state directory alone.

If no companion path resolves, run a direct one-shot instead:

```bash
timeout -k 10 600 codex exec --sandbox read-only -o "<tmp>/codex-result.md" "$(cat "<tmp>/focus.txt")" < /dev/null
```

The `< /dev/null` is required here: with stdin not a terminal, `codex exec` waits on it until the timeout kills it. This path returns free text; when it reports nothing, return exactly `No findings`.

## Deadline and liveness

The review is the second opinion, never the critical path:

- Hard deadline: **10 minutes** for the whole review, which the `timeout` on either launch enforces.
- The job is **dead** if `job.pid` is not alive (`ps -p "<pid>"`) while status still says `running`.
- The job is **stalled** if its log file has been silent for **5 or more minutes**.
- A job that completed with an error, or whose result is absent, truncated, or unreadable, is a failed review.

On any of these: run the companion's own `cancel`, then return `failed` with the reason. Make exactly one attempt: the main loop's fallback costs less than a second stall.
