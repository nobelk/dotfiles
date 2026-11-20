# Tickets instead of a `/spec` phase

Read this when the argument is a ticket reference rather than a `specs/<name>` phase. Everything in `SKILL.md` still applies: each ticket is a **task**, and its blocking links are its `Depends on`. Only the points below differ. Use one tracker for the whole run.

| Tracker | Spec and tasks | Blockers | Linked in the PR as | Marked done |
|---|---|---|---|---|
| **GitHub** | the spec issue and its sub-issues, or issues referencing it (`gh issue view`, `gh issue list`) | native sub-issue or blocking links, else each ticket's "Blocked by" section | `Closes #N` per issue | automatically, when the PR merges |
| **Jira** | the spec issue and its child issues or epic children (Atlassian tools: `getJiraIssue`, `searchJiraIssuesUsingJql`) | "is blocked by" issue links, else the ticket's "Blocked by" text | ticket keys (`PROJ-123`) in the PR body, plus the spec key in the title if the repo's convention uses keys | only with the user's OK, at wrap-up |
| **Local** (`/to-tickets`) | a spec file plus `.scratch/<feature>/issues/NN-*.md` | each file's `**Blocked by:**` line | the ticket file paths, listed in the PR body | set the file's `**Status:**` to `done` once its branch is merged |

Local ticket files usually sit untracked in the user's checkout, so a worktree cut from `<base>` doesn't contain them. Read them, and mark them done, by absolute path in that checkout, and give subagents the same absolute paths. They are the one thing this skill edits outside the worktree.

## What differs, by step

- **Step 1, the branch.** No `/spec` run created one. Resolve and refresh `<base>` first, then name the branch by the repo's convention (`CLAUDE.md`, recent branch names), including a ticket key or issue number if the convention uses one; with no convention, use `implement/<spec-slug>`. Create it in a worktree at the usual `<wt-path>` with `git worktree add <wt-path> --no-track -b <branch> <base>`, and enter that worktree. Nothing is pushed yet, so skip Step 1's sync with `origin/<branch>` and its `plan.md` precondition. If the branch already exists, this is a rerun: attach or reuse its worktree, and Step 1 applies as written.
- **Step 2, the standards.** There is no `plan.md`, so the standards are `specs/tech-stack.md` if the repo has one and the agent docs. Read every ticket, and build the graph from the tracker's blocking links.
- **Step 3, seams and decisions.** Tickets record no seams, so every ticket's seams are unsettled and all of them are confirmed here, before any implementer starts. If a decision contradicts a ticket's text, ask whether to update that issue before the PR links to it. If the tickets can't be built as written, stop: nothing has been pushed, so report the local branch and worktree for the user to remove, and leave `/spec` out of it.
- **Step 4, the PR.** A new branch has no commits beyond its base, and GitHub refuses a PR for it, so publish it first:
  ```bash
  git commit --allow-empty -m "<subject>"
  git push -u origin <branch>
  ```
  The PR body links the spec and the tickets the way the table says.
- **Step 5, after each merge:** mark a local ticket done in its file.
- **Step 8, the end-to-end survey** maps the tickets' acceptance criteria.
- **Step 9, `spec-review`:** the spec is the spec issue or file, with its tickets.
- **Step 11, closing out.** With no `validation.md` or roadmap phase, skip that commit; the tickets' acceptance criteria are the checklist, reported in the PR body.
- **Step 12, Jira.** `AskUserQuestion` whether to transition the delivered tickets (for example to "In Review"), naming the tickets and the target status. A transition is visible to the whole team, so it needs an explicit yes.
