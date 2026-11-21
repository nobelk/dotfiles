# Writing requirements in EARS

EARS (Easy Approach to Requirements Syntax) is a small set of sentence templates for requirements, developed by Alistair Mavin and colleagues at Rolls-Royce while they analysed airworthiness regulations for a jet-engine control system (Mavin, Wilkinson, Harwood, Novak, RE'09, 2009). Each template puts the conditions, the system, and the response in fixed places. A reader can then see exactly when a requirement applies, and a tester can see exactly what to check. EARS targets the three classic defects of natural-language requirements (ambiguity, vagueness, and omission) while staying plain English that any stakeholder can read.

## The shape of a requirement

```
WHERE <feature>, WHILE <state>, WHEN <trigger>, IF <unwanted condition>, THEN the <system name> SHALL <response>.
```

The clauses always come in this order, and every one before the system name is optional:

| Part | How many | Keyword |
|---|---|---|
| Feature precondition | 0 or 1 | WHERE |
| State precondition | 0 or 1 (join several states with "and") | WHILE |
| Trigger | 0 or 1 | WHEN, or IF ... THEN for an unwanted one |
| System name | exactly 1 | - |
| Response | exactly 1 | SHALL (or SHALL NOT) |

EARS itself allows several responses in one sentence. This skill allows one, so that each row passes or fails on its own and a ticket can cite it alone.

## The patterns

| Pattern | Template | Example |
|---|---|---|
| Ubiquitous | The <system name> SHALL <response>. | The mobile phone SHALL have a mass of less than 150 grams. |
| Event-driven | WHEN <trigger>, the <system name> SHALL <response>. | WHEN 'mute' is selected, the laptop SHALL suppress all audio output. |
| State-driven | WHILE <state>, the <system name> SHALL <response>. | WHILE there is no card in the ATM, the ATM SHALL display 'insert card to begin'. |
| Unwanted behaviour | IF <unwanted condition>, THEN the <system name> SHALL <response>. | IF an invalid credit card number is entered, THEN the website SHALL display 'please re-enter credit card details'. |
| Optional feature | WHERE <feature is included>, the <system name> SHALL <response>. | WHERE the car has a sunroof, the car SHALL have a sunroof control panel on the driver door. |
| Complex | Two or more of the keywords, in clause order. | WHILE the aircraft is on ground, WHEN reverse thrust is commanded, the engine control system SHALL enable reverse thrust. |

The examples are the canonical ones from the EARS literature, as given on Wikipedia.

## Choosing the pattern

The keyword is a claim about the behaviour, so a wrong keyword is a wrong requirement, not a style slip.

- **WHEN or WHILE?** WHEN is for something that happens at an instant (a user submits, a timer expires, a message arrives): the response happens once per event. WHILE is for a condition that lasts (offline, signed in, in maintenance mode): the response holds for as long as the condition does. A clause that reads naturally after "as long as" is a WHILE.
- **WHEN or IF ... THEN?** IF ... THEN is for the unwanted: things the product has to cope with but nobody wants, such as invalid input, a declined payment, a timeout, a dependency that is down, a permission denied, or a limit exceeded. A normal path the user chose is a WHEN, even when it is the less common one ("WHEN the customer selects 'pay later'").
- **WHERE or WHILE?** WHERE is fixed for a given installation, customer, or build: an edition, a plan tier, a configured feature, a hardware option. WHILE changes at runtime.
- **Ubiquitous** is for what is always true. If you find yourself adding "always", check that it really has no condition.
- **Complex** is for behaviour that needs a state and a trigger, or a variant and a failure. More than three conditions in one sentence stops being readable: put them in a decision table or a state table beneath the requirements table, give that table no ID column, and have the requirement cite it ("... SHALL apply the fee in Table 6.2.").

## Writing rules

The checker enforces rules 1 to 4; the review enforces the rest.

1. **Keywords in capitals:** WHERE, WHILE, WHEN, IF, THEN, SHALL, SHALL NOT. Everything else is in normal sentence case. A comma closes every clause, including the one before THEN.
2. **The subject is the declared system name**, spelled exactly as in the header, in every requirement ("the Dispatch app", never "the system", "the app", or "Dispatch"). The product can only be held to its own behaviour, so a requirement whose subject would be another system is really a dependency (9.3) or an assumption (9.1).
3. **One SHALL per requirement.** If a sentence needs a second response, write a second row with its own ID.
4. **Each keyword at most once.** Join several states or conditions inside one clause with "and".
5. **A testable response.** The response is something a tester can observe at the product's boundary, stated precisely: numbers with units ("within 2 s", "at most 3 attempts", "for 30 days"), the exact text of a message in quotes, named states, named fields. Vague words stand in for a number or a behaviour that nobody decided: fast, easy, intuitive, user-friendly, robust, seamless, efficient, flexible, scalable, appropriate, sufficient, as needed, if possible, etc., and/or, minimize, maximize, optimize, real-time. "SHALL support", "SHALL handle", and "SHALL manage" hide the behaviour the same way. Replace each one with what was meant, and ask the user if nobody knows.
6. **SHALL is the only modal verb.** Priority lives in the Priority column, so a Should requirement still reads SHALL. "should", "may", "will", and "must" inside a requirement leave it unclear whether it is a requirement at all.
7. **What, not how.** State the behaviour a user or a neighbouring system can observe, and stop at the product's boundary. Components, services, databases, frameworks, algorithms, and screen layouts are design decisions: /design-doc makes them, informed by these requirements. A mechanism imposed from outside (a mandated vendor, a regulation, a platform the company already runs) is a constraint: record it in 9.2 Constraints rather than as a requirement.
8. **Positive where possible.** "SHALL NOT" is for a prohibition that is itself the point, usually about privacy, safety, or security ("... SHALL NOT store the full card number."). It still has to be checkable, typically by Inspection or Test.

## The unwanted-behaviour sweep

Omission is the defect EARS most often catches, and it hides in the failure cases. For every event-driven requirement, walk this list with the user. Each case that can happen becomes an IF ... THEN requirement; each case that can't happen becomes a recorded decision or an assumption (9.1). None is left unspoken.

- The input is invalid, incomplete, or out of range.
- The actor is not signed in, or is not allowed to do this.
- The same request arrives twice (double submit, retry, replay).
- A dependency is slow, down, or returns something wrong.
- A limit is reached: a quota, a size, a rate, a balance.
- Someone else changed the same thing at the same time.
- The action is interrupted partway: the connection drops, the app closes, the device restarts.
- The data the response needs is missing or out of date.

## Non-functional requirements

Quality targets are requirements too, and they are written in EARS: usually ubiquitous or state-driven, sometimes event-driven. Each one names what is measured, a threshold with its unit, and the conditions it is measured under (the load, the percentile, the period, the environment). These are the drivers /design-doc chooses the architecture from, so a target without a number becomes a guess there.

Categories (use only those that apply): Performance, Capacity, Availability, Reliability, Security, Privacy, Compliance, Accessibility, Usability, Compatibility, Operability, Data retention.

| Category | Example |
|---|---|
| Performance | WHILE up to 500 dispatchers are signed in, the Dispatch app SHALL return search results within 1 s at the 95th percentile. |
| Availability | The Dispatch app SHALL be available for 99.5% of each calendar month, excluding announced maintenance windows. |
| Privacy | The Dispatch app SHALL NOT display a customer's full phone number to a technician. |
| Accessibility | The Dispatch app SHALL meet WCAG 2.2 level AA. |
| Data retention | WHEN a work order has been closed for 7 years, the Dispatch app SHALL delete its customer contact details within 30 days. |

A quality that is not behaviour ("written in Go", "runs on the company's Kubernetes cluster") is a constraint, not a requirement: record it in 9.2 Constraints.

## Rewrites

| Before | What is wrong | After |
|---|---|---|
| The system should be fast. | No system name, a non-EARS modal verb, a vague word, no condition to measure under. | WHEN a dispatcher submits a search, the Dispatch app SHALL return the first page of results within 1 s at the 95th percentile. |
| When the user logs in, the system shall show the dashboard and send a welcome email. | Keywords not in capitals, a generic subject, two responses. | Two rows: WHEN a dispatcher signs in, the Dispatch app SHALL display the Today view. / WHEN a dispatcher signs in for the first time, the Dispatch app SHALL send a welcome email to the dispatcher's address within 5 minutes. |
| WHEN an order is open, the Shop app SHALL let the customer cancel it. | An open order is a state, not an event. | WHILE an order is open, the Shop app SHALL accept a cancellation from the customer who placed it. |
| If the payment fails, the Shop app shall retry. | Keywords not in capitals, no THEN, a vague response (how often, then what?). | IF a card payment is declined, THEN the Shop app SHALL display 'Your card was declined. Try another card.' |
| The Shop app SHALL display the confirmation WHEN the payment succeeds. | The condition comes after SHALL. | WHEN a payment succeeds, the Shop app SHALL display the order confirmation. |
| The Dispatch app SHALL store work orders in PostgreSQL. | How, not what. | A requirement for the behaviour, such as "The Dispatch app SHALL keep each saved work order retrievable for 7 years.", plus a constraint in 9.2 if PostgreSQL is mandated. |
