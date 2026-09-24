# Scheduled PR review

Runs the `/pr-review` Claude Code skill (`claude/skills/pr-review`) with `--yes` over a list of GitHub repos at 09:00, 12:00, 15:00 and 18:00 local time every day. Each run posts review comments as the active `gh` login and never approves; PRs ready for approval are listed in the report for an interactive `/pr-review` run.

## Files

| File | Installed to | Purpose |
|---|---|---|
| `repos.txt` | `~/.config/claude-pr-review/repos.txt` | Repos to review, one `owner/repo` per line. Read on every run, so edits need no restart. |
| `claude-pr-sweep` | `~/.local/bin/claude-pr-sweep` | Runs `claude -p "/pr-review <repo> --yes"` for each repo, one after another, with a 90-minute cap per repo. Uses `~/sources/<repo>` as the working clone when it exists. |
| `claude-pr-review.service` | `~/.config/systemd/user/` | Oneshot unit that runs the script. |
| `claude-pr-review.timer` | `~/.config/systemd/user/` | The schedule. `Persistent=true` runs a missed slot once after boot or resume. |
| `install.sh` | — | Copies the files, enables the timer, and turns on lingering. |

## Install

Prerequisites: the `pr-review` skill (and the built-in `code-review`) available to `claude`, `claude` logged in, `gh auth login` done as the account that should post, and the Atlassian connector connected for the Jira check.

```bash
./install.sh
```

`loginctl enable-linger` makes the timer start at boot without a login session, so the schedule survives restarts. The machine still has to be powered on; a missed slot runs once when it comes back.

Toolchain paths are set at the top of `claude-pr-sweep` (`~/.local/bin`, `~/.local/go/bin`, mise shims, Flutter). Adjust them on a machine with a different layout, since systemd doesn't load the shell profile.

## Output

- Reports: `~/pr-reviews/<date>/<HHMM>-<repo>.md`, kept for 30 days.
- Failures: `~/pr-reviews/<date>/_errors.log`.
- Review state: `~/.local/state/pr-review/<owner>__<repo>.json`, which stops the same PR head being reviewed twice.

## Operate

```bash
systemctl --user list-timers claude-pr-review.timer   # next run
systemctl --user start claude-pr-review.service       # run now
journalctl --user -u claude-pr-review.service         # run log
systemctl --user disable --now claude-pr-review.timer # stop scheduling
```

Try a repo without posting: `cd ~/sources/<repo> && claude -p "/pr-review <owner>/<repo> --dry-run" --permission-mode auto`.
