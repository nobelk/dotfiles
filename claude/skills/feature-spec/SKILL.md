---
name: feature-spec
description: Writes the planning spec for the next roadmap phase. Grills the user on scope, key decisions, and validation, then writes specs/<name>/{requirements,plan,validation}.md on a specs/<name> branch in its own git worktree, marks the phase `in progress` in specs/roadmap.md, codex-reviews the files, commits them, and pushes the branch. Takes a branch name (auto-prefixed with specs/; derived from specs/roadmap.md if omitted). Use when starting a new feature, speccing the next roadmap phase, or turning a /constitution roadmap phase into a buildable plan.
---

# Feature spec skill

Turn one roadmap phase into three planning docs under `specs/<name>/`: `requirements.md`, `plan.md`, `validation.md`. They are written only after a grilling session has settled every open decision. Codex then reviews them, the valid findings are folded back in, and the result is committed and pushed on its own `specs/<name>` branch. `/implement-plan` builds from `plan.md` later.

There are two identifiers, both derived from one input:
- `<branch-name>` is the git branch, always under `specs/` (e.g. `specs/2026-05-05-firefly`).
- `<name>` is `<branch-name>` without the leading `specs/`. It names the docs directory `specs/<name>/`, which avoids `specs/specs/...` nesting.

## Subagent delegation

- **Main loop owns:** name normalization and worktree setup (Steps 0-2a), the grilling session (Step 3; the Skill tool runs in this conversation and subagents cannot prompt the user), writing the spec files (Step 4), every `AskUserQuestion`, routing decision-changing findings back to the user, the commit and push (Step 7), and the report.
- **Delegate to `general-purpose` subagents:**
  - **Step 5:** launch the codex review, wait for it under the deadline, and return the raw findings verbatim (or `codex failed: <reason>`). The codex transcript stays in the subagent.
  - **Step 6, only with more than about 5 findings:** split them into disjoint batches of 3-5 (contradictory findings share a batch) and launch one adjudication subagent per batch in a single message. Each one gets the settled decisions and the mission/tech-stack constraints, and returns its slice of the disposition table.

Give each subagent a self-contained prompt with absolute paths inside the worktree, the exact commands, and the result shape you want back. Run independent work in parallel: the Step 1 reads are independent, and so are the Step 6 batches.

## Step 0 - Normalize the branch name and find any existing worktree

- **With an argument:** prepend `specs/` if it's missing (`feat-x` → `specs/feat-x`).
- **Without one:** the name is derived in Step 2, after the roadmap is read. Run the checks below on it then.

Validate with `git check-ref-format --branch "<branch-name>"`. If it fails, ask the user for a corrected name rather than sanitizing it yourself.

Then check `git worktree list --porcelain` for `branch refs/heads/<branch-name>`:
- **A worktree has it checked out:** reuse that worktree. This is a *reused branch* (see Step 2a).
- **The branch exists locally but no worktree has it:** `AskUserQuestion` whether to attach it to a new worktree (a reused branch), pick a different name, or delete it and recreate it fresh.
- **Neither:** Step 2 creates the branch in a new worktree.

## Step 1 - Read the roadmap and constitution

In parallel, read whichever of these exist:
- `specs/roadmap.md`: pick the phase to spec. If the user named a phase, or the branch name clearly matches one, use that phase. Otherwise take the first phase whose `Status` is `not started`. In a roadmap without status fields, take the first phase with no `specs/<name>/` directory yet.
- `specs/mission.md`: the product north star, which bounds scope.
- `specs/tech-stack.md`: the tech choices and quality gates `plan.md` must use.
- `CLAUDE.md` / `AGENTS.md` and the architecture or convention docs they cite: layering rules, TDD mandate, test idioms, and gates that `plan.md` and `validation.md` must respect.

If `specs/roadmap.md` is missing, stop and ask the user what to spec. Suggest running `/constitution` first rather than inventing a phase. If `mission.md` or `tech-stack.md` is missing, note it, mention `/constitution`, and carry on with what you have.

## Step 2 - Resolve the base and create the worktree

If no name was given, derive `<branch-name>` as `specs/<today>-<feature-name>`, where `<feature-name>` is the phase name in kebab case (four words at most) and `<today>` is the local date in `YYYY-MM-DD`. Run Step 0's validation and worktree check on it.

**Require `origin`.** Step 7 pushes there. If `git remote get-url origin` fails, report that and end the run now rather than after the specs are written.

