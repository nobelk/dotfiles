#!/usr/bin/env bash
# Installs the scheduled /pr-review sweep as a systemd user timer.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)

mkdir -p ~/.config/claude-pr-review ~/.config/systemd/user ~/.local/bin
# Keep an existing repo list; it is the per-machine config.
[[ -f ~/.config/claude-pr-review/repos.txt ]] || cp "$here/repos.txt" ~/.config/claude-pr-review/repos.txt
install -m 755 "$here/claude-pr-sweep" ~/.local/bin/claude-pr-sweep
cp "$here/claude-pr-review.service" "$here/claude-pr-review.timer" ~/.config/systemd/user/

systemctl --user daemon-reload
systemctl --user enable --now claude-pr-review.timer
# Lingering starts the user's timers at boot without a login session.
loginctl enable-linger "$USER"

systemctl --user list-timers claude-pr-review.timer --no-pager
