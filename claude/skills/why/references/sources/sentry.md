# Sentry Error History

## How to search it

Use the Sentry MCP if this session has one. Otherwise use the `sentry` CLI (the `sentry-cli` skill covers it) with read-only `--json` commands. If neither is installed, or the CLI exits with an auth error (codes 10 to 19), stop and report the gap.

1. **Orient.** Find the organization and project (MCP `find_organizations` / `find_projects`; the CLI auto-detects them from the repo's DSN config).

2. **Search for issues related to the target.** MCP `search_issues`, or `sentry issue list --query '<terms>' --json`. Build queries from the exception or error strings the target handles, its function or type name, and its file path.

3. **Narrow by release and time window.** MCP `search_issue_events` / `get_issue_tag_values`, or `sentry issue view <id> --json`. For a suspected issue, check **first seen** and **last seen** (does the stop line up with the target's ship date?), the **affected releases** (which saw it, and which was the fix?), and the **frequency trajectory** (did it spike, then get resolved?).

4. **Pull the full event for context.** MCP `get_sentry_resource`, or the CLI's event view. Does the stack trace pass through the target code? Do the tags and breadcrumbs match the conditions the target defends against?

5. **Check releases that landed near the target.** MCP `find_releases`, or the CLI's release list, around the commit date. Cross-reference the release version with the PR's merge date.

6. **Treat AI root-cause output as inference.** Seer analyses (`analyze_issue_with_seer`, `sentry issue explain`) generate hypotheses, not evidence. The actual events and stack traces are the primary evidence.

Every call is a read. Resolve, archive, merge, assign and delete stay unused.

## What to return

For each relevant issue:
- Issue ID and title
- Project and organization
- First seen / last seen timestamps
- Event count (and sampling rate if known)
- Affected releases
- A representative stack trace snippet showing relevance to the target (verbatim excerpt, not summary)
- First/last-seen correlation with the target's ship date
- Link to the issue
- Any author comments or resolution notes
