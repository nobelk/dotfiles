---
name: spec
description: "Writes the spec for one roadmap phase. Grills the user on scope, key decisions, test seams, and validation, then writes specs/<name>/{requirements,plan,validation}.md on a specs/<name> branch in its own git worktree, marks the phase `in progress` in specs/roadmap.md, codex-reviews the files, commits them, and pushes the branch for /code to build on. Takes a branch name (auto-prefixed with specs/; derived from the roadmap if omitted). Use when starting a new feature, speccing the next roadmap phase, or turning a /constitution roadmap phase into a buildable plan."
---

# Spec skill

Turn one roadmap phase into three planning docs under `specs/<name>/`: `requirements.md`, `plan.md`, and `validation.md`. They are written only after a grilling session has settled every open decision. Codex then reviews them, the valid findings are folded back in, and the result is committed and pushed on its own `specs/<name>` branch.

This is the middle of three stages. `/constitution` wrote the mission, the engineering standards, and the roadmap this spec has to fit. `/code` then builds on **this same branch and worktree**, so the phase lands as one PR: spec, code, tests, and the roadmap flip to `done`. `/code`'s implementers are subagents that can't ask the user anything, so every decision recorded here saves an interruption there, and every one left out becomes a guess.

Identifiers, all derived from one input:

- `<branch-name>`: the git branch, always under `specs/` (e.g. `specs/2026-05-05-firefly`).
- `<name>`: `<branch-name>` without the leading `specs/`. It names the docs directory `specs/<name>/`, which avoids `specs/specs/...` nesting. A name with slashes nests to match.
- `<slug>`: `<branch-name>` with `/` replaced by `-`.
- `<wt-path>`: `<repo-parent>/<repo-dirname>-worktrees/<slug>`, beside the repo and never inside it. The repo here is the **main** worktree (the first `worktree` line of `git worktree list --porcelain`), not a linked worktree the session may still be in from an earlier phase.

The main loop owns everything that talks to the user or rests on their decisions: the grilling, the writing, every question, the final call on each review finding, and all git work. Subagents take the bulky, self-contained work: exploring the code, the codex run, and the adjudication of a long list of findings. Give each one a self-contained prompt with absolute paths, the exact commands, and the result shape you want back.

## Step 1 - Resolve the base and pick the phase

**Require `origin`.** Step 8 pushes there. If `git remote get-url origin` fails, report that and end the run now rather than after the spec is written.

**Resolve `<base>`**, the default branch as a remote ref: `git symbolic-ref --short refs/remotes/origin/HEAD` (e.g. `origin/main`), else the `ref: refs/heads/<default>` line of `git ls-remote --symref origin HEAD`, else ask the user. Then refresh it, together with the spec branches, using explicit refspecs, because a narrowed clone can otherwise update only `FETCH_HEAD`:

```bash
git fetch --prune origin '+refs/heads/<default>:refs/remotes/origin/<default>' '+refs/heads/specs/*:refs/remotes/origin/specs/*'
git rev-parse --verify refs/remotes/origin/<default>
```

If either fails, stop. A spec written against a stale tip describes code that has already changed.

**Pick the phase** from the roadmap as it is on `<base>` (`git show <base>:specs/roadmap.md`), because the worktree is cut from `<base>` and sees only what has landed there:

- If the user named a phase, or the branch-name argument clearly matches one, use it.
- Otherwise take the first `not started` phase that isn't **in flight**. The default branch learns about a phase only when its PR merges, so a phase is in flight when an `origin/specs/*` branch's copy of the roadmap marks it `in progress`:
  ```bash
  for b in $(git for-each-ref --format='%(refname:short)' refs/remotes/origin/specs/); do
    echo "== $b"; git show "${b}:specs/roadmap.md" 2>/dev/null | grep -B1 -F -e '**Status:** in progress'
  done
  ```
  Keep the braces in `${b}:specs`: zsh reads `$b:s...` as a substitution modifier and silently shows the commit instead of the file.
- In a roadmap without status fields, take the first phase with no `specs/<name>/` directory on `<base>`.

If the chosen phase depends on a phase that isn't `done` on `<base>`, the code it builds on isn't in the tree this spec will be written against. Tell the user and ask whether to wait or go ahead.

