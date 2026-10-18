# Jira Tickets

## What this source contains

- Issues describing features, bugs, and their motivation
- Epics and parent issues (broader initiative, then the specific tickets under it)
- Comments on issues (clarifications, scope changes, "why we're doing this" rationale)
- Issue links (blocks, relates to, duplicates) and remote links (PRs, Confluence pages)
- Labels and components that signal the type of motivation
- Status history and fix versions that explain scope changes and timing

Jira is where the product/business context often lives: the "we're doing this because customer X asked" or "this is for the safety review" layer.

## How to search it

Use the Atlassian MCP Jira tools with the `cloudId` the main agent passed you. Ask for `responseContentFormat: "markdown"` to keep bodies readable.

1. **Start with linked tickets.** Fetch every ticket key from the anchor with `getJiraIssue`, including comments. Read the full issue, not the summary.
2. **Follow the links.** `getJiraIssueRemoteIssueLinks` for linked PRs and docs; the issue's own links for related and duplicate tickets.
3. **Walk the issue tree.** If you land on a child issue, fetch its parent or epic. Children are tactical. Parents often carry the "why."
4. **Search by keyword with JQL.** `searchJiraIssuesUsingJql` with `text ~ "<feature or symbol>"`, scoped by `project = <KEY>` and a `created` window around the ship date. Include `comment` in `fields` when the hits look relevant. Try several phrasings.
5. **Check labels, components and fix versions.** They hint at the category of motivation (customer request, incident follow-up, compliance, safety) and tie work to deadlines.

Every call is a read. Comment, transition, link, label, worklog and edit tools stay unused.

## What good evidence looks like here

- An issue description stating the business or safety problem in specific terms
- A comment recording a decision: "We decided to go with approach B because approach A would require touching the billing service"
- An epic titled like an initiative
- An attached or linked spec or design page
- Labels like `incident-followup`, `compliance`, `perf-regression`

## Common pitfalls

- **Scope drift.** The ticket may have been closed and reopened with a different scope. Read the whole history.
- **Mechanical templates.** Some teams require "Why" sections but fill them with boilerplate. Generic text ("improve user experience") is probably not a real answer.
- **Stale tickets.** Old tickets often reflect a version of the plan that changed. Check dates and cross-reference with the code's ship date.
- **Closed-as-duplicate chains.** Follow the duplicate links back to the canonical ticket.
- **Restricted content.** If you can't access an issue, note that as a gap rather than guessing.

## What to return

For each relevant ticket:
- Ticket key and title
- The problem/motivation quoted from the description or comments (verbatim, since the synthesizer needs the exact text to cite)
- Labels, components, parent or epic
- Reporter, created date, resolved date
- Link to the ticket