**Resolve `<base>`**, the default branch as a ref, taking the first of these that works:
1. `git symbolic-ref --short refs/remotes/origin/HEAD` (e.g. `origin/main`).
2. `git ls-remote --symref origin HEAD`, looking for a `ref: refs/heads/<default>	HEAD` line, which gives `origin/<default>`. A success with no such line counts as no answer.
3. A local `main` or `master`. If it tracks a remote branch (`git rev-parse --abbrev-ref <branch>@{upstream}`), use that remote-tracking ref instead.
4. Nothing resolved: ask the user which branch to base on.

Use `<base>` verbatim from then on; it is already remote-qualified.

**Refresh it** when it is a remote-tracking ref `<remote>/<default>`. Fetch with an explicit refspec, because a narrowed or single-branch clone can otherwise update only `FETCH_HEAD`:

```bash
git fetch <remote> '+refs/heads/<default>:refs/remotes/<remote>/<default>'
git rev-parse --verify refs/remotes/<remote>/<default>
```

Both commands must name the remote and branch that `<base>` actually resolved to. If either fails, stop; don't fall back to a possibly stale local tip.

**Create or attach the worktree** at `<wt-path>` = `<repo-parent>/<repo-dirname>-worktrees/<slug>`, where `<slug>` is `<branch-name>` with `/` replaced by `-`. Never nest a worktree inside the repo itself.
- **New branch:** `git worktree add <wt-path> -b <branch-name> <base>`.
- **Existing worktree:** use it as it is.
- **Attach chosen:** `git worktree add <wt-path> <branch-name>`.
- **Recreate chosen** (the user already confirmed the delete in Step 0): `git branch -D <branch-name>`, then the new-branch command.

`cd` to the worktree root. Every later step runs there, and the user's original checkout is never touched.

## Step 2a - Bring a reused branch up to date

A new branch was just cut from the freshly fetched `<base>`, so it is already current; skip this step for it. For a reused branch, the specs must describe code on top of the current default branch rather than a stale one:

1. **Already current?** If `git merge-base --is-ancestor <base> HEAD` succeeds, skip to Step 3.
2. **Clean tree required.** If `git status --porcelain` shows anything, stop and report it. Don't stash: a stash taken here is easy to strand if the rebase is aborted. The user can commit or discard the changes and rerun.
3. **Check what is published** at `origin/<branch-name>`:
   ```bash
   git ls-remote --exit-code origin refs/heads/<branch-name>   # 0 = published, 2 = not published
   ```
   - **Exit 2:** not published, so it's safe to rebase.
   - **Any other non-zero exit:** a failure (auth, network), not an absence. Stop and report it.
   - **Exit 0:** fetch it with `git fetch origin '+refs/heads/<branch-name>:refs/remotes/origin/<branch-name>'`, then:
     - If `git merge-base --is-ancestor origin/<branch-name> HEAD` fails, the remote has commits this worktree lacks. Stop and tell the user to integrate them first.
     - If `git rev-list <base>..origin/<branch-name>` is non-empty, a rebase would rewrite published commits, and Step 7 never force-pushes. `AskUserQuestion`: **skip the rebase and spec against the branch as is** (note the staleness in the report), **pick a different branch name** (loop back to Step 0), or **stop**.
     - Otherwise every published commit is already in `<base>`, so it's safe to rebase.
4. **Rebase.** Invoke the `rebase-branch` skill with `<base>` as its argument. It owns conflict resolution and its own questions; let them run. If it aborts, or the user aborts one of its questions, stop this skill too rather than writing specs onto a half-integrated tree. It also runs its own codex review and project gates over the branch. Let those finish, but they don't replace Step 5, which reviews the spec files against the constitution.
5. **Re-read everything from Step 1** in the rebased tree, and check the chosen phase again. The default branch may have changed the roadmap or delivered the phase already; if so, pick the next unstarted phase, or ask.

## Step 3 - Grill the user (`grilling` skill)

Before writing anything, invoke `mattpocock-skills:grilling` with the Skill tool and run its session to completion. It is the skill `/grill-me` loads; call it by this name, because `/grill-me` sets `disable-model-invocation` and the Skill tool refuses it.

Seed the design tree from the phase's roadmap entry and the Step 1 docs, so every question and recommended answer is specific to this phase. Cover at least:
- **Scope:** what is in and out for this phase. The roadmap entry is the starting point, not the final word.
- **Key decisions:** every consequential open choice (library, data model, sync vs. async, auth, ...), each with its trade-off. A choice the spec makes without the user gets frozen silently.
- **Validation:** how we will know the phase is done (unit and integration tests, manual QA, metrics, ...).
- **Repo-mandated content:** anything `CLAUDE.md` / `AGENTS.md` requires a spec to state. Each one is a decision for the user, even when the answer looks obvious.

