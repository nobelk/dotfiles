# <System or feature name>: design document

| | |
|---|---|
| **Status** | Draft |
| **Date** | <YYYY-MM-DD> |
| **Scope** | <the system, or the feature and the system it belongs to> |
| **Sources** | <the requirements, README, tickets, and code this document was written from> |

## 1. Introduction and overview

### 1.1 Purpose

<What this document describes and what a reader can do once they have read it. Two or three sentences.>

### 1.2 Scope

**In scope**

- <...>

**Out of scope**

- <What a reader might expect here and won't find, with the reason.>

### 1.3 Goals and quality attributes

<The drivers that shaped the architecture. A target is a number with a unit wherever one exists.>

| Goal or quality attribute | Target | Source |
|---|---|---|
| <Availability> | <99.5% during site operating hours> | <PRD section 3, or decision D4> |

### 1.4 Overview

<One paragraph: what the system does, for whom, and the architecture pattern in a sentence. A reader who stops here should have the right picture.>

### 1.5 How to read the diagrams

<Two sentences on the C4 model and its levels as this document uses them, then the notation key as Figure 1. If the document covers a change to an existing system, say here how new and changed elements are marked.>

## 2. System architecture

### 2.1 Architecture pattern

<The pattern chosen and the C4 level it applies to; a second pattern for the inside of a container if there is one. Then why: which drivers from 1.3 decided it. Then the cost the pattern brings and what this design does about it.>

| Pattern considered | Fit against the drivers | Decision |
|---|---|---|
| <Chosen pattern> | <...> | Chosen |
| <Closest alternative> | <...> | Rejected: <one reason> |

### 2.2 System context

<One sentence citing the figure and saying what to notice. Then the C4 level 1 diagram and its caption.>

| Person or system | Type | Relationship to the system |
|---|---|---|

### 2.3 Containers

<Cite the figure. Then the C4 level 2 diagram and its caption. When the document covers a change to an existing system, add a Status column: existing, new, or changed.>

| Container | Technology | Responsibility | Data it owns |
|---|---|---|---|

### 2.4 Deployment

<Where each container runs, and in which environments. A diagram when there is more than one node; otherwise a sentence.>

### 2.5 Cross-cutting decisions

<Only the concerns this system has: security, observability, error handling, configuration, concurrency.>

| Concern | Decision | Reason |
|---|---|---|

## 3. Data design

### 3.1 Data model

<Cite the figure. Then the entity-relationship diagram and its caption.>

| Entity | Purpose | Key attributes | Owning container |
|---|---|---|---|

### 3.2 Storage

| Store | Technology | Holds | Retention | Consistency and backup |
|---|---|---|---|---|

### 3.3 Data flow and integrity

<How data enters, changes, and leaves the system: validation at the boundary, transactions, consistency between stores, schema migration, and handling of personal or sensitive data.>

## 4. Interface design

### 4.1 External interfaces

<One row for each relationship that crosses the system boundary in the context diagram.>

| Interface | Consumer → provider | Protocol and format | Authentication and authorization | Errors and limits |
|---|---|---|---|---|

### 4.2 Internal interfaces

<One row for each relationship between containers in the container diagram.>

| Interface | Consumer → provider | Protocol and format | Contract | Errors and limits |
|---|---|---|---|---|

### 4.3 Key interactions

<A sequence diagram for each flow that shaped the design: the main success path, and each failure path that drove a decision. Cite each figure and say what it shows that the tables can't.>

## 5. Component design

### 5.1 <Container name>

<Cite the figure. Then the C4 level 3 diagram and its caption. Repeat this subsection for each container with internal structure worth showing, and say in one line which containers have none. Add a Status column as in 2.3 when the document covers a change.>

| Component | Responsibility | Depends on | Notes |
|---|---|---|---|

<Behaviour that the structure doesn't show: a state diagram for a stateful component, the algorithm that carries the risk, error handling, concurrency. A code-level diagram only where a component's internal structure is itself the design problem.>

## 6. User interface design

<Every system has users. If this one has no graphical interface, say so in one line and describe the surface its users do work through (commands, configuration files, API clients) under the same three headings.>

### 6.1 Users and tasks

| User | Task | Frequency | What they need to see or do |
|---|---|---|---|

### 6.2 Screens and navigation

<Cite the figure. Then a flowchart of the screens, or command steps, and the moves between them, and a line on each one's purpose and content. With nothing to move between (a single command, a configuration file), list the surface in a table and draw no figure.>

### 6.3 Interaction states

<What the interface shows while loading, when empty, and on each error; how input is validated; accessibility requirements.>

## 7. Assumptions and dependencies

### 7.1 Assumptions

| # | Assumption | If it is wrong |
|---|---|---|
| A1 | <...> | <what breaks, and what would have to change> |

### 7.2 Dependencies

| Dependency | Version | Used for | Owner | Risk |
|---|---|---|---|---|

### 7.3 Constraints

- <Technical, organisational, or regulatory limits the design had to work within.>

### 7.4 Risks and open questions

| # | Risk or open question | Impact | Owner or next step |
|---|---|---|---|

## 8. Glossary of terms

<Alphabetical. Every acronym, domain term, product name, and C4 term this document uses.>

| Term | Definition |
|---|---|
| <API> | <Application programming interface. In this document, the HTTP interface the API application exposes to the web client.> |
