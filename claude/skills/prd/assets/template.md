# <Product or feature name>: product requirements

| | |
|---|---|
| **Status** | Draft |
| **Date** | <YYYY-MM-DD> |
| **Target release** | <version, milestone, or date> |
| **Participants** | <product owner, team, and stakeholders, by name or role> |
| **System name** | <the name every requirement uses as its subject, e.g. Dispatch app; if users get more than one product, one name each, separated by semicolons> |
| **Sources** | <the brief, tickets, interviews, README, and code this document was written from> |

## 1. Background and strategic fit

### 1.1 Problem

<Who has the problem, how it shows up, what it costs them, and what they do today instead. Cite the evidence: interviews, tickets, support data, metrics.>

### 1.2 Strategic fit

<Why this, and why now: the company, product, or project goal this work serves.>

## 2. Goals and success metrics

<The outcomes that will tell us the product worked. A target is a number with a unit and a date.>

| ID | Goal | Metric | Baseline | Target |
|---|---|---|---|---|
| G1 | <an outcome for a user or for the business> | <what is measured, and how> | <today's value, or "unknown: measured from <date>"> | <value with unit, by date> |

## 3. Users

| User | Who they are | What they come to do | How often |
|---|---|---|---|
| <Dispatcher> | <role, context, relevant skills or constraints> | <their tasks this product serves> | <daily, weekly, ...> |

## 4. Scope

### 4.1 In scope

- <A capability. When the product already exists, mark it (new) or (changed).>

### 4.2 What we're not doing

- <What a reader might expect and won't get> - <why; say "later" if it may come back>

## 5. User stories

| ID | User story | Priority | Goals |
|---|---|---|---|
| US1 | As a <user>, I want <capability>, so that <benefit>. | Must | G1 |

## 6. Functional requirements

Each requirement is one EARS sentence. WHERE, WHILE, WHEN, and IF ... THEN say when it applies; SHALL introduces what the system does. Priority is Must, Should, or Could; Verification is how a reviewer checks it: Test, Demonstration, Inspection, or Analysis.

### 6.1 <Capability>

| ID | Requirement | Priority | Traces to | Verification |
|---|---|---|---|---|
| FR1 | WHEN <trigger>, the <system name> SHALL <response>. | Must | US1 | Test |
| FR2 | IF <unwanted condition>, THEN the <system name> SHALL <response>. | Must | US1 | Test |

## 7. Non-functional requirements

<The quality targets, also in EARS: what is measured, the threshold with its unit, and the conditions it is measured under. Only the categories that apply.>

| ID | Category | Requirement | Priority | Traces to | Verification |
|---|---|---|---|---|---|
| NFR1 | <Performance> | WHILE <load condition>, the <system name> SHALL <response, within N ms at the 95th percentile>. | Must | G1 | Test |

## 8. User interaction and design

<The main flows users go through, step by step in words, and links to any wireframes, mockups, or prototypes. Screen layout and visual design belong to the design document; say so here if there are no mockups yet.>

## 9. Assumptions, constraints, and dependencies

### 9.1 Assumptions

| ID | Assumption | If it is wrong |
|---|---|---|
| A1 | <about users, the business, or technology> | <what breaks, and which requirements change> |

### 9.2 Constraints

- <A limit imposed from outside: regulation, a mandated platform or vendor, budget, deadline. Name its source.>

### 9.3 Dependencies

| Dependency | What the product needs from it | Owner |
|---|---|---|
| <an external system, team, or vendor> | <the data, service, or decision> | <team or person> |

## 10. Open questions

<Things we still need to decide or research.>

| ID | Question | Blocks | Owner | Needed by |
|---|---|---|---|---|
| Q1 | <...> | <the IDs it blocks, e.g. FR3, NFR2; or -> | <person or team> | <date or milestone> |

## 11. Glossary

<Alphabetical. Every acronym, domain term, product name, and the system name.>

| Term | Definition |
|---|---|
| EARS | Easy Approach to Requirements Syntax. The sentence templates every requirement in sections 6 and 7 follows. |
