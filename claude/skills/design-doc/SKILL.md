---
name: design-doc
description: "Writes a software design document in Markdown, structured by the C4 model with Mermaid figures. Reads the requirements and the codebase, grills the user on the open decisions, chooses and justifies the architecture pattern (layered, client-server, event-driven, microkernel, microservices, and so on), then writes docs/design/<slug>.md in eight fixed sections: introduction and overview, system architecture, data design, interface design, component design, user interface design, assumptions and dependencies, and glossary of terms. Checks that every diagram renders, has codex review the document, and folds the valid findings back in. Leaves the file uncommitted. Use whenever the user asks for a design doc, software design description, architecture document, system design write-up, or C4 context / container / component diagrams for a project or a feature - including revising an existing design doc after the design changed."
argument-hint: "[what to design, a requirements-doc path, or a design doc to revise] [output path]"
---

# Design-doc skill

Write the design document for a system or a feature: one Markdown file, structured by the C4 model, illustrated with Mermaid figures, in eight fixed sections. A reader who was not in the room should be able to build from it, review it, or plan work against it.

The flow: read the sources → grill the user on the decisions, choosing the architecture pattern on the way → write → check → codex review → adjudicate → report. The file is left **uncommitted** for the user to read and commit.

The main loop owns everything that talks to the user or rests on their decisions: the grilling, the choice of pattern, the writing, and the final call on each review finding. Subagents take the bulky, self-contained work: surveying the code, the codex run, and the adjudication of a long list of findings. Give each one a self-contained prompt with absolute paths, the exact commands, and the result shape you want back.

## Step 1 - Read the sources

Finding facts is your job; only decisions go to the user. Work from the repository root (`git rev-parse --show-toplevel`, or the current directory outside git).

**The subject and the mode** come from the argument:

- A sentence naming a system or feature, or a path to a requirements document: **create mode**. With no argument, the subject is the repository itself, as its README describes it.
- A path to an existing design document, or a subject whose document already exists at the output path: **revise mode**. That document is the starting point, not something to replace, unless the user asks to start over.

**The output path** is the one the argument gives. Otherwise follow the repo's existing home for design documents if it has one, and default to `docs/design/<slug>.md`, where `<slug>` is the subject's name in kebab case.

**The scope of a feature document** is the feature, shown in its setting: the context and container diagrams show the whole system with the new and changed elements marked, and the data, interface, and component sections cover only what the feature adds or changes.

Then, in one message:

- Read the requirement sources: the document or ticket the argument names, `README.md`, and `specs/mission.md`, `specs/tech-stack.md`, and `specs/roadmap.md` if they exist. They already settle many of the goals, the stack, and the constraints.
- Read `CLAUDE.md` / `AGENTS.md`, the architecture docs they cite, and any existing design documents or decision records. The new document uses their vocabulary and doesn't contradict them without saying so.
- Read `assets/template.md` in this skill's directory. Its subsections are the questions the grilling has to settle.
- Launch an `Explore` subagent (medium thoroughness) to survey the code, with file citations:
  - what runs: each process, service, data store, and queue, with its technology and pinned version (these become the containers);
  - inside each: the main packages or modules and which way their dependencies point (the components);
  - the data: schemas, migrations, and which unit owns which store;
  - the interfaces: HTTP routes, RPC definitions, message topics, commands, and every external service called;
  - the user interface: screens or routes, if there is one;
  - how it is deployed: Dockerfiles, compose files, infrastructure code, pipelines;
  - which architecture pattern the code actually follows, with the evidence.

An empty repository is a valid answer: the whole design is then a proposal.

Where two sources disagree (the README says one thing, the code another), that is a decision. Raise it in the grilling session instead of resolving it silently.

## Step 2 - Grill the user and choose the pattern (`grilling` skill)

Invoke **`mattpocock-skills:grilling`** with the Skill tool and run its session to completion. It is the skill `/grill-me` loads; the Skill tool can invoke it only under this name.

Seed the design tree from the sources and the survey, so every question and recommended answer is specific to this system. The branches depend on one another in this order:

