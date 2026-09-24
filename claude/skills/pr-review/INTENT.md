# Intent check (pr-review Step 4, subagent procedure)

Check that one review target's change matches what it claims to be: its **Jira ticket**, its **PR title and description**, and its **spec**, when a spec exists. Inputs come from the dispatching prompt: `<owner>/<repo>`, PR number, title, body, `headRefName`, `commits`, range `<base>...<head>` (full SHAs), the clone path, and, for a C delta, my existing feedback bodies. Work read-only. Read code with `git -C <clone> show <head>:<path>` and the change with `git -C <clone> diff <base>...<head>`.

The step is done when every source below has either been compared against the diff or has a recorded reason it couldn't be.

## 1. Jira ticket

- **Find the key.** Look for keys matching `[A-Z][A-Z0-9]+-\d+` in the head branch name, the title, the body, and the commit messages, in that order. The first key found in the branch name, or else the first found anywhere, is **primary**. Fetch every distinct key.
- **Fetch it.** Load the Atlassian tools with `ToolSearch` (`select:mcp__claude_ai_Atlassian__getAccessibleAtlassianResources,mcp__claude_ai_Atlassian__getJiraIssue`). Resolve the `cloudId`, then fetch each ticket. Capture the summary, description, acceptance criteria (whether a field or a section of the description), issue type, and status.
- **If the fetch fails** (tools not connected, auth, not found), record `jira: unavailable (<error>)` and compare against the remaining sources. Use only ticket content you actually fetched.
- **If there is no key**, check whether the repo links tickets: `gh pr list --repo github.com/<owner>/<repo> --state merged --limit 20 --json title,headRefName`. When any of those carry a key, the missing link is a finding; otherwise record `jira: not used in this repo`.

## 2. Spec

A spec is present when any of these exist at `<head>`:
- `specs/<name>/`, where `<name>` matches the head branch with its prefix (`feature/`, `specs/`, `fix/`, ...) removed, or the ticket key;
- in-repo spec or design files the PR body links to (a `github.com/<owner>/<repo>/blob/...` URL or a relative path; read them at `<head>`), or that the PR adds or changes under `specs/` or `docs/`;
- a Confluence page the PR body or the ticket links to, fetched with `mcp__claude_ai_Atlassian__getConfluencePage`.

Read the plan, requirements, and validation files when present. Record any other link (Google Docs, Notion, and so on) as `spec: linked but not fetched (<url>)` in the result, not as absent. If no spec exists, record `spec: none` and move on.

## 3. Compare

Judge the diff against each source, and report only concrete mismatches you can quote:

- **Ticket**:
  - an acceptance criterion the change leaves out or only partly implements;
  - behaviour that contradicts the ticket;
  - substantial change the ticket doesn't cover (scope creep);
  - a primary ticket that plainly describes different work (wrong ticket linked).
- **Title**: the title misdescribes the change, for example "fix" on a feature, or naming a component the diff doesn't touch.
- **Description**: a claim the diff doesn't bear out, such as "adds tests" with no tests, a migration mentioned with none included, or listed behaviour that isn't implemented. Also a description too empty to review against, but only when the repo's recent merged PRs carry real descriptions.
- **Spec**: a requirement that is missing, partial, or implemented differently from what the spec states.

For a C delta, judge only what the delta changes, and drop anything already raised in my existing feedback.

## Result

```
{jira: {keys, primary, status: "fetched" | "unavailable" | "none-in-repo" | "missing"}, spec: {paths} | "none",
 findings: [{source: "jira" | "title" | "description" | "spec", quote, summary, path?, line?}]}
```

`quote` is the ticket, spec, or PR text the finding contradicts. Include `path:line` only when a specific head line is where the mismatch shows; title, description, and missing-ticket findings usually have none.