If `<base>` has no roadmap:

- The user's checkout has one that is uncommitted or unpushed: the constitution hasn't landed. Stop and ask the user to get it onto the default branch first.
- There is none anywhere: ask the user what to spec, and suggest `/constitution` first rather than inventing a phase.

If the main worktree has uncommitted edits to the constitution (`git status --porcelain -- specs/mission.md specs/tech-stack.md specs/roadmap.md`), a revision hasn't landed. Tell the user this spec will be written against the versions on `<base>`, and ask whether to go on.

## Step 2 - Name the branch and enter its worktree

`<branch-name>` is the argument with `specs/` prepended if it's missing. With no argument it is `specs/<today>-<phase>`: the local date as `YYYY-MM-DD`, then the phase name in kebab case, four words at most. Validate it with `git check-ref-format --branch "<branch-name>"`; if that fails, ask the user for a corrected name rather than sanitizing it yourself.

Then find where the branch stands:

- **It doesn't exist** (no local branch, no `origin/<branch-name>`): `git worktree add <wt-path> --no-track -b <branch-name> <base>`.
- **A worktree has it checked out** (`git worktree list --porcelain` shows `branch refs/heads/<branch-name>`): reuse that worktree.
- **It exists without a worktree:** `AskUserQuestion` whether to attach it, pick a different name, or, for a branch that was never pushed, delete it and start fresh. Attach a local branch with `git worktree add <wt-path> <branch-name>`, and one that is only on `origin` with `git worktree add <wt-path> -b <branch-name> origin/<branch-name>`.

Move the session into the worktree with the `EnterWorktree` tool (`path: <wt-path>`; it is a deferred tool, so load it with `ToolSearch` first). If the session is inside a different worktree, leave that one first with `ExitWorktree` (`action: "keep"`). From here on every command, sub-skill, and subagent runs in the worktree, and the user's own checkout is never touched. Where the tool isn't available or refuses the path, prefix each command with `cd <wt-path> &&` and give subagents the absolute path.

**A reused branch has to contain `<base>`**, so the spec describes code on top of the current default branch. A new branch already does. For a reused one:

1. If `origin/<branch-name>` has commits this worktree lacks, `git merge --ff-only origin/<branch-name>`, and stop if it can't fast-forward. Left alone, Step 8's push would be rejected after the whole session.
2. If `git merge-base --is-ancestor <base> HEAD` succeeds, the branch is current and the rest of this list doesn't apply.
3. Otherwise the tree must be clean (`git status --porcelain` is empty). If it isn't, stop and report; a stash taken here is easy to strand.
4. If no commit above `<base>` is published (`git rev-list <base>..origin/<branch-name>` is empty, or the branch isn't on `origin`), invoke the `rebase` skill with `<base>`. Let its questions, review, and gates run. If it aborts, stop rather than write a spec onto a half-integrated tree.
5. Otherwise a rebase would rewrite published commits, and this skill never force-pushes. `AskUserQuestion`: **merge `<base>` into the branch**, **spec against the branch as it is** (the report notes the staleness), or **stop**.

After a rebase or merge, check the phase again: the default branch may have changed the roadmap or delivered the phase already.

## Step 3 - Read the constitution and the code

In one message, in the worktree:

- Read the phase's roadmap entry and `specs/mission.md`, which bound the scope.
- Read `specs/tech-stack.md`. Its *Architecture and conventions* and *Testing and quality gates* sections are the engineering standards the plan has to follow.
- Read `CLAUDE.md` / `AGENTS.md` and the architecture or convention docs they cite. Their rules bind the plan too, and win where they are more specific.
- Launch an `Explore` subagent over the code this phase will touch: the packages involved, their public interfaces, and how the existing tests reach them. The seams and task groups below are only as good as this picture.

If `mission.md` or `tech-stack.md` is missing, note it, mention `/constitution`, and carry on with what you have.

## Step 4 - Grill the user (`grilling` skill)

Invoke **`mattpocock-skills:grilling`** with the Skill tool and run its session to completion.

Seed the design tree from the roadmap entry and the Step 3 reads, so every question and recommended answer is specific to this phase. Cover at least:

- **Scope:** what is in and out for this phase. The roadmap entry is the starting point, not the final word.
- **Key decisions:** every consequential open choice (library, data model, sync vs. async, auth, ...), each with its trade-off. A choice the spec makes without the user gets frozen silently.
- **Test seams:** the public interfaces this phase's tests will exercise, each with a one-line note on what it catches and what it misses. The `tdd` skill that `/code` follows allows no test at an unconfirmed seam, so confirming them here is what lets `/code` build without stopping to ask.
- **Validation:** how we will know the phase is done (tests, manual QA, metrics, ...).
- **Repo-mandated content:** anything `CLAUDE.md` / `AGENTS.md` requires a spec to state. Each one is a decision for the user, even when the answer looks obvious.

Ask only questions whose answer changes the spec.

**Done when** the frontier is empty and the user confirms you share an understanding. List the settled decisions as `D1`, `D2`, ... in the conversation; Step 5 writes from them and Step 7 checks findings against them. Write nothing under `specs/<name>/` until then.

## Step 5 - Write the spec files and mark the phase

If `specs/<name>/` already exists, `AskUserQuestion` whether to overwrite, append, or pick a different name. A new name goes back to Step 2, so the branch and the directory keep matching.

Write for an implementer who reads these files cold and can't ask what you meant.

### `requirements.md`

- **Context:** a short paragraph tying this phase to the roadmap (name the phase by number and name), the mission, and the tech stack.
- **Scope:** `In:` / `Out:` lists, from the settled scope decisions.
- **Decisions:** every other settled decision, numbered `D1`, `D2`, ... as in the session, plus the constraints inherited from the mission and tech stack.

### `plan.md`

Open with a short **Standards** section. Name the documents that govern this plan (the two `tech-stack.md` sections, `CLAUDE.md` / `AGENTS.md`, any doc they cite) rather than restating them, and add only what is specific to this phase: for example a design pattern a task group needs, named by its well-known name with the reason plain code isn't enough. Where the repo documents no standards at all, state the defaults here instead: dependencies point inward, behavior changes are test-first through public interfaces, plain code before patterns, and style follows the surrounding code.

Then write the **task groups**, numbered, in this shape:

```markdown
## 2. <Task group name>
- **Depends on:** 1
- **Seam:** <the agreed public interface its tests exercise>
- **Tests first:** <the behaviors to pin, each as a failing test written before its code>
- **Then:** <the code, migrations, or config that make them pass, and the package or layer they land in>
```

`/code` runs the groups as a task graph: a group starts once the groups it depends on are merged, and independent groups are built in parallel by separate subagents. That shapes how to cut them:

- **Each group is a vertical slice** that leaves the branch building and its tests green, and is small enough for one implementer. Group 1 is the smallest slice that works on its own.
- **`Depends on` lists only real blockers** (`-` for none). Every needless edge forces work into sequence.
- **Groups that can run side by side edit different files.** If two groups need the same file, make one depend on the other.
- **Every group names a seam from the settled list.** A group that needs a seam nobody agreed to means Step 4 isn't finished.

### `validation.md`

- **Success criteria:** from the settled validation decisions.
- **Checklist:** concrete checkboxes for the tests to add, the repo's quality gates (format, lint, build, the full test suite, any architecture or static-analysis checks), manual checks, and metrics to confirm. `/code` ticks the boxes it verifies and leaves the manual ones for the PR's reviewer.
- **Done when:** one line naming the binary signal, consistent with the roadmap entry's own `Done when`.

### Roadmap status

If the phase has a `Status:` line in `specs/roadmap.md`, set it to `in progress`. That is the only change to `roadmap.md`. If the roadmap has no status fields, or already had uncommitted changes you didn't make, leave it alone and say so in the report.

## Step 6 - Codex review (in a subagent)

Get an independent second-model review. Launch a `general-purpose` subagent and point it at `references/codex-review.md` in this skill's directory, which holds its instructions. Give it:

- `<dir>`: the worktree root.
- `<tag>`: `spec-<slug>-<random>`.
- `<scratch>`: `/tmp/codex-spec-review-<slug>.md`.
- `<focus>`:

> Review these planning documents: specs/<name>/requirements.md, specs/<name>/plan.md, specs/<name>/validation.md. Also read specs/roadmap.md, specs/mission.md, specs/tech-stack.md, and CLAUDE.md / AGENTS.md plus any convention or architecture docs they cite, if they exist; the specs must be consistent with them. Review for: internal contradictions between the three files; scope items in plan.md missing from requirements.md and vice versa; validation criteria that don't verify the stated requirements; ambiguous or untestable success criteria; missing edge cases or risks; scope that strays outside this phase's roadmap entry or works against the mission's non-goals; and conflicts with the tech stack or its engineering standards. Check plan.md's task groups as a task graph: a missing, circular, or needless "Depends on" edge; groups that could run in parallel but edit the same files; a group that is not a vertical slice, would leave the branch broken, or is too large for one implementer; a group with no seam, or tests not listed before the code they pin; needless abstractions; and steps that would break the repo's dependency and layering boundaries or produce untestable code. For each finding, output a numbered item with the file, the issue, and the suggested change. Output findings only; do not rewrite the documents.

If it returns `codex failed`, tell the user and `AskUserQuestion`: **retry the codex review**, **substitute a self-review** (adversarial `general-purpose` subagents given the same focus text, whose findings go through Step 7), **skip the review and commit and push the unreviewed spec**, or **skip the review and stop without committing**. Go on to Step 8 only if the chosen option allows it.

## Step 7 - Adjudicate the findings and update the spec

Codex's findings are hypotheses, not instructions. With more than about 5, split them into batches of 3-5 (contradictory findings share a batch) and launch one subagent per batch in a single message, each with the settled decisions and the constitution's constraints; the final call on each finding stays here. For each finding:

1. Re-read the cited passage and confirm the issue is real.
2. Check it against the settled decisions, the mission, and the tech stack.
3. Give it a disposition:
   - **accept** - a real gap or contradiction. Edit the file(s), keeping each edit traceable to its finding number.
   - **reject** - wrong, a deliberate scope cut, or only preferring a different choice than one the user made. Say why.
   - **defer** - valid but it belongs to a later phase, or needs a user decision that can wait. Say where it goes.

A finding you would otherwise accept that changes a settled decision (wider scope, a different key choice, a new seam), or one showing that a decision rests on a wrong fact or is unsafe, is the user's call. Reopen that branch with the grilling skill, update the decision list, and then edit. Show the user the full disposition table.

## Step 8 - Commit and push

This runs without a confirmation prompt, because the worktree guarantees `HEAD` is the `specs/<name>` branch. Every failure below is a stop: report the exact error and end the run. Pushes are plain fast-forward pushes to `origin`.

1. **Preflight:** `git rev-parse --abbrev-ref HEAD` equals `<branch-name>`, and `git diff --cached --name-only` is empty.
2. **Stage by explicit path:**
   ```bash
   git add -- specs/<name>/requirements.md specs/<name>/plan.md specs/<name>/validation.md
   git add -- specs/roadmap.md   # only if Step 5 changed its status line
   ```
   Confirm `git diff --cached --name-only` lists exactly those paths. Leave anything else `git status` shows untouched, and mention it in the report.
3. **Commit** in the repo's convention: a subject style set in `CLAUDE.md` or the repo docs, else the style of recent `git log` subjects (a ticket-key prefix only when the name or roadmap carries a key), else `docs(specs): add <name> spec`. Add any trailers the environment requires. The body lists the files and gives the codex outcome in one line.
4. **Push:** `git push -u origin <branch-name>`. On a failure, leave the commit in place. `/code` opens the PR, so don't open one here unless the user asks.

## Step 9 - Report

- The three spec paths, each with a one-sentence summary, the number of task groups, and whether the roadmap status was updated.
- How the worktree was set up: new or reused, and for a reused one what Step 2 did (already current, rebased or merged onto `<base>` at `<sha>`, or left stale and why).
- The codex outcome: the total, the accept / reject / defer counts, and a one-line reason for each rejection (or which Step 6 option was taken and why).
- The commit hash and subject, the branch pushed, and the worktree path. If Step 8 stopped, which check failed and its exact error.
- Next step: `/code <name>`. This session is already in the worktree `/code` works in. The worktree stays until the phase's PR has merged; the user removes it then (`git worktree remove <wt-path>`, then `git worktree prune`).