1. **Subject and scope:** what is being designed, who will read the document, and what is deliberately out of scope.
2. **Drivers:** the goals and quality attributes that shape the architecture - scalability, performance, availability, security, budget, and technology constraints. Ask for a number with a unit wherever one exists ("200 ms at the 95th percentile", not "fast"), because the pattern is chosen from these.
3. **Architecture pattern:** read `references/architecture-patterns.md` and choose. This choice is yours to make, not a blank question for the user: put it to them as a recommendation with the drivers that decided it and the alternatives you rejected, so they can accept it with a yes or overrule it with a reason.
4. **Structure:** the people and external systems, the containers and their technologies, and where each one runs.
5. **Data:** the entities, which container owns each, the stores, and the consistency and retention each needs.
6. **Interfaces:** each contract that crosses the system boundary or runs between containers - protocol, format, authentication, and what happens on failure.
7. **Components:** which containers need a component view, their components' responsibilities, and any behaviour that is a state machine.
8. **User interface:** the users, their tasks, and the screens or commands they work through.
9. **Assumptions and dependencies:** what the design takes for granted, and what it needs from outside. Each assumption is a risk the user is accepting, so confirm the list.

For a system that already exists, most of branches 4 to 8 are facts the survey found: grill only on what is proposed, and on what the code leaves ambiguous. In revise mode, grill on what changed and what it touches; a decision the document already records stays settled unless the change or the code puts it in doubt. Ask only questions whose answer changes the document.

**Done when** the frontier is empty and the user confirms you share an understanding. Then list the **settled decisions** in the conversation as `D1`, `D2`, .... Step 3 writes from this list, and Step 6 checks every codex finding against it. Write no part of the document until then.

## Step 3 - Write the document

In create mode, start from `assets/template.md`: fill every subsection and delete the angle-bracket guidance. In revise mode, edit the existing document: keep the wording the change doesn't touch, and bring its structure up to the template's where it differs.

The eight level-2 headings are the document's whole top level. Keep their wording and order exactly, and add no others, because readers and the checker both rely on them. Anything else is a subsection of one of the eight. A subsection that doesn't apply keeps its heading and one line saying why.

| Section | What the reader learns |
|---|---|
| 1. Introduction and overview | What this is, what it covers, the goals that drove it, how to read the diagrams |
| 2. System architecture | The pattern and why; the system in its environment; its containers; where they run |
| 3. Data design | What data exists, who owns it, where it lives, how it stays correct |
| 4. Interface design | Every contract across the boundary and between containers; the flows that matter |
| 5. Component design | The inside of each container that has one; behaviour the structure doesn't show |
| 6. User interface design | Who uses it, for what, through which screens or commands |
| 7. Assumptions and dependencies | What the design takes for granted and relies on; what could still change it |
| 8. Glossary of terms | What every term in the document means here |

Section 6 always applies, because every system has users. One without a graphical interface describes the surface its users do work through - commands, configuration files, API clients - under the same three subsections.

### Diagrams

Read `references/c4-mermaid.md` before drawing the first one. It says which diagram each section needs, sets the notation every diagram shares, and gives a template for each diagram type that is known to render. Figures are numbered in order through the document, so after adding or removing one, renumber the captions that follow and the places that cite them.

### Writing style

The document is clear, concise, and accurate, in that order of difficulty:

- **Accurate.** Write only what is true of the design. Say what exists today and what is proposed, and check every statement about existing code against the code. A number has a unit and a source. Where something is unknown, put it under Assumptions or Open questions instead of writing around it; a confident guess is the most expensive sentence in a design document.
- **Clear.** One name for each thing, used everywhere: the name in a diagram is the name in the table, the prose, and the glossary. Use the active voice with the actor as the subject ("The API application validates the token"), and the present tense for the design. One idea to a sentence. Tables for facts that compare, lists for items that are parallel, prose for reasoning.
- **Concise.** State each fact once and refer to it by section number afterwards. Leave out what the diagram already shows, the history of how the design was reached, and adjectives that carry no information ("robust", "seamless", "scalable" without a number).

### Glossary

Use only the jargon the design needs, and define all of it. Every acronym, domain term, product or technology name, and C4 term in the document has a row in section 8: the expanded form, then one sentence on what it means in this system. "Container" is the entry that matters most, because readers assume it means a Docker container. Spell out an acronym at first use in the body as well. Keep the table alphabetical, and delete terms the document no longer uses.

## Step 4 - Check the document

Run the checker, with a Bash timeout of 600000 ms. The first run on a machine downloads mermaid-cli and a headless browser (about 700 MB), which can take several minutes.

```bash
python3 <skill-dir>/scripts/check_design_doc.py <document>
```

It prints one line per check (sections, figures, diagrams, glossary) with the details beneath, and ends with `result: PASS`, `result: FAIL`, or `result: UNVERIFIED DIAGRAMS`.

