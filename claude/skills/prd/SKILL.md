---
name: prd
description: "Writes a product requirements document (PRD) to prod_req.md with every requirement in EARS syntax (Easy Approach to Requirements Syntax: WHERE / WHILE / WHEN / IF ... THEN, the <system> SHALL ...). Reads the brief and the repo, grills the user on the problem, users, goals, scope, behaviour, and quality targets, then writes the PRD in Atlassian's agile shape - measurable goals, scope and what we're not doing, user stories, and EARS functional and non-functional requirements traced to them - plus assumptions, open questions, and a glossary. Validates the EARS with a checker, has codex review the document, and folds the valid findings back in. Leaves the file uncommitted as the input for /design-doc. Use whenever the user asks for a PRD, product requirements, a requirements document, EARS or \"shall\" requirements, or wants to pin down what to build before designing it - including revising an existing prod_req.md. For one /constitution roadmap phase, use /spec instead."
argument-hint: "[product or feature, a brief path / URL / Jira key, or a PRD to revise] [output path]"
---

# PRD skill

Write the product requirements document for a product or a feature: one Markdown file, `prod_req.md`, that says what to build, for whom, why, and how we will know it worked. It never says how to build it. Every requirement is one EARS sentence, so it states exactly when it applies and what the product does, and it can be tested on its own.

| Stage | Reads | Writes |
|---|---|---|
| `/prd` | the brief, the repo, the user | `prod_req.md` |
| `/design-doc prod_req.md` | this file and the code | `docs/design/<slug>.md` |
| `/jira-planner <design doc>` | the design document | `jira_plan.md` and Jira tickets |

`/design-doc` takes its scope, quality drivers, users, assumptions, and glossary from this file, and grills the user only on what this file leaves open. So a number missing here becomes a guess in the architecture, and a requirement that says *how* takes a decision away from the design.

The flow: read the sources → grill the user → write → check → codex review → adjudicate → report. The file is left **uncommitted** for the user to read and commit.

The main loop owns everything that talks to the user or rests on their decisions: the grilling, the writing, and the final call on each review finding. Subagents take the bulky, self-contained work: surveying the code, the codex run, and the adjudication of a long list of findings. Give each one a self-contained prompt with absolute paths, the exact commands, and the result shape you want back.

## Step 1 - Read the sources

Finding facts is your job; only decisions go to the user. Work from the repository root (`git rev-parse --show-toplevel`, or the current directory outside git).

**The subject and the mode** come from the argument:

- A sentence naming a product or feature, or a brief given as a path, a URL, or a Jira key: **create mode**. Read a Jira issue or a Confluence page with the Atlassian tools, and a web page with whatever fetch tool the session has.
- A path to an existing PRD, or no subject while `prod_req.md` exists: **revise mode**. That document is the starting point, not something to replace, unless the user asks to start over.
- No argument and no `prod_req.md`: ask the user for a two-or-three-sentence pitch (what, for whom, why now) and treat it as the brief.

**The output path** is the one the argument gives, else `prod_req.md` at the repository root. If that file already exists and covers a different product or feature, ask whether to replace it, extend it, or write to another path.

Then, in one message:

- Read the brief, `README.md`, and `specs/mission.md` and `specs/roadmap.md` if they exist. They often settle the problem, the users, the goals, and the non-goals already.
- Read `CLAUDE.md` / `AGENTS.md` and any existing PRDs, design documents, or decision records. The PRD uses their vocabulary and doesn't contradict them without saying so.
- Read `assets/template.md` and `references/ears.md` in this skill's directory. The template's subsections are the questions the grilling has to settle; `ears.md` governs how every requirement is written, and its unwanted-behaviour sweep is one branch of the grilling.
- If the repository has code, launch an `Explore` subagent (medium thoroughness) to report, with file citations:
  - what the product already does for its users (features, commands, routes, screens), so the PRD marks what is new and doesn't require what exists;
  - the user roles and permissions the code knows about;
  - the external systems it calls or is called by;
  - the limits already set in code or config: timeouts, rate limits, quotas, size limits, retention periods;
  - the names the code and the user interface use for the product and its main entities, which become the system name and the glossary.

