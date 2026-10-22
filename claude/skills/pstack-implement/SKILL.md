---
name: pstack-implement
description: Implements a feature spec written by /feature-spec (specs/<name>/{requirements,plan,validation}.md) end to end with the pstack engineering process — ground, architect, throughput checkpoint, test-first delegated build per task group, deslop and comment cleanup, codex plus Claude adversarial review, independent proof of every validation item, then push the spec branch and open or update a ready PR. Takes the spec branch name (specs/<name> or <name>).
disable-model-invocation: true
---

# pstack-implement

Build the feature that `/feature-spec` specified, on the same `specs/<name>` branch, using the pstack process (poteto-mode's Feature playbook, its principles, and its architect, tdd, no-comments, unslop, interrogate, and Opening a PR skills). The output is one ready PR that carries the spec and its implementation: one green commit per `plan.md` task group, then cleanup, review-fix, gate, and spec commits when each has content. The spec commit ticks the `validation.md` boxes the evidence proved.

**You own the design. Plan, review, verify. Delegate the code.** The main loop is the lead engineer: it grounds, designs, sequences, reviews every diff, judges findings, and commits. Subagents write code and gather evidence. The author of a change never verifies it.

Read [`references/principles.md`](references/principles.md) before Step 2. Every design choice, scrap, and disposition in this run names the principle that shaped it and the specific choice it changed. Cite only principles from that file.

## Identifiers and state

- `<branch>` is the spec branch, always `specs/<name>`. Normalize the argument: prepend `specs/` when missing. Validate with `git check-ref-format --branch "<branch>"`; on failure stop and ask.
- `<name>` is `<branch>` without `specs/`. The spec lives in `specs/<name>/`.
- `<wt>` is the worktree that has `<branch>` checked out. Every command after Step 0 runs there.
- `<base>` is the refreshed remote default branch ref (Step 1).
- `<scratch>` is `${TMPDIR:-/tmp}/pstack-implement/<repo-id>/<slug>/`. `<repo-id>` is `<repo-dirname>-` plus the first 10 hex characters of `sha1sum` over the absolute path printed by `git rev-parse --path-format=absolute --git-common-dir`. `<slug>` is `<branch>` with each `/` replaced by `-`, plus `-` and the first 8 hex characters of `sha1sum` over the full `<branch>` name, so distinct branches never share a directory. It holds the decision log, review output, and verification evidence. Nothing in it is committed. It is stable across runs so a resumed run finds its own log; each run writes its review, evidence, and PR-body files under `<run-dir>` = `<scratch>/run-<UTC timestamp>/` so runs never overwrite each other.

**Decision log.** Append one TSV row per decision to `<scratch>/decisions.tsv` with columns `ts	phase	decision	why	evidence	result` (header on first write; cells single-line; evidence is a pointer such as a SHA, `file:line`, or a `<scratch>` path, never prose). Log forks chosen, units completed with their check result, scraps and reverts with their trigger, blockers, and dispositions. Append only. A resumed run first writes a row with phase `start`. Plain words, per the prose rules in [`references/cleanup.md`](references/cleanup.md).

**Todo list.** Open one whose first items are the headings of Steps 0 to 10 below, copied verbatim. A step you skip stays in the list as `skip: <reason>`.

## Delegation

The main loop owns, and never delegates: every `AskUserQuestion`, every Skill invocation (`rebase-branch`), the design decisions of Step 3, the checkpoint of Step 4, reviewing each subagent diff, every commit, every disposition, the push, and the PR. Subagents cannot ask the user, so a subagent that hits a product or preference fork stops and returns the question.

Delegate to subagents: bulk reading (Step 2), code writing (Steps 3 arena, 5, 7 fixes), comment review (Step 6), review lanes (Step 7), gates and live verification (Step 8).

Subagent conventions in Claude Code:

- `subagent_type: "Explore"` for read-only work; its brief says "do not edit files", and you check `git status` afterward.
- `subagent_type: "general-purpose"` for anything that writes.
- `model: "opus"` for the hardest code (cross-cutting design, concurrency, subtle algorithms) and for judgment lanes (Claude reviewer, verifier). Omit `model` for routine code.
- `isolation: "worktree"` only for parallel writers and prototypes. The brief names the exact commit to check out first.
- Briefs carry file paths, not pasted content: the spec paths, this skill's `references/` paths, `<scratch>`, the group's scope, the success criteria, and the exact result shape to return.
- **Fresh subagents by default.** A fix round, retry, or follow-up goes to a new subagent with consolidated scope (the original brief, every later directive, and the prior report). Reuse an agent only when the work needs state that lives only in it.
- You own every subagent's output. Read its diff and write your own summary. Never pass its self-report through.

Dispatch independent subagents in one message so they run concurrently.

## Step 0 — Find the spec branch and its worktree

1. Run `git worktree list --porcelain` and look for `branch refs/heads/<branch>`.
   - Found: `<wt>` is that worktree's root.
   - Not found, local branch exists (`git show-ref --verify --quiet refs/heads/<branch>`): attach it with `git worktree add "<wt-path>" "<branch>"`.
   - Not found locally: fetch `git fetch origin "+refs/heads/<branch>:refs/remotes/origin/<branch>"`. On success, `git worktree add --track -b "<branch>" "<wt-path>" "origin/<branch>"`. On failure stop and tell the user to run `/feature-spec <name>` first.
   - `<wt-path>` is `<repo-parent>/<repo-dirname>-worktrees/<branch with each / replaced by ->`, the same path `/feature-spec` uses. Never nest a worktree inside the repo.
2. `cd "<wt>"`. Confirm `specs/<name>/requirements.md`, `plan.md`, and `validation.md` all exist. A missing file is a stop: the spec is incomplete.
3. **Staged changes are a hard stop.** If `git diff --cached --name-only` is non-empty, report and end the run.
4. **The tree starts clean.** If `git status --porcelain=v1 -uall` shows any unstaged or untracked path, ask whether to stash it (`git stash push -u -m "pstack-implement <branch>"`; the Step 10 report names the stash for the user to restore, and this skill never pops it) or abort. Builders, formatters, and commits in this run then own every change in the tree, and Step 9 can require a clean tree before pushing.
5. **Reconcile with the remote before anything else.** Fetch `git fetch origin "+refs/heads/<branch>:refs/remotes/origin/<branch>"` (exit non-zero with "couldn't find remote ref" means unpublished; any other failure is a stop). When the remote branch exists, record `<remote-oid>` = `git rev-parse "refs/remotes/origin/<branch>"`, then: equal to `HEAD`, nothing to do; `HEAD` is an ancestor, fast-forward with `git merge --ff-only "refs/remotes/origin/<branch>"`; remote is an ancestor of `HEAD`, keep local; diverged, stop and ask. Re-record `<remote-oid>` after any fast-forward. It is the lease Step 9 pushes against.
6. **One push destination.** `git remote get-url --push --all origin` must print exactly one URL, and it must equal `git remote get-url origin`. Otherwise stop: the history gate and the push would describe different repositories.
7. Create `<scratch>` and `<run-dir>`. If `<scratch>/decisions.tsv` exists, this is a resumed run: write the `start` row.

## Step 1 — Rebase onto the default branch

Read `${CLAUDE_SKILL_DIR}/../feature-spec/SKILL.md` and follow its **Step 2 default-branch resolution and refresh** (to produce and fetch `<base>`; skip its branch and worktree creation, Step 0 already did that) and these parts of its **Step 2a**: the published-history gate, "Running it" (invoke `/rebase-branch <base>` from `<wt>`, the two "already current" early exits, honoring its gates, the orphaned-stash check). Three changes:

- At the published-history gate the options are **rebase and force-push with a pinned lease in Step 9**, **skip the rebase and implement on the branch as-is**, or **stop**. Record the choice and `<remote-oid>`; only the first unlocks the Step 9 carve-out.
- Skip its "After it returns" phase revalidation. This run implements the named spec; it never picks another roadmap phase.
- **Protect the spec.** You run `rebase-branch` in this conversation, so its Steps 3 and 3a are yours to execute. Before any edit there to a decision, scope item, or validation item in `specs/<name>/`, ask with `AskUserQuestion` and edit only on approval, even where `rebase-branch` would edit without asking. As a backstop, after it returns, run `git diff "<pre-rebase-sha>" HEAD -- "specs/<name>/"` (record `<pre-rebase-sha>` before invoking). A change to a decision, scope item, or validation item goes to the user with `AskUserQuestion`: keep it, or revert it with a new commit. A rebase that changed the spec also sends this run back through Step 2's reconcile.

After it returns, record `<start-sha>` = `git rev-parse HEAD`. Every drift check compares `HEAD` with the tip this run expects: `<start-sha>`, advanced only by commits this run makes.

## Step 2 — Ground the work

Dispatch two read-only `Explore` subagents in one message:

- **Spec brief.** Read the spec trio, `CLAUDE.md` / `AGENTS.md` and every convention or architecture doc they cite, and `specs/roadmap.md`, `specs/mission.md`, `specs/tech-stack.md` if present. Return: the ordered task groups with the failing tests each one lists; the settled decisions from `requirements.md`; each `validation.md` item with how it can be proven (test, command, stored value, UI flow, metric); the repo's binding rules (layering, TDD, logging, safety, commit and PR conventions); and the real format, lint, build, and test commands, including suites CI runs behind tags or separate targets.
- **How it works today.** For each task group, map the subsystem it touches: entry points, data flow, the types and modules that own the concern, the nearest code and test patterns to mirror, and how the running app can be driven for live checks (a project `verify-*` skill under `.claude/skills/`, a CLI, an HTTP endpoint, a UI harness, a seeded dev environment). Return file pointers, not dumps.

Then, in the main loop:

1. **Resume state.** List `git log --format='%H %s' "<base>..HEAD"`. A commit whose subject ends with `(plan group N)` marks group N built. Run that group's tests once; green means skip it, red means a fresh builder repairs it as in Step 5's repair rule. Every later step re-runs in full because each is idempotent.
2. **Reconcile.** Check the brief for contradictions inside the spec, conflicts with repo rules, and decisions the spec left open. Classify each one before asking anything:
   - A fact you can look up: look it up.
   - An empirical fork (behavior, timing, layout, output, perf): settle it with a prototype in Step 3, not a question.
   - A product or preference call no experiment can settle, or a spec contradiction: batch these into one `AskUserQuestion`. Never offer "violate the documented repo rule" as an option.

**Done when** every task group has its files, tests, and patterns named, every validation item has a proof method, and no open question remains unrouted.

## Step 3 — Design before code (architect)

For each task group whose code crosses a function boundary (a new or changed signature, type, or module interface, including inside an existing module):

1. **Usage first.** Write the caller's usage of the new code, then derive the type and signature sketch from it, with `not implemented` bodies.
2. **Name the data shape** and its organizing structure per Model the Domain: a state machine over booleans, a table or union over branching, a typed model over loose parameters. Plain code wins when the current shape is already clear.
3. **Design it twice.** Dispatch two `Plan` subagents in one message (one with `model: "opus"`) for structurally distinct whole-shape candidates. Screen each against the design red flags in [`references/review.md`](references/review.md). Prefer the deeper interface: more complexity hidden behind a smaller surface, and the design where a change that looks right from one file is right for the whole repo. Record the synthesis decision in the log.
4. **Arena** when the sketch still admits several valid implementations (error handling strategy, layer placement, test structure). Two `general-purpose` subagents with `isolation: "worktree"` each implement one candidate from `<start-sha>` plus prior groups. Judge them on tests, red flags, and diff size. Pick a base and graft the best parts. Discard the losers' worktrees.
5. **Prototype** each empirical fork from Step 2 in a throwaway worktree. Measure, decide, log the evidence, delete the prototype.

A group that changes no signature, type, or module interface (a body-only change behind an existing boundary) skips this step with `skip: <reason>`.

**Done when** each designed group has a usage sketch, a named data shape, and a logged decision.

## Step 4 — Throughput checkpoint

Write four todo items and log them. A dimension that does not apply keeps its item as `n/a: <reason>`.

- **Blocking first steps.** Scaffold and subtraction that every later group needs (shared types, test fixtures, dead-code removal). These run first and alone.
- **Independent workstreams.** Groups with disjoint files and packages and no shared artifact. They may build in parallel.
- **Shared mutable state.** Lockfiles, migrations, codegen output, golden files, a public API surface, any file two groups touch. Split the target when possible; otherwise those groups serialize in plan order.
- **Smallest safe decomposition.** One worker or several, and why.

When in doubt, a group is dependent. A race through a shared artifact costs more than the time it saves.

## Step 5 — Build each task group, test first

Process groups in plan order. Serial groups run one at a time in `<wt>`, and builders there never commit. A parallel batch runs with `isolation: "worktree"`; each worker first runs `git checkout --detach <pre-batch sha>`, then makes one transport commit of its group (any subject; the main loop rewrites it) and returns the SHA and its worktree path.

Brief each builder with: the spec paths and its group number; the Step 3 sketch and data shape; the files and packages it may touch, and nothing else; [`references/principles.md`](references/principles.md) and the code-slop and comment rules of [`references/cleanup.md`](references/cleanup.md); the repo's binding rules and test command; and this loop:

1. **Red.** Write the failing tests the group lists, asserting observable behavior derived from the requirement (Test Behavior, Not Implementation). Run them. Confirm each fails for the intended reason, not a compile error or an unrelated red. Where a test would need broad harness setup, brittle mocks, or production-only state, use the closest executable check instead and say why.
2. **Green.** The smallest change that makes them pass, inside the package that owns the concern, honoring the layering rules.
3. **Refactor** while green: intention-revealing names, one abstraction level per function, no duplication the change introduced, no comments except a non-obvious why.
4. Run the touched packages' tests.
5. Return: changed files, the red and green command output tails, every deviation from the sketch and why, and any question it stopped on.

After each serial group, in the main loop:

1. Read the diff. Check it against the sketch, the group's scope, and the spec. A deviation is a signal: decide whether the sketch was wrong, a requirement was missed, or the code overreaches.
2. Re-run the group's tests yourself. Confirm `HEAD` and the branch still match the expected tip.
3. Commit with explicit paths (`git add -- <paths>`; never `-A`). Subject: the repo's convention when it has one, else Conventional Commits, always ending with `(plan group N)`. Advance the expected tip.
4. Log the row: group, check result, SHA.

After a parallel batch, in the main loop. Keep every worker worktree until the batch is integrated.

1. Read each worker's diff with `git -C "<worker-wt>" show <sha>` and judge it as in serial step 1.
2. Cherry-pick the workers' SHAs in plan order. Before each pick, confirm the branch and that `HEAD` equals the expected tip. Pick with `git cherry-pick --no-commit <sha>`, commit with its final `(plan group N)` subject, and advance the expected tip to the new commit before picking the next.
3. A conflict, an empty pick, or a rejected hook: run `git cherry-pick --abort` (or `git reset --hard <last committed group sha>` when only this run's uncommitted pick is in the tree), log it, and rebuild that group serially with a fresh builder on top of the groups already committed.
4. Run the union of the batch's tests at `HEAD`. Red: find the failing group, roll the branch back to the last green commit with `git reset --hard <sha>` (this only discards this run's unpushed commits), set the expected tip to that `<sha>`, and rebuild the rest of the batch serially.
5. Log the batch, then remove the worker worktrees.

**Repair rule.** When a built group goes red later (resume check, Step 7 finding, Step 8 failure), a fresh builder repairs it in `<wt>`, and the main loop commits the repair as its own commit whose subject ends with `(plan group N fix)`. Never a second `(plan group N)` marker. Never rewrite earlier commits.

**Scrap signals.** Stop building and return to Step 3 for the affected groups when the same workaround shape repeats across unrelated code, types need casts or always-set optionals to compile, callers must know an abstraction's internal rules, or two independent deviations share a shape. Redesign as if the new constraint had been there on day one, and subtract before adding. Two failed fixes on one premise trigger Attack the Premise before a third.

**Done when** every task group has a commit whose tests are green at `HEAD`.

## Step 6 — Clean the diff

1. **Deslop findings.** In the main loop, read `git diff "<base>...HEAD"` against the code-slop rules in [`references/cleanup.md`](references/cleanup.md) and list each hit as `file:line` plus the removal, only on lines this branch changed.
2. **Comments.** Dispatch a fresh `general-purpose` subagent with the comments section of that file and the diff scope. It deletes comments and reports `MUST KILL` flags; it edits nothing but comments. Inspect its edits: revert any change outside comments or outside scope. Judge each `MUST KILL` flag; accept those whose root-cause fix fits the spec's scope and report the rest open.
3. **Apply.** Hand the deslop list and the accepted `MUST KILL` flags to one fresh `general-purpose` builder. It applies them, runs the touched packages' tests, and returns the diff. Review the diff in the main loop.
4. Commit any change as `refactor(<scope>): remove slop and redundant comments (pstack cleanup)`. No change means no commit.

## Step 7 — Adversarial review (interrogate)

Write a one-paragraph intent statement from the spec and the commits. Then dispatch two review lanes in one message:

- **Codex lane** (`general-purpose`, `model` omitted). It resolves the companion script with `ls -d ~/.claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs | sort -V | tail -1`, then launches `timeout -k 10 660 node "<companion>" adversarial-review --background --base "<base>" -- "<focus>"` with `run_in_background: true`, passing the flags as separate arguments and `<focus>` as its own argument after `--` (the companion re-splits a single combined string with its own parser, which rewrites quotes and can turn focus text into options) and substituting the resolved `<companion>` path literally, since shell variables do not persist between Bash calls. The `<focus>` is the intent paragraph, the spec paths, and "Judge the branch against specs/<name>/ and the repo's CLAUDE.md. Report numbered findings with file:line, the triggering path, and the suggested change. Do not edit files." It finds the job id with `node "<companion>" status` (the newest adversarial-review job), polls `node "<companion>" status <job-id> --wait --timeout-ms 240000 --json`, fetches `result <job-id>`, saves the output verbatim to `<run-dir>/review-codex.md`, and returns it. Hard deadline 10 minutes; a dead pid or a log silent for 5 minutes counts as stalled; on either it runs `cancel <job-id>` and returns "codex failed: <reason>". Without the companion script it runs `timeout -k 10 600 codex exec --sandbox read-only -C "<wt>" -o "<run-dir>/review-codex.md" "<focus> Review exactly the changes in git diff <base>...HEAD; read surrounding code as needed."` and treats a non-zero exit (124, or 137 after the kill, is the timeout) or an empty output file as "codex failed: <reason>". Without `codex` on `PATH` it returns "codex unavailable".
- **Claude lane** (`general-purpose`, `model: "opus"`). Its brief is the reviewer section of [`references/review.md`](references/review.md), the intent paragraph, the spec paths, `<base>`, and the file list from `git diff --name-status "<base>...HEAD"`. It saves its output to `<run-dir>/review-claude.md`.

If the codex lane fails, dispatch a second fresh Claude reviewer focused on spec fidelity and verification, so two independent reviews still exist. Never retry codex and never ask about it; record the reason.

Then apply the lead judgment in [`references/review.md`](references/review.md): merge, bucket, and assign accept, defer, or reject with a one-line reason and the lane that raised it. Present the table and the agreement map to the user without waiting for a reply.

Fix every accepted finding with a fresh `general-purpose` subagent, test first for anything behavioral. When a finding admits several fixes, classify the fork as in Step 2: pick by evidence or a prototype when the difference is observable, and use lead judgment for a reversible technical call. Ask with `AskUserQuestion` only for an invasive fix (public API change, new dependency, files outside the spec's scope), a product or preference call, or a finding that would change a settled spec decision. A fix that changes behavior gets one fresh verifier subagent that rereads that fix against its finding. Commit as `fix(<scope>): address review findings (pstack review)`.

## Step 8 — Prove it works

**8a. Gates.** Dispatch a `general-purpose` subagent to run the repo's real gates over the whole branch, in order: format (apply, then check mode), lint, build, full test suite including the CI-only suites. Each gate returns `pass`, `fail` with only the failing output, `not configured` (searched and absent), or `not run` (needs unavailable infrastructure, with the reason). After the gates, any change in `git status --porcelain=v1 -uall` belongs to this run: formatter output and lint autofixes are committed as `style(<scope>): apply formatter (pstack gates)`. A change to logic, control flow, error handling, or test assertions is committed as `fix(<scope>): <subject> (pstack gates)`, then reviewed by both Step 7 lanes scoped to that commit only (`git diff <prior tip> HEAD` in place of `<base>...HEAD`), and its accepted findings fixed before moving on. Then re-run the gates on the committed tree. On a failure caused by this branch, fix the root cause with a fresh subagent and re-run all gates. For a failure that looks pre-existing, reproduce it at `<start-sha>` in a throwaway worktree (`git worktree add --detach`), then remove the worktree. Pre-existing: ask to fix it, abort, or commit under a documented waiver. Passes at `<start-sha>`: it is this branch's failure; fix it.

**8b. Independent verification.** Dispatch a fresh `general-purpose` verifier with `model: "opus"`, which wrote none of the code. For each `validation.md` item, it proves the requirement on the real artifact and returns `pass`, `fail`, or `inconclusive` with an evidence path under `<run-dir>/evidence/`. Surface order: the project's `verify-*` skill when one exists; else the real command, HTTP request, stored value read back, or UI flow driven with the session's browser tooling; else a small throwaway driver script in `<run-dir>` when the item requires live behavior and the driver is cheap. Tests passing is evidence only for items that are tests. A check that cannot run on the right surface is `inconclusive`, never `pass`.

When `validation.md` names a performance metric, the verifier measures it at `<base>` and at `HEAD` in separate worktrees, interleaved, at least 5 runs each, and reports median, range, and the named limiter. It reports faster, slower, no measurable difference, or inconclusive against the spec's threshold.

A `fail` sends its task group back to Step 5 with a fresh builder and the evidence, then through Step 7 for the fix and Step 8 again. `inconclusive` items ship only as named gaps in the PR and the report.

**8c. Spec write-back.** Reconcile every checkbox in `specs/<name>/validation.md` with this run's evidence: `- [x]` for each item that passed, `- [ ]` for each item that failed or is inconclusive, including a box an earlier run ticked. When the implementation deviated from a decision in `requirements.md`, ask with `AskUserQuestion` whether to record the deviation; on approval, add it to the Decisions section. When these files changed, commit only them as `docs(specs): record <name> validation results`. No change means no commit.

**Done when** every gate is `pass` or `not configured` (or waived by the user), and every validation item is `pass` or a named `inconclusive`.

## Step 9 — Push and open the PR

1. **Preflight.** `git rev-parse --abbrev-ref HEAD` equals `<branch>`. `HEAD` equals the expected tip. `git remote get-url origin` succeeds. `git status --porcelain=v1 -uall` is empty: every change this run made is committed. Any failure is a stop.
2. **Push** with an explicit refspec: `git push -u origin "HEAD:refs/heads/<branch>"`. A non-fast-forward rejection is a stop, unless the user chose rebase and force-push at the Step 1 gate: then retry once with `git push -u --force-with-lease="refs/heads/<branch>:<remote-oid>" origin "HEAD:refs/heads/<branch>"`. The pinned `<remote-oid>` makes the push fail if anyone pushed since the gate. Never `--force`, never another remote.
3. **Resolve the repository once.** Parse `<host>/<owner>/<repo>` from `git remote get-url origin` (HTTPS or `git@host:owner/repo.git`). Run `gh auth status --hostname "<host>"`. When `gh` is missing, unauthenticated, or the host is not GitHub, skip the PR and give the exact `gh pr create` command in the report. Pass `--repo "<host>/<owner>/<repo>"` to every `gh` command below. The PR merges into the same repository it was pushed to, so `<default-branch>` is the branch name inside `<base>`.
4. **PR.** List `gh pr list --repo "<host>/<owner>/<repo>" --head "<branch>" --state all --json number,state,isDraft,baseRefName,headRepositoryOwner,headRepository` and keep only PRs whose head repository is `<owner>/<repo>` (case-insensitive).
   - An open match with base `<default-branch>`: update its title and body with `gh pr edit`, and run `gh pr ready` if it is a draft.
   - An open match with another base: ask whether to update it anyway (it stays on its base, and the report says review and verification measured `<base>`) or open a new PR against `<default-branch>`. Never retarget a base on your own.
   - Only closed or merged matches: ask whether to open a new PR or skip. Never reopen.
   - No match: `gh pr create --repo "<host>/<owner>/<repo>" --base "<default-branch>" --head "<branch>" --title "<title>" --body-file "<run-dir>/pr-body.md"`, without `--draft`.
   Write the title and body per the PR section of [`references/cleanup.md`](references/cleanup.md), then apply its prose rules. Use the repo's PR template when it has one. Append any attribution lines the environment requires.
5. Confirm `gh pr view <number> --repo "<host>/<owner>/<repo>" --json url,headRefOid,isDraft` shows `headRefOid` equal to `HEAD` and `isDraft` false. GitHub updates the head asynchronously; re-query for about 30 seconds before reporting a mismatch.

Stop at the open PR. Babysitting and merging are separate decisions.

## Step 10 — Report

Before writing, audit the decision log: each row maps to something that happened and its evidence resolves.

Write the reply per the prose rules in [`references/cleanup.md`](references/cleanup.md). Lead with what changes for the consumer (end user, caller, colleague importing the code) and for the next maintainer. Then:

- What was built, per task group, with commit SHAs.
- The design choices and the principle behind each, as a table when alternatives were weighed.
- The throughput checkpoint and what ran in parallel.
- The Step 1 rebase outcome.
- Review: the lanes that ran (and why codex fell back, if it did), finding counts, the accept, defer, and reject breakdown with one-line reasons.
- Verification: each gate with its command and state; each validation item with pass, fail, or inconclusive and its evidence path; perf numbers with run count, spread, and limiter.
- Any stash Step 0 created, with the command to restore it.
- Push outcome and the PR URL from the Step 9 `gh pr view`, created or updated.
- Open decisions, deferred findings, inconclusive items, and remaining risk.
- The decision log path.

Label every claim measured, inferred, or guess. Never hand the user a check you could run.

## Stop-and-ask conditions

Ask with `AskUserQuestion` only for these; everything else proceeds and is reported:

- The branch name is invalid, the tree is dirty, or local and remote spec branches diverged (Step 0).
- The published-history gate before the rebase, any gate `rebase-branch` raises, and any spec change the rebase made (Step 1).
- A spec contradiction, a conflict with a repo rule, or a product or preference call no experiment can settle (Step 2, and any subagent that returns one).
- An invasive review fix, a product or preference call inside a fix, or a finding that would change a settled spec decision (Step 7).
- A pre-existing red gate (Step 8a).
- Recording a deviation in `requirements.md` (Step 8c).
- Only closed or merged PRs exist for the branch, or the open one targets another base (Step 9).

Hard stops, reported without a question: staged changes in the worktree, a missing spec file, more than one push URL, a failed fetch or preflight, a non-fast-forward push without the Step 1 approval, a failed `gh` call. Irreversible actions not listed here (deleting branches, force-pushing without approval, merging) never happen in this skill.

## Notes

- This skill adapts pstack from `github.com/cursor/plugins/tree/main/pstack` (commit `eb4db2b`, MIT; see [`references/PSTACK-LICENSE`](references/PSTACK-LICENSE)). It does not require the pstack plugin. pstack's ten-lane live swarm, Bugbot triage, stacked PRs, and babysit loop are out of scope by design: one ready PR with independent verification is the deliverable.
- Worktrees made for parallel builders, arena candidates, prototypes, and baselines are removed after use. The spec worktree stays; the user removes it after merge with `git worktree remove "<wt>"`.
