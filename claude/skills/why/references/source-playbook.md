# Source playbooks

The why skill spawns one investigator per available evidence category, each reading a single playbook below. The playbooks are concrete examples for common tools. Adapt them for a different tool in the same category, and inspect an unfamiliar tool's schema before the first call.

| Category | Playbook | Claude Code tools it usually maps to |
|---|---|---|
| Source control history | [`code-archaeology.md`](./sources/code-archaeology.md) | git, `gh` (always available) |
| Issue / ticket tracker | [`jira.md`](./sources/jira.md) | Atlassian MCP Jira tools; adapt for GitHub Issues (`gh issue`), Linear |
| Long-form documents | [`confluence.md`](./sources/confluence.md) | Atlassian MCP Confluence tools; adapt for Notion, Google Drive |
| Real-time team chat | [`slack.md`](./sources/slack.md) | Slack MCP or plugin |
| Infrastructure observability | [`datadog.md`](./sources/datadog.md) | Datadog MCP or plugin; adapt for Grafana, New Relic, Honeycomb |
| Error / exception tracking | [`sentry.md`](./sources/sentry.md) | Sentry MCP, or the `sentry` CLI (see the `sentry-cli` skill) |
| Product analytics warehouse | none | BigQuery, Hex, Amplitude, Databricks, Snowflake |

The analytics warehouse has no playbook. Its investigator probes the schema first (`SHOW TABLES`, `DESCRIBE`, or the tool's catalog call), time-bounds every query to a window around the ship date, returns compact numeric summaries rather than rows, and names a retention cliff as a gap rather than a null result.

Cross-cutting:

- [`incident-postmortem.md`](./sources/incident-postmortem.md). Add this if the target code looks defensive (null checks, retry, timeout, rate limit, feature flag, egress guard, OOM handler).
