# Incident & Postmortem Context

- **Jira**: look for tickets labeled `incident`, `sev-*`, `postmortem-action-item`, `reliability`, or of an incident issue type
- **Confluence**: postmortem pages created in the weeks before the target code was added
- **Slack**: search `#sev-*` and `#incident-*` channels around the dates the target code was added
- **Git**: commits with messages like "fix for incident", "add defensive check", "revert" followed by "re-apply with..." are strong signals
