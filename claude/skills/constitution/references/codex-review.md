# Running a codex review of documents

You are the subagent that runs codex for a calling skill. The caller gave you four things: the directory to review (`<dir>`), a job tag (`<tag>`), the focus text (`<focus>`), and a scratch path outside the repo (`<scratch>`).

Return codex's findings verbatim, `no findings` for a review that completed clean, or the single line `codex failed: <reason>`. Leave the findings unjudged and the documents unedited: the caller adjudicates.

## Run it

Use the codex plugin's **adversarial review**, because it accepts focus text and the plain `review` doesn't. The `/codex:*` slash commands can't be invoked from here, so run the companion script they wrap.

First write `<focus>` to `<scratch>.focus` with the Write tool. The text contains quotes, and reading it back from a file keeps it one shell argument.

```bash
ls -d ~/.claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs 2>/dev/null | sort -V | tail -1   # -> <companion>
# launch with the Bash tool's run_in_background: true
CODEX_COMPANION_SESSION_ID=<tag> timeout -k 10 660 node "<companion>" adversarial-review --background --scope working-tree --cwd "<dir>" -- "$(cat "<scratch>.focus")"
CODEX_COMPANION_SESSION_ID=<tag> node "<companion>" status --cwd "<dir>" --json       # lists only this launch's job -> <job-id>
node "<companion>" status <job-id> --cwd "<dir>" --wait --timeout-ms 240000 --json     # repeat until finished
node "<companion>" result <job-id> --cwd "<dir>"                                        # save verbatim to <scratch>
```

- Substitute `<companion>`, `<tag>`, and `<dir>` literally, and keep `--cwd "<dir>"` on every call. Neither shell variables nor `cd` persist between Bash calls, and a `status` run from another directory finds no job.
- Pass each flag as its own argument and the focus as one argument after `--`. The companion re-splits a combined string and can mangle it.
- Give the `--wait` call a Bash timeout of at least 250000 ms, since it blocks for up to 240 seconds.
- Find the job by its tag, not as "the newest job": other reviews may share the workspace. Zero jobs under the tag, or more than one, means the launch failed.

## When it goes wrong

- **Deadline:** 10 minutes from launch. The job has stalled if its `pid` is dead while status still says running, or if its `logFile` has been silent for 5 minutes. On a stall or the deadline, run `node "<companion>" cancel <job-id> --cwd "<dir>"` and return `codex failed: <reason>`.
- **No companion script, or `<dir>` is not a git repo** (`--scope working-tree` needs git): run codex directly.
  ```bash
  cd "<dir>" && timeout -k 10 600 codex exec --sandbox read-only --skip-git-repo-check -o "<scratch>" "$(cat "<scratch>.focus")" < /dev/null
  ```
  The `< /dev/null` matters: with no terminal on stdin, `codex exec` waits on it until the timeout kills it.
- A non-zero exit, a job that ends in an error, or an empty result is `codex failed`.
