# Confluence Pages

## What this source contains

- PRDs (product requirement documents)
- Technical specs and RFCs
- Design records kept outside the repo
- Meeting notes from design reviews
- Team pages with domain context
- Postmortems from incidents
- Runbooks that may explain defensive code
- Strategy documents that set priorities

Confluence is where "why" often lives in long-form before it becomes code. A significant feature usually has a page.

## How to search it

Use the Atlassian MCP Confluence tools with the `cloudId` the main agent passed you.

1. **Keyword searches with `searchConfluenceUsingCql`.** Try `text ~ "<term>" AND type = page` for:
   - The feature name
   - Key symbols / type names from the target code
   - Ticket keys from the anchor (pages often name the ticket they support)
   - Error strings or operator-visible terms
   - A `created` or `lastmodified` window if you know when the code shipped
2. **Fetch candidate pages with `getConfluencePage`.** Read the full content, not the excerpt. Rationale is often buried mid-document.
3. **Follow child pages and comments.** `getConfluencePageDescendants` for alternatives-considered and appendix pages; `getConfluencePageFooterComments` and `getConfluencePageInlineComments` for review discussion.
4. **Search by contributor.** If the PR author wrote design pages, `contributor = "<accountId>"` around the ship date may surface exploratory thinking that preceded the code.

Every call is a read. Comment and page-edit tools stay unused.

## What good evidence looks like here

- A PRD with a "Problem statement" or "Motivation" section that matches the target code's purpose
- An "Alternatives considered" or "Rejected approaches" section
- A postmortem that names the target code as the fix for a specific incident
- Meeting notes that record "we decided X because Y" and tie to the same author/date range as the PR
- A decision record filled out non-trivially (status, context, decision, consequences)

## Common pitfalls

- **Outdated pages.** Specs are often written before implementation and not updated. The page may describe a plan that changed. Cross-check against the actual PR.
- **Page vs. reality drift.** A spec may say "we'll do X" but the code actually does Y. Flag the divergence. The synthesizer will surface the contradiction.
- **Boilerplate templates.** Some orgs require a "Why" section that gets filled with fluff. Look for specificity.
- **Unlinked pages.** The most relevant page may not be linked from anywhere. Broad keyword searches help.
- **Multiple drafts.** If a topic has multiple pages, find the one that was finalized or most recently updated. Check dates.
- **Restricted pages.** If you can't access a page, note it as a gap.

## What to return

For each relevant page:
- Title and URL
- Authors and last-updated date
- The motivation text (verbatim quote), with section location
- Relevant linked pages (so the synthesizer can cite them)
- Whether the page was finalized or draft
