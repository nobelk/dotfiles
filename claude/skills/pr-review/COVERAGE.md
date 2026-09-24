# Coverage check (pr-review Step 4, subagent procedure)

Measure unit-test coverage of the **changed lines** in one review target, and turn the uncovered changed code into findings. Inputs come from the dispatching prompt: clone path, `<owner>/<repo>`, PR number, `authorAssociation`, `isCrossRepository`, range `<base>...<head>` (full SHAs), and the scratchpad path. The only thing you create is your own worktree. Never touch the clone's checked-out tree or GitHub.

The step is done when you return one result in the shape at the bottom: `measured` with every eligible changed file accounted for, or `skipped` or `failed` with a reason.

## 1. Eligibility

- **Trust.** Running the tests executes the PR's code on this machine. Continue only when `authorAssociation` is `OWNER`, `MEMBER`, or `COLLABORATOR` and `isCrossRepository` is false. Otherwise return `skipped: untrusted author`.
- **Eligible files.** Start from `git diff --name-only --diff-filter=AMR <base>...<head>`, then drop:
  - tests, generated code, vendored code, lockfiles, docs, and CI config;
  - **Flutter/Dart**: `*.dart`, plus any file under a directory whose ancestor holds a `pubspec.yaml`;
  - **Ansible**: files under `roles/`, `playbooks/`, `group_vars/`, `host_vars/`, `inventory/`, `inventories/`, `collections/`, `*.j2` templates, and any YAML in a repo with an `ansible.cfg` or `galaxy.yml`;
  - config and data files that carry no executable lines (YAML, JSON, TOML, SQL migrations, Markdown).

  If nothing remains, return `skipped` with the reason (`ansible`, `flutter/dart`, or `no production code`).

## 2. Worktree

```bash
WT=<scratchpad>/pr-review/wt/<owner>__<repo>-<n>-<head short sha>-$$
git -C <clone> worktree add --detach "$WT" <head>
# ... measure ...
git -C <clone> worktree remove --force "$WT"   # always, including on failure
```

## 3. Pick the command

Use the repo's own coverage entry point first, so the number matches what the team sees. Look for a `cover`/`coverage`/`test:cover`/`test:coverage` target in `Taskfile.yml`, `Makefile`, `justfile`, or `package.json` scripts, or a coverage command documented in `CLAUDE.md`, `README`, or `CONTRIBUTING`. It must leave a machine-readable profile (Go cover profile, lcov, coverage JSON or XML) you can map to lines. If not, fall back to the language default for the eligible files:

| Language | Command (run in `$WT`) |
|---|---|
| Go | `go test -short -count=1 -coverprofile=cover.out <each changed package, named explicitly>`. Naming packages explicitly makes a package with no tests report 0% instead of disappearing. |
| TS/JS | Install with the lockfile (`npm ci`, `pnpm install --frozen-lockfile`, or `yarn install --frozen-lockfile`), then run the runner in `package.json` with lcov output: `npx jest --coverage --coverageReporters=lcov` or `npx vitest run --coverage --coverage.reporter=lcov`. |
| Python | In a fresh venv (`uv venv` when `uv` exists), install the project's test deps, then `pytest --cov=<package> --cov-report=json`. |
| Rust | `cargo llvm-cov --lcov --output-path lcov.info`, only when `cargo llvm-cov` is installed. |
| anything else | `skipped: no coverage tooling for <language>` |

Run unit tests only: skip integration build tags, docker-compose, and live services. Run every install and test command under a scrubbed environment:

```bash
env -i PATH="$PATH" HOME="$WT/.home" LANG=C.UTF-8 TMPDIR="$WT/.tmp" \
  GOPATH="$(go env GOPATH 2>/dev/null)" GOMODCACHE="$(go env GOMODCACHE 2>/dev/null)" \
  <command>
```

This keeps `GH_TOKEN`, cloud credentials, and `SSH_AUTH_SOCK` away from the PR's code, and moves `HOME` so tools can't reach `~/.config` or `~/.ssh` through it. Add back only the variables the repo's documented test setup names. This limits exposure but is not a sandbox, which is why the trust check in step 1 comes first. Timebox the whole measurement to **15 minutes**. If the build or tests fail, or time runs out, return `failed` with the command and the last 30 lines of output. A failing test suite is reported to the user, not posted as a coverage finding.

## 4. Map uncovered lines to the change

1. From `git diff -U0 <base>...<head> -- <eligible files>`, collect the new-side line numbers of added and modified lines.
2. From the profile, collect the executable lines that are **not** covered. Go profile blocks cover a line range with a count of 0; lcov uses `DA:<line>,0`; coverage.py JSON uses `missing_lines`.
3. Take the intersection. Group contiguous uncovered changed lines that fall inside the same function or method into one **gap**.
4. For each gap, read the code and name the behaviour that goes untested, such as "the retry branch when the dispatcher returns 409" or "the empty-list early return". Point to the existing test file where a case belongs, or say that a new one is needed.

A new file with zero covered lines becomes a single gap, anchored on its first executable line.

## Result

```
{status: "measured" | "skipped" | "failed", reason?, command?, outputTail?,
 files: [{path, changedExecutable, changedCovered}],
 gaps: [{path, line, endLine, function, behaviour, suggestedTest}]}
```

List gaps in order of risk: error handling and branching logic first, simple accessors last. The main loop turns each gap into an inline comment and caps them.