An empty repository is a valid answer: everything in the PRD is then new.

Where two sources disagree (the brief promises one thing and the code does another), that is a decision. Raise it in the grilling session instead of resolving it silently.

## Step 2 - Grill the user (`grilling` skill)

Invoke **`mattpocock-skills:grilling`** with the Skill tool and run its session to completion. It is the skill `/grill-me` loads; the Skill tool can invoke it only under this name.

Seed the design tree from the sources and the survey, so every question and recommended answer is specific to this product. The branches depend on one another in this order:

1. **Problem and strategic fit:** who has the problem, how it shows up, what it costs them, what they do today instead, the evidence, why now, and which company or project goal it serves.
2. **Users:** the primary and secondary users, the tasks they come to do, and how often.
3. **Goals and success metrics:** each goal is an outcome with a metric, a baseline, and a target with a unit and a date ("a dispatcher assigns a work order in under 2 minutes by the end of Q2", not "faster dispatch").
4. **Scope:** what is in, what we're not doing (and whether it may come later), the target release, and the MVP line, which sets the Must / Should / Could priorities.
5. **System name:** the one name every requirement uses as its subject. Recommend the name the users and the code already use. Add a second only if users get separate products (a mobile app and an admin portal), not for internal parts.
6. **User stories:** one per user task in scope, each tied to the goals it serves.
7. **Behaviour:** for each story, its EARS requirements: the normal responses, the states that change them, the variants, and the unwanted-behaviour sweep from `references/ears.md`. Put a story's requirements to the user as one question whose recommended answer is the drafted EARS sentences, so a "yes" settles the wording along with the substance.
8. **Quality targets:** the non-functional categories in `references/ears.md` that apply, each with a number and a unit and the conditions it is measured under. Press for numbers: these are the drivers `/design-doc` chooses the architecture from.
9. **Assumptions, constraints, and dependencies:** each assumption is a risk the user is accepting, so confirm the list.
10. **Open questions:** what the user chooses to leave open, each with an owner, a date, and the requirements it blocks. Leaving a question open is a legitimate answer; one that blocks a Must requirement is a risk the report names.

Ask only questions whose answer changes the document. In revise mode, grill on what changed and what it touches; a decision the document already records stays settled unless the change or the code puts it in doubt.

**Done when** the frontier is empty and the user confirms you share an understanding. Then list the **settled decisions** in the conversation as `D1`, `D2`, .... Step 3 writes from this list, and Step 6 checks every codex finding against it. Write no part of the document until then.

## Step 3 - Write the document

In create mode, start from `assets/template.md`: fill every subsection and delete the angle-bracket guidance. In revise mode, edit the existing document: keep the wording the change doesn't touch, and bring its structure up to the template's where it differs.

The eleven level-2 headings are the document's whole top level. Keep their wording and order exactly, and add no others, because `/design-doc`, the codex review, and the checker all rely on them. Anything else is a subsection of one of the eleven. A subsection that doesn't apply keeps its heading and one line saying why.

| Section | What the reader learns | What `/design-doc` takes from it |
|---|---|---|
| 1. Background and strategic fit | Why this exists and why now | The purpose in its introduction |
| 2. Goals and success metrics | The outcomes that mean success, as numbers | Its goals table |
| 3. Users | Who uses it, for what, how often | Its users and tasks; the people in the context diagram |
| 4. Scope | What is in, and what we're not doing | Its scope |
| 5. User stories | Each user need, tied to a goal | The key interactions it draws |
| 6. Functional requirements | What the product does, in EARS | Its interfaces and components |
| 7. Non-functional requirements | The quality targets, in EARS | The quality attributes that choose its architecture pattern |
| 8. User interaction and design | The flows users go through; links to mockups | Its user interface design |
| 9. Assumptions, constraints, and dependencies | What is taken for granted, imposed, or relied on | Its assumptions, constraints, and dependencies |
| 10. Open questions | What is still undecided, and what it blocks | Its risks and open questions |
| 11. Glossary | What every term means here | Its glossary |