Ask only questions whose answer changes the spec. What the repo's docs already settle is a fact, and finding facts is your job.

**Done when** the frontier is empty and the user confirms you share an understanding. List the settled decisions as `D1`, `D2`, ... in the conversation; Step 4 writes from them and Step 6 checks findings against them. Write nothing under `specs/<name>/` until then.

## Step 4 - Write the spec files and mark the phase

If `specs/<name>/` already exists, `AskUserQuestion` whether to overwrite, append, or pick a different name. A new name loops back to Step 0, so the branch and the directory keep matching.

### `requirements.md`
- **Context:** a short paragraph tying this phase to the roadmap, mission, and tech stack.
- **Scope:** `In:` / `Out:` lists, from the settled scope decisions.
- **Decisions:** every other settled decision, plus constraints inherited from the mission and tech stack.

### `plan.md`
Open with a short **Engineering standards** section, stated once. Where these overlap with the repo's own documented conventions, the repo's version wins:
- **TDD:** behavior changes are test-first. Each group lists the failing tests to write before the code that makes them pass.
- **Clean architecture:** keep the repo's dependency boundaries. Where it defines layered or hexagonal rules, dependencies point inward (consumer-defined interfaces, domain logic free of transport/DB/framework concerns).
- **Standard design patterns:** where a group needs a non-obvious abstraction, name the well-known pattern (Strategy, Repository, Ports & Adapters, Functional Options, ...) and why. Plain code wins when it is enough, and pattern names stay in the plan, not in code identifiers.
- **Clean, idiomatic code:** small, single-purpose units with names that say what they do, and no duplication introduced by the change. Style precedence: documented repo rules, then the surrounding code's idiom, then the language's community conventions.

Then write **numbered task groups** (`## 1. Schema migration`), each with a few bullets on the concrete code, migrations, and tests: its tests, the package or layer it lands in, and any pattern decision. Don't restate the standards in each group. Order the groups so each could land as its own commit; group 1 is the smallest slice that is mergeable on its own.

### `validation.md`
- **Success criteria:** from the settled validation decisions.
- **Checklist:** concrete checkboxes for the tests to add, the repo's quality gates (format, lint, build, full test suite, any architecture or static-analysis checks), manual checks, and metrics to confirm.
- **Done when:** one line naming the binary signal.

### Roadmap status
If the chosen phase in `specs/roadmap.md` has a `Status:` line, set it to `in progress`. That is the only change to `roadmap.md`. If the roadmap has no status fields, or `roadmap.md` already had uncommitted changes you didn't make, leave it alone and say so in the report.

## Step 5 - Codex review (adversarial review, in a subagent)

Use the codex plugin's **adversarial review**, because it accepts focus text and plain `review` doesn't. The `/codex:*` slash commands set `disable-model-invocation`, so the subagent runs the companion script they wrap, from the worktree root:

```bash
ls -d ~/.claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs 2>/dev/null | sort -V | tail -1   # -> <companion>
# Bash tool with run_in_background: true
CODEX_COMPANION_SESSION_ID=feature-spec-<slug>-<random> timeout -k 10 660 node "<companion>" adversarial-review --background --scope working-tree -- "<focus>"
CODEX_COMPANION_SESSION_ID=feature-spec-<slug>-<random> node "<companion>" status --json   # lists only this launch's job
node "<companion>" status <job-id> --wait --timeout-ms 240000 --json                       # repeat until finished
node "<companion>" result <job-id>
```

Shell variables don't persist between Bash calls, so substitute `<companion>` and the tag literally. Pass each flag as its own argument and `<focus>` as one argument after `--`, because the companion re-splits a combined string and can mangle it. Use the tag to find the job, not "the newest job", since other reviews may share the workspace. If the tagged status shows zero jobs or more than one, the launch failed.

`<focus>`:

> Review these planning documents: specs/<name>/requirements.md, specs/<name>/plan.md, specs/<name>/validation.md. Also read specs/roadmap.md, specs/mission.md, specs/tech-stack.md, and CLAUDE.md / AGENTS.md plus any convention or architecture docs they cite, if they exist; the specs must be consistent with them. Review for: internal contradictions between the three files; scope items in plan.md missing from requirements.md and vice versa; validation criteria that don't verify the stated requirements; ambiguous or untestable acceptance criteria; missing edge cases or risks; scope that strays outside this phase's roadmap entry or works against the mission's non-goals; and conflicts with the tech stack. Also check plan.md's task groups against the engineering standards: tests listed before the code they pin, the repo's dependency and layering boundaries, needless abstractions, and steps that would produce non-idiomatic or untestable code. For each finding, output a numbered item with the file, the issue, and the suggested change. Output findings only; do not rewrite the documents.

