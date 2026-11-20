# Choosing the architecture pattern

The catalog is the ten patterns from the GeeksforGeeks article "Types of Software Architecture Patterns" (https://www.geeksforgeeks.org/software-engineering/types-of-software-architecture-patterns). Weigh these first. A pattern from outside the catalog is allowed when it fits better; the last section says how.

## How to choose

1. **Write down the drivers.** The article's six questions are the ones that separate the patterns. Answer each from the sources, and take what they leave open to the user as a number, not an adjective:
   - **Scalability:** the load now, the load expected, and which part of the system it lands on.
   - **Performance:** latency and throughput targets, and which operations they apply to.
   - **Availability:** how much downtime is tolerable, and what has to keep working when a part fails.
   - **Security:** what has to be protected, from whom, and any compliance rule that applies.
   - **Budget:** the size of the team, the time available, and the running cost that is acceptable.
   - **Technology:** the stack that is already in use, required, or ruled out.

   Two more often decide between close candidates: whether parts of the system must be released independently of each other, and where change is expected (new features, new integrations, new data volumes).
2. **Shortlist** the two or three patterns whose "choose when" matches the drivers.
3. **Pick the simplest one that meets every driver.** Each step up in distribution is paid for in operations, debugging, and consistency work, so a named driver has to justify it. A team of three with one deployable does not need microservices because the domain is large.
4. **Say which level each pattern applies to.** One pattern can describe how the containers relate (C4 level 2) and another how a container is organised inside (C4 level 3). "Client-server between the tablet and the site server; layered inside the API application" is a normal answer. Combining patterns is fine when each one is tied to its level.
5. **Record the choice** in section 2.1 of the document: the pattern at each level, the drivers that decided it, the closest alternatives with the reason each lost, and the cost the pattern brings with what the design does about it.

For a system that already exists, first describe the pattern the code actually follows, with evidence from the code. Changing the pattern of a running system is a proposal for the user to accept, not a finding.

## The catalog

| Pattern | Structure | Choose when | Cost it brings | How it shows in the C4 diagrams |
|---|---|---|---|---|
| **Layered** (n-tier) | Code is grouped into layers, each with one job (the article names presentation, business, application, and data); a layer depends only on layers beneath it | A conventional business application, one team, where separation of concerns matters more than raw performance | Every request crosses every layer; layers can become pass-throughs; strict layering adds effort | Level 3: components grouped by layer, every dependency pointing downward |
| **Client-server** | Clients request resources from a central server that owns the data and the rules | Many clients share centrally managed data and security: web and mobile apps, email, file sharing | The server is a single point of failure, and it is costly to set up and maintain | Level 2: client containers calling one server container that owns the data store |
| **Event-driven** | Producers publish events; consumers react to them asynchronously | Real-time reaction, bursty load, or consumers that must be added without touching producers: IoT, fraud detection, analytics | Hard to trace and test; delivery, ordering, and failure handling need explicit design | Level 2: producer and consumer containers joined through topics or queues, each drawn as a data-store container or named on the arrow; relationships are labelled "publishes" and "subscribes" |
| **Microkernel** (plug-in) | A small core holds the essential behaviour; plug-ins add features through a defined contract | A product that is extended or customised per customer or device: IDEs, embedded platforms | The core-to-plug-in contract is hard to get right and expensive to change | Level 3: a core component and a registry, with plug-in components that depend on the core and never on each other |
| **Microservices** | Small services, each owning its data, developed and deployed independently | Several teams that must release independently, or parts with very different scaling needs | Operational load, network failure modes, distributed data consistency, a larger attack surface | Level 2: several service containers, each with its own data store, behind a gateway |
| **Space-based** | Processing units share an in-memory data grid, with no central database on the request path | Very high and unpredictable concurrent load where the database is the bottleneck | Costly infrastructure; data consistency and recovery are complex | Level 2: identical processing-unit containers, a data-grid container, and an asynchronous writer to the durable store |
| **Primary-secondary** (the article calls it master-slave) | One coordinator hands work to several workers and collects the results | Parallel work on divisible tasks, or replication: database replicas, sensor networks, backups | The coordinator is a single point of failure; coordination overhead grows with the worker count | Level 2: a coordinator container and worker containers, with relationships labelled "assigns" and "reports" |
| **Pipe-filter** | Data flows through a chain of independent processing steps | Data transformation with clear stages: ETL, compilers, stream and signal processing | Every step must agree on the data format; long chains are slow and hard to debug | Level 3: filter components in a line, each arrow labelled with the data format it carries |
| **Broker** | An intermediary routes requests between clients and servers that do not know each other | Integrating separate systems, or servers that come and go: enterprise integration, message queues | The broker is a single point of failure and has to be secured and scaled itself | Level 2: a broker container between the callers and the providers; no arrow bypasses it |
| **Peer-to-peer** | Every node is both client and server; there is no central authority | Decentralised sharing or resilience without central infrastructure: file sharing, blockchains | Security policy and data consistency are hard to enforce across peers | Level 2: identical node containers connected to each other, with no central container |

## Outside the catalog

When a well-known pattern that the article leaves out fits the drivers better, choose it, say plainly in section 2.1 that it is outside the catalog, and name the catalog pattern it was preferred over and why. The usual candidates:

- **Hexagonal** (ports and adapters): the domain sits at the centre, and everything external reaches it through an interface the domain defines. Preferred over layered when the domain has to be tested without its infrastructure, or when adapters are expected to be swapped.
- **Modular monolith:** one deployable with enforced module boundaries. Preferred over microservices when the team is small and independent deployment is not a driver.
- **CQRS** (command query responsibility segregation): separate models for writing and for reading. Used inside another pattern, when read and write loads or shapes differ sharply.
- **Serverless:** functions triggered by events on a managed platform. Preferred over event-driven on owned infrastructure when load is spiky and operating servers is not wanted.

Use the name the wider community uses, define it in the glossary, and apply the same record as in step 5.
