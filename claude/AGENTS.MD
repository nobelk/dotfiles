# Global agent instructions

## Go code navigation

For Go go-to-definition, find-references, interface implementations, and call
hierarchies, load the LSP tool first (`ToolSearch "select:LSP"`) and use it
instead of Grep. gopls is installed and registered for `.go` files via the
`gopls-lsp` plugin. The GoLand MCP tools (`mcp__goland__*`) are an equivalent
alternative when that server is connected. Grep is for plain text patterns only.

`goToImplementation` on an `internal/app/ports` interface is the preferred query
in a hexagonal codebase: it returns every adapter, mock, and test double with no
false positives.

## Background processes and test runs

Never spawn unbounded busy-loops to simulate CPU load, contention, or a loaded
CI runner. Patterns like `(while :; do :; done) &` are banned outright: if the
parent shell dies before its cleanup line runs, the children reparent to launchd
and pin a core each until the machine is rebooted or they are killed by hand.
To exercise code under load, use a bounded tool instead — `go test -cpu=N`,
`-parallel=N`, `-race`, `stress-ng --timeout`, or `timeout N <cmd>`.

Any background process started from a Bash tool call must clean itself up
without depending on a later line in the same script:

- Install the trap in the same command that spawns the process, immediately
  after the spawn: `trap 'kill $PIDS 2>/dev/null' EXIT INT TERM`.
- Give every long-running command its own upper bound (`timeout 300 ...`,
  `go test -timeout 180s`), so nothing outlives the call that started it.
- Never rely on a trailing `kill $PIDS` alone. A session that exits, a tool
  timeout, or an interrupt skips it.

After any command that spawned background work, verify nothing survived before
reporting the task done:

    ps -axo pid,ppid,etime,%cpu,command | awk '$2 == 1 && $4 > 10'

Any hit whose parent is PID 1 is an orphan you created. Kill it and say so.