- **FAIL** lines are defects in the document: a section missing, misordered, or added; a diagram without a caption, misnumbered, or never cited; a diagram that doesn't render, with the Mermaid error and its line. Fix them and run it again until none remain.
- **WARN** lines are heuristics that need judgment. A listed acronym is often a real gap in the glossary and sometimes a state name or a constant. A glossary term never used is usually left over from an edit.
- **UNVERIFIED DIAGRAMS** means the other checks passed but nothing on this machine could render the diagrams; the line says why. Tell the user and `AskUserQuestion`: **fix the cause and check again**, or **continue with the diagrams unverified**. The report says which.

Then check what the script can't see:

- Every element in a diagram has a row in the table beneath it, and every row appears in the diagram.
- Every arrow crossing the system boundary has a row in section 4.1, and every arrow between containers has one in section 4.2.
- Every entity in the data model is owned by exactly one container.
- The pattern named in section 2.1 is visible in the container and component diagrams: the dependencies point the way the pattern says they do.
- Every settled decision appears in the document, and nothing in it contradicts one.

## Step 5 - Codex review (in a subagent)

Get an independent second-model review. Launch a `general-purpose` subagent and point it at `references/codex-review.md` in this skill's directory, which holds its instructions. Give it:

- `<dir>`: the repository root, or the document's directory outside git.
- `<tag>`: `design-doc-<random>`.
- `<scratch>`: `/tmp/codex-design-doc-<slug>.md`.
- `<focus>`:

> Review the software design document at <absolute document path>. The review context may list this file as skipped because of its size; open it at that path and read it in full before reviewing. Also read README.md, CLAUDE.md / AGENTS.md, anything under specs/, and the source code wherever the document describes existing behaviour. Review only this document; ignore other working-tree changes. Look for: statements that contradict the requirements or the code; contradictions between sections; elements or relationships that appear in a diagram but not in its table or in the interface section, and the reverse; misuse of the C4 model (a diagram that mixes levels, an element without a type or technology, an unlabelled relationship, a container that is really a component); an architecture pattern that the stated drivers do not justify, or that the diagrams do not actually follow; entities with no owning container, and wrong keys or cardinalities; interfaces missing a protocol, a format, authentication, or failure behaviour; components with an unclear responsibility or a circular dependency; user tasks the interface design does not cover; assumptions the design depends on but does not state, and dependencies without a version or an owner; terms used but not in the glossary, or used with two meanings; vague, unverifiable, or promotional wording; and Mermaid syntax that would not render. For each finding, output a numbered item with the section, the issue, and the suggested change. Output findings only; do not rewrite the document.

Codex's helper leaves an uncommitted file over 24 KB out of the context it hands the model, which is why the focus text tells it to open the file. If the findings come back without citing a single section of the document, codex didn't read it: treat that as `codex failed`.

If it returns `codex failed`, tell the user and `AskUserQuestion`: **retry the codex review**, **substitute a self-review** (one or two adversarial `general-purpose` subagents given the same focus text, whose findings go through Step 6 the same way), or **skip the review**. The report names the option taken.

## Step 6 - Adjudicate the findings and finalize

Codex's findings are hypotheses, not instructions. With more than about 8, split them into batches of 3-5 (contradictory findings share a batch) and launch one subagent per batch in a single message, each with the settled-decision list; the final call on each finding stays here. For each finding:

1. Re-read the cited passage and confirm the problem is real. Discard findings about text that isn't there.
2. Check factual claims against the code and the sources rather than taking codex's word or your own memory.
3. Give it a disposition:
   - **accept** - a real error, gap, or contradiction. Edit the document, keeping each edit traceable to its finding number.
   - **reject** - wrong, already handled, or only preferring a different choice than one the user made. Say why.
   - **defer** - valid but beyond this document (it belongs in a spec or a ticket), or it needs a user decision that can wait. Record it in section 7.4.

A finding you would otherwise accept that changes a settled decision (a different pattern, another container, a changed contract), or one showing that a decision rests on a wrong fact or is unsafe, is the user's call. Reopen that branch with the grilling skill, update the decision list, and then edit.

An edit to one section often leaves a diagram, a table, or the glossary stale. After the edits, run Step 4 again in full.

## Step 7 - Report

Leave the document uncommitted. Report:

- The path, the system or feature it covers, and its size (sections filled, figure count). In revise mode, what changed.
- The architecture pattern chosen, the drivers that decided it, and whether the user accepted or changed your recommendation.
- The checker's result, including any diagrams left unverified and why.
- The codex outcome: total findings and the accept / reject / defer breakdown, with a one-line reason for each rejection (or which Step 5 option was taken and why).
- The open questions and risks recorded in section 7.4.
- Next steps the document now supports: `/constitution` if the repo has no `specs/` yet, or `/jira-planner <path>` to break the design into tickets.