Rules for the subagent:
- **Capture** the result verbatim to `/tmp/codex-spec-review-<slug>.md`, so Step 6 can be audited, and return the findings. This file is never committed.
- **Deadline:** 10 minutes from launch. The job has stalled if its `pid` is dead while status still says running, or if its `logFile` has been silent for 5 minutes. Then `cancel <job-id>` and return `codex failed: <reason>`.
- **No companion:** run `timeout -k 10 600 codex exec --sandbox read-only -o /tmp/codex-spec-review-<slug>.md "<focus>" < /dev/null` instead. Without the `< /dev/null`, a background `codex exec` waits on stdin until the timeout kills it. A non-zero exit or an empty file means `codex failed`.

If codex fails, tell the user and `AskUserQuestion` with these options: **retry the codex review**, **substitute a self-review** (adversarial `general-purpose` subagents given the same focus text, whose findings go through Step 6), **skip the review and commit and push unreviewed specs**, or **skip the review and stop without committing**. Go on to Step 7 only if the chosen option allows it.

## Step 6 - Adjudicate the findings and update the specs

Codex's comments are hypotheses, not instructions. For each finding:
1. Re-read the cited passage and confirm the issue is real.
2. Check it against the settled decisions. A finding that only disputes a decision the user made is **rejected**. A finding showing that a decision rests on a wrong fact, or is unsafe, goes back to the user (below).
3. Check it against the mission and tech-stack constraints.
4. Give it a disposition:
   - **accept:** a real gap or contradiction; edit the file(s), and keep each edit traceable to its finding number.
   - **reject:** wrong, a deliberate scope cut, or contradicts a user decision; say why.
   - **defer:** valid but belongs to a later phase or needs a user decision; say where it goes.

If an accepted finding would change a settled decision (widen scope, swap a key choice), don't edit it on your own. Reopen that branch with the grilling skill until the user confirms, update the decision list, and then edit. Show the user the full disposition table.

## Step 7 - Commit and push

This runs without a confirmation prompt, because the worktree guarantees `HEAD` is the `specs/<name>` branch. Every failure below is a hard stop: report the exact error and end the run. Never force-push and never switch remotes.

1. **Preflight:** `git rev-parse --abbrev-ref HEAD` equals `<branch-name>`, `git remote get-url origin` succeeds, and `git diff --cached --name-only` is empty.
2. **Stage by explicit path, never by directory:**
   ```bash
   git add -- specs/<name>/requirements.md specs/<name>/plan.md specs/<name>/validation.md
   git add -- specs/roadmap.md   # only if Step 4 changed its status line
   ```
   Confirm `git diff --cached --name-only` lists exactly those paths. Leave anything else `git status` shows untouched, and mention it in the report.
3. **Commit** in the repo's convention: a subject style set in `CLAUDE.md` or the repo docs, else the style of recent `git log` subjects (e.g. a ticket-key prefix, used only when the name or roadmap carries a key; never invent one), else `docs(specs): add <name> feature spec`. Add any trailers the environment requires. The body lists the files and gives the codex outcome in one line.
4. **Push:** `git push -u origin <branch-name>`. A non-zero exit is a stop; leave the commit in place. Don't open a PR unless the user asks.

## Step 8 - Report

- The three spec paths, each with a one-sentence summary, and whether the roadmap status was updated.
- How the worktree was set up: new, or reused. For a reused one, the Step 2a outcome (already current, rebased onto `<base>` at `<sha>`, or rebase skipped and why).
- The codex outcome: the total, the accept / reject / defer counts, a one-line reason for each rejection (or which Step 5 option was taken and why).
- The commit hash and subject, the branch pushed, and the worktree path. If Step 7 stopped, which check failed and its exact error.
- The next step, `/implement-plan specs/<name>/plan.md`, and a reminder that the worktree stays until the user removes it (`git worktree remove <wt-path>`, then `git worktree prune`).

## Notes

- "Today" is the local system date.
- If `<name>` contains slashes (`specs/feat/auth`), the docs directory nests to match (`specs/feat/auth/`).
- If the user's own checkout is on a non-default branch, mention it; they may have meant to merge that work first.
- This skill never removes worktrees.