**IDs.** Goals are `G1`, `G2`, ...; user stories `US1`; functional requirements `FR1`; non-functional requirements `NFR1`; assumptions `A1`; open questions `Q1`. The design document and every later ticket cite these, so an ID never changes meaning. In revise mode keep every existing ID, give new items the next free number, and retire a removed item's number rather than reuse it.

**Traceability.** Every story names the goals it serves, every functional requirement the stories (or goals) it implements, and every non-functional requirement the goals or stories it protects. A goal that nothing traces to will not be delivered, and a requirement that traces to nothing is scope nobody asked for.

**Requirements.** Write every row of sections 6 and 7 in one of the EARS patterns, following `references/ears.md`. Group the functional requirements by capability, one subsection and table per capability. Priority is Must, Should, or Could; a Won't item goes in 4.2 instead. Verification is Test, Demonstration, Inspection, or Analysis: how a reviewer will check the requirement, which is where acceptance criteria and test plans start.

### Writing style

The document is accurate, clear, and concise, in that order of difficulty:

- **Accurate.** Write only what the user decided or the sources say. A number has a unit and a source. Where the product already exists, check every statement about current behaviour against the code. Where something is unknown, record it as an assumption or an open question instead of writing around it. A confident guess is the most expensive sentence in a PRD, because the design and the tests both get built on it.
- **Clear.** One name for each thing, used everywhere: the glossary's term is the word in every requirement. One idea to a sentence. Tables for facts that compare, lists for parallel items, prose for the reasoning in sections 1 and 8.
- **Concise.** Just enough to build a shared understanding. Link interviews, mockups, tickets, and data rather than restating them. Leave out the history of how a decision was reached, and adjectives that carry no information.

### Glossary

Every acronym, domain term, product name, and the system name has a row in section 11: the expanded form, then one sentence on what it means for this product. Spell an acronym out at first use in the body as well. Keep the table alphabetical, and delete terms the document no longer uses.

## Step 4 - Check the document

Run the checker:

```bash
python3 <skill-dir>/scripts/check_prd.py <document>
```

It prints one line per check (sections, header, placeholders, ids, ears, fields, trace, wording, glossary) with the details beneath, and ends with `result: PASS` or `result: FAIL`. The `ears` line counts the requirements by pattern.

- **FAIL** lines are defects: a section missing or misordered, template guidance left behind, a duplicate or malformed ID, a requirement that breaks EARS (keywords out of order or not in capitals, a second SHALL, a subject other than the system name), a priority or verification method outside the allowed values, or a trace to an ID that doesn't exist. Fix them and run it again until none remain.
- **WARN** lines are heuristics that need judgment. A vague word or a requirement with no number is usually a real gap, so take it back to the user when you can't settle it from the decisions. "No IF ... THEN requirement" almost always means the unwanted-behaviour sweep was skipped. A goal or story that nothing traces to is either missing its requirements or out of scope.

Then check what the script can't see:

- Each requirement's keyword matches its meaning: WHEN for an instant, WHILE for a lasting state, IF ... THEN for the unwanted, WHERE for a variant (`references/ears.md`, "Choosing the pattern").
- Every event-driven requirement has been through the unwanted-behaviour sweep: its IF ... THEN companions exist, or a decision or an assumption says why the case can't arise.
- Each requirement states what, not how (`references/ears.md`, rule 7).
- No two requirements contradict or duplicate each other, and none delivers something in 4.2.
- Every settled decision appears in the document, and nothing in it contradicts one.

## Step 5 - Codex review (in a subagent)

Get an independent second-model review. Launch a `general-purpose` subagent and point it at `references/codex-review.md` in this skill's directory, which holds its instructions. Give it:

- `<dir>`: the repository root, or the document's directory outside git.
- `<tag>`: `prd-<random>`.
- `<scratch>`: `/tmp/codex-prd-<slug>.md`, where `<slug>` is the product or feature name in kebab case.
- `<focus>`:

> Review the product requirements document at <absolute document path>. The review context may list this file as skipped because of its size; open it at that path and read it in full before reviewing. Also read README.md, CLAUDE.md / AGENTS.md, anything under specs/, and the source code wherever the document describes existing behaviour. Review only this document; ignore other working-tree changes. Its requirements are written in EARS (Easy Approach to Requirements Syntax): "WHERE <feature>, WHILE <state>, WHEN <trigger>, IF <unwanted condition>, THEN the <system name> SHALL <response>", every clause before the system name optional, one response per requirement. Look for: requirements that break that syntax; a keyword that misstates the behaviour (WHEN for a lasting state, WHILE for an instant event, WHEN for an error or failure that should be IF ... THEN); missing unwanted behaviour for an event-driven requirement (invalid input, a missing permission, a duplicate request, a dependency failing, a limit reached, a conflicting change, an interruption, missing data); requirements that are not testable (no number or unit, vague words, an unverifiable negative); requirements that say how rather than what (components, storage, frameworks, algorithms, screen layouts) and are not listed as constraints; requirements that contradict or duplicate each other, or deliver something listed under "What we're not doing"; goals without a measurable metric, baseline, and target, and goals that no requirement serves; user stories that no requirement implements, and requirements that trace to nothing; priorities that conflict with the stated MVP or target release; non-functional targets missing the conditions they are measured under (load, percentile, period); statements about existing behaviour that contradict the code; assumptions the requirements depend on but do not state; open questions that block a Must requirement; and terms used but not in the glossary, or used with two meanings. For each finding, output a numbered item with the section and requirement ID, the issue, and the suggested change. Output findings only; do not rewrite the document.

Codex's helper leaves an uncommitted file over 24 KB out of the context it hands the model, which is why the focus text tells it to open the file. If the findings come back without citing a single section or ID of the document, codex didn't read it: treat that as `codex failed`.

If it returns `codex failed`, tell the user and `AskUserQuestion`: **retry the codex review**, **substitute a self-review** (one or two adversarial `general-purpose` subagents given the same focus text, whose findings go through Step 6 the same way), or **skip the review**. The report names the option taken.

## Step 6 - Adjudicate the findings and finalize

Codex's findings are hypotheses, not instructions. With more than about 8, split them into batches of 3-5 (contradictory findings share a batch) and launch one subagent per batch in a single message, each with the settled-decision list and `references/ears.md`; the final call on each finding stays here. For each finding:

1. Re-read the cited passage and confirm the problem is real. Discard findings about text that isn't there.
2. Check factual claims against the code and the sources rather than taking codex's word or your own memory.
3. Give it a disposition:
   - **accept**: a real error, gap, or contradiction. Edit the document, keeping each edit traceable to its finding number.
   - **reject**: wrong, already handled, a design question that belongs to `/design-doc`, or only preferring a different choice than one the user made. Say why.
   - **defer**: valid, but it needs a user decision that can wait. Record it as a question in section 10.

A finding you would otherwise accept that changes a settled decision (a new requirement, a dropped one, a moved MVP line, a different target), or one showing that a decision rests on a wrong fact or is unsafe, is the user's call. Reopen that branch with the grilling skill, update the decision list, and then edit. Adding a missing IF ... THEN case whose answer the decisions already imply is an ordinary accept; one whose response nobody has decided goes to the user.

An edit to one requirement often leaves a trace, a story, or the glossary stale. After the edits, run Step 4 again in full.

Then finalize: set the header's Status to `Reviewed` and its Date to today. If the review was skipped, leave the Status at `Draft`.

## Step 7 - Report

Leave the document uncommitted. Report:

- The path, the product or feature it covers, and its size: goals, stories, functional and non-functional requirements (with the checker's pattern breakdown), and how many are Must. In revise mode, what changed, and which IDs were added or retired.
- The checker's result, and any warnings left standing, with the reason.
- The codex outcome: total findings and the accept / reject / defer breakdown, with a one-line reason for each rejection (or which Step 5 option was taken and why).
- The open questions in section 10, and the Must requirements each one blocks.
- Next step: `/design-doc <path>`. Pass the path, because `/design-doc` doesn't look for `prod_req.md` on its own.
