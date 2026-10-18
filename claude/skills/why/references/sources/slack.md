# Slack Conversations

## How to search it

Slack tools vary. Check which Slack MCP or plugin is available and inspect its tool schema first. If it exposes only sign-in tools, or a call fails on authentication, stop and report the gap.

1. **Author-bounded search.** Messages from the PR author around the PR merge date. Limits scope dramatically and often hits gold.
2. **PR URL search.** Slack often links PRs when they're reviewed or discussed. Search for the PR URL (or just `/pull/<number>`).
3. **Ticket key search.** Search for the ticket keys from the anchor.
4. **Error string search.** If the code handles a specific error, search for the error string. Incident threads often surface.

Every call is a read. Posting, reacting and other write tools stay unused.

## Common pitfalls

- **Channel archaeology limits.** Very old messages may be gone due to retention policies. If you can't find anything before a certain date, note the retention cliff.
- **Unsearched DMs.** Many decisions happen in DMs that aren't searchable. You'll miss them. That's a known limitation.
- **Speculative jokes as "decisions."** Slack is casual. "Lol just do the thing" isn't a decision, even if it preceded the commit. Look for considered discussion.
- **Context collapse in single messages.** Without the thread, a single message often reads differently than in context. Always fetch threads.
- **Auth failures.** If the tool isn't authenticated, stop. Report that Slack wasn't searchable rather than inventing findings.
