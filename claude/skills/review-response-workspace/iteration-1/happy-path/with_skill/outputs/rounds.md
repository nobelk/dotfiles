# Rounds shown to the user

Each section is the exact text that would have been shown to the user at that point. The user was not present; every question was taken as answered "yes" (recommended answer accepted).

## Step 3 - Grilling, round 1 (status block and contested calls)

**Status**

- **PR**: https://github.example.invalid/acme/ratelimit/pull/7 - "RATE-12: sliding-window rate limiter", `feat/RATE-12-limiter` -> `main`, open, head `c545718`. Replies post as `dev-author`.
- **Ticket**: RATE-12 (from the branch name). Jira context unavailable: no Jira connection in this session, so nothing below rests on the ticket. The statement of intended behavior is the spec, `specs/rate-12-limiter/requirements.md` (R1-R6).
- **Mode**: Execute. The PR head is checked out here, `HEAD` is the PR head, the tree is clean, and there are no local commits ahead of it.
- **Items**: 5 to answer (4 unresolved threads, 1 review summary that asks for something), plus 1 resolved thread listed for completeness. Nothing to answer in rev-tom's empty review summary, my own "Ready for review" comment, or the CI bot comment.
- **Classification**: Agree 2, Agree with modification 1, Push back 1, Needs clarification 1.
- **Gates at the PR head**: `make test` passes (6 tests); `make lint` is a syntax check and the sources compile.

Settled by the evidence (not questions):

- `ratelimit/limiter.py:21` - rev-maria - Agree (S). R3 says a hit exactly `W` old no longer counts; `hits[0] < now - self._window` keeps it, and no test advances exactly `window_seconds`. Fix: `<=`, plus a boundary test.
- Review summary - rev-maria - Agree (S). The README has no mention of `burst`. Fix: a `burst` section in the README, and the class docstring, which says "at most `limit` hits" where the ceiling is `limit + burst`.
- `tests/test_limiter.py:32` - rev-tom - resolved thread (the `windw` typo). Already fixed at head; no action, no reply.

Three calls are yours:

Q1 - **Push back on rev-tom's "`limit` is never validated" (`ratelimit/limiter.py:11`)**: Tom asks me to raise on a non-positive limit because "zero or a negative value gives a limiter that silently rejects everything". The code already does: `__init__` calls `_check_arguments` on line 15, four lines below his hunk, and `ratelimit/limiter.py:34-35` raises `ValueError("limit must be positive, got ...")`. `test_rejects_non_positive_limit` (`tests/test_limiter.py:44-47`) covers 0 and -1 and passes, and R4 requires exactly this. A probe confirms `limit=0`, `limit=-1`, and `limit=0, burst=5` all raise, so no limiter that rejects everything can be built. He most likely missed it because line 11 assigns `limit + burst` before the check runs. The stance: say it is already covered, cite the line and the test, change no code, and offer to move the validation to the top of `__init__` if the ordering is what bothered him. The alternative is to make that move now, unasked (no behavior change, about three lines).

Recommended: Push back with the evidence, no code change, and make the offer in the reply. Yes?

---

Q2 - **Fix the `_hits` growth by expiry instead of rev-maria's LRU (`ratelimit/limiter.py:20`), in this PR**: Maria is right that `_hits` grows without bound: nothing ever removes a key (5,000 distinct keys are still tracked 1,000 s later on a 10 s window), and that is also an R5 violation ("holds no state for a key that has no hits in the current window"). Her remedy, an LRU with `maxsize=1024`, contradicts the spec twice: evicting a key that still has live hits lets its next call through, which is a count reset caused by other keys (R6) and more than `limit + burst` hits in a window (R1). A probe confirms it: `limit=1`, key "a" hit once, 1,024 other keys touched, "a" evicted, "a" allowed again in the same instant. A caller rotating keys could use that to get around the limit. An LRU would also still hold up to 1,024 expired keys, so R5 stays unmet.

The remedy I would plan instead: keep `_hits` ordered by each key's most recent accepted hit and drop keys from the old end once their newest hit has left the window, in both `allow()` and `tracked_keys()`. Amortized O(1) per call, state is exactly the keys with a hit in the current window (R5), and R1 and R6 hold. Tests: state is dropped after the window, and a key at its limit stays limited after 2,000 other keys are hit. Size M. No spec edit, since the code is being brought to what R1, R5 and R6 already say. What remains is memory proportional to the keys active inside one window; a hard cap on top of that needs a product answer (what happens to a new key when the table is full) and a change to R1/R6, so it goes to a follow-up ticket rather than this PR.

Recommended: Agree with modification - expiry-based eviction in this PR, explain to Maria why not the LRU, and offer the hard cap as a follow-up ticket. Yes?

---

Q3 - **Ask rev-tom what "Hmm, is this right?" refers to (`ratelimit/limiter.py:10`), and fix the one wrong thing in that hunk meanwhile**: The comment sits on the `__init__` signature and names no subject. I checked every candidate in the hunk: the `burst=0` default (right: R1, `test_allows_up_to_limit`), the `clock=time.monotonic` default (spec is silent; tests inject a fake clock per CLAUDE.md; nothing shows it wrong), the parameter names and order (match the spec's terms; every caller uses keywords), and the class docstring on line 8, which is wrong: it says "at most `limit` hits" while the ceiling is `limit + burst`. The plan: reply with the specific question (which of the `burst` default, the `clock` default, or the parameter order do you mean), say what I checked, and say I fixed the docstring, which is being corrected anyway under Maria's request to document `burst`. The thread stays open until he answers.

Recommended: Needs clarification - ask the specific question and mention the docstring fix; no other code change on a guess. Yes?

*(Taken as answered: Q1 yes, Q2 yes, Q3 yes.)*

## Step 3 - Grilling, round 2 (confirmation of shared understanding)

All three answers accepted, and no question hangs off them, so the frontier is empty. The settled decisions:

- **D1** - Thread 5002 (rev-tom, `limit` validation): push back. Cite `ratelimit/limiter.py:15` and `:34-35`, `test_rejects_non_positive_limit`, and R4. No code change. The reply offers to move the validation to the top of `__init__` if he wants it.
- **D2** - Thread 5003 (rev-maria, `_hits` growth): agree with modification. Expiry-based eviction of idle keys (ordered by most recent accepted hit, applied in `allow()` and `tracked_keys()`), not an LRU, because an LRU breaks R1 and R6 and still misses R5. Done in this PR. No spec edit.
- **D3** - A hard cap on tracked keys is out of scope for this PR: offered to Maria as a follow-up ticket. No ticket is created by this run.
- **D4** - Thread 5004 (rev-tom, "Hmm, is this right?"): needs clarification. Ask which of the `burst` default, the `clock` default, or the parameter order he means; no code change on a guess. The thread stays open.
- **D5** - The class docstring ("at most `limit` hits") is corrected to `limit + burst` as part of documenting `burst`, and mentioned in the 5004 reply and the summary reply.
- **D6** - Jira is unreachable, so the spec (`specs/rate-12-limiter/requirements.md`) stands as the statement of intended behavior and the plan says "Jira context unavailable" where ticket evidence would apply.
- **D7** - Execute mode: implement, run `make lint` and `make test`, commit on top of `c545718`, then come back to you once more before anything is pushed or posted.

Q1 - **Shared understanding**: Is that the plan as you understand it, and may I write `review_response_7.md`, have it reviewed, and implement it?

Recommended: Yes - proceed; the next time I stop is the publish round, before the push and the replies.

*(Taken as answered: yes.)*

## Step 5 - Grilling, reopened branch (D3, after the plan review)

The plan review found that one reason I gave you for D3 was wrong, so I am putting D3 back to you before changing the plan.

Q1 - **D3, hard cap as a follow-up: keep the decision, correct the reason**: In round 1 I said a hard cap on tracked keys "needs a product answer ... and a change to R1/R6". That is only true of a cap that evicts live keys. A cap that refuses new keys when the table is full leaves R1 and R6 intact and gives up R2 instead ("Keys are limited independently", `specs/rate-12-limiter/requirements.md:4`), because whether a new key is served would then depend on how many other keys are active. Maria could have rebutted the reply as I had drafted it. What still holds: any cap needs a product answer (which requirement to give up) and a spec edit in the same commit (`CLAUDE.md:6`), so it still does not belong in a PR whose job is to meet R1-R6 as written. The reply to Maria now says a cap needs a spec change either way, R1/R6 if it evicts live keys, R2 if it refuses new ones.

Recommended: Keep D3 (follow-up ticket, not this PR) with the corrected reason in the plan and in the reply. Yes?

*(Taken as answered: yes. D3 now reads: "A hard cap on tracked keys is out of scope for this PR: it needs a product answer and a spec change either way (R1/R6 if it evicts live keys, R2 if it refuses new ones). Offered to Maria as a follow-up ticket. No ticket is created by this run.")*

## Step 5 - Disposition table (shown, not a question)

The plan review ran as two native adversarial reviewers instead of codex (codex was treated as not installed in this environment). They returned 12 findings, 9 after merging duplicates. All 9 accepted; none rejected or deferred.

| # | Finding | Disposition | Evidence |
|---|---------|-------------|----------|
| F1 | 5003: "amortized O(1)" is false if `_hits` is a plain `dict` (finding the oldest key rescans deleted slots; one call stalled 5.4 s at 160k expired keys) | Accept | Both reviewers measured it; plan now names `OrderedDict` with `move_to_end`. |
| F2 | 5001: the planned boundary test (`limit=1`) stops exercising the per-hit comparison once idle keys are dropped first | Accept | A mutant with the old `<` on the hit comparison passed all planned tests; test changed to `limit=2` with hits at t and t+5. |
| F3 | 5003: planned tests do not pin the ordering step or the live-hit guard | Accept | Mutants (no re-insert; peek oldest hit) passed; two tests added. Eviction from `allow()` is not observable through the public API and is recorded as such. |
| F4 | 5002 reply cites `limiter.py:34-35`, `:15`, `:11` and test lines that shift once the fix lands | Accept | `allow()` and `tracked_keys()` grow above `_check_arguments`; replies now cite by name. |
| F5 | `<sha>` is ambiguous across the two commits (the summary reply needs both) | Accept | Placeholders are now `<sha-limiter>` and `<sha-readme>`. |
| F6 | 5003 reply overstates a lazy design ("state is exactly the keys with a hit in the window") | Accept | Eviction only runs inside `allow()` and `tracked_keys()`; reply reworded. |
| F7 | Checklist lacks commit subjects and the README content the summary reply promises | Accept | `CLAUDE.md:5`; step 4 and step 6 now list them. |
| F8 | WRONG FACT (D3, partial): a hard cap does not necessarily change R1/R6; a refuse-new-keys cap gives up R2 instead | Accept, D3 reopened and kept | See the reopened round above. |
| F9 | 5003: dropping a key on its newest hit alone fails open if an injected clock steps back, where head fails closed | Accept | Probe: `[T, T, T, T, F]` against head's `[T, T, F, F, F]`. Plan now prunes the oldest key's hits with the one expiry rule and drops the key only when none are left. |

## Step 7 - Publish round

Everything is committed locally and the gates are green on `HEAD` (`make lint` pass, `make test` pass with 11 tests; no formatter or build step is configured). Nothing has left this machine yet.

Q1 - **Publish**: Push, post the replies, update the PR description, and re-request review, as listed here?

**Push**: `git push origin HEAD:refs/heads/feat/RATE-12-limiter` (fast-forward from `c545718`; no force). Outgoing commits:

- `b1f85dd` fix(limiter): expire hits and idle keys at the window boundary (RATE-12)
- `47593b1` docs(readme): document the burst parameter (RATE-12)

**Replies** (posted as `dev-author`; full text in `/tmp/rr-eval/happy-path/repo/review_response_7.md`):

- `ratelimit/limiter.py:21` (rev-maria) - Agree - "You're right."
- `ratelimit/limiter.py:20` (rev-maria) - Agree with modification - "The growth is real, and it is also a spec violation: R5 says the limiter holds no state for a key with no hits in the current window, and nothing ever removed a key from `_hits`."
- `ratelimit/limiter.py:11` (rev-tom) - Push back - "I think this is already covered, though the layout makes it easy to miss."
- `ratelimit/limiter.py:10` (rev-tom) - Needs clarification - "Could you say which part you mean?"
- Conversation comment answering rev-maria's review summary - Agree - "@rev-maria, on your review: ... Done in 47593b1." (This mentions her by login, so it notifies her.)

The resolved typo thread (`tests/test_limiter.py:32`) gets no reply. No thread is resolved by this run.

**PR description**: the existing text stays as written (nothing in it became false). This block is appended:

> ## Changes in response to review
>
> **Window expiry now matches the spec (R3, R5)** - b1f85dd
> - A hit exactly `window_seconds` old no longer counts: expiry compares with `<=`, so the window is `(now - W, now]`.
> - The limiter no longer keeps state for idle keys. `_hits` is an `OrderedDict` ordered by each key's most recent accepted hit, and `allow()` and `tracked_keys()` drop keys whose last hit has left the window. A key with a live hit is never dropped, so R1 and R6 hold.
> - Five tests added: the exact-window boundary, state dropped after the window, an idle key dropped while a busier one stays, a key with a live hit keeping its count, and 2,000 other keys not resetting a limited key.
>
> **`burst` is documented** - 47593b1, b1f85dd
> - The README has a `burst` section with an example (47593b1).
> - The class docstring now states the ceiling as `limit + burst` (b1f85dd).
>
> **Not changed**
> - No LRU cap on tracked keys: evicting a key with live hits would break R1 and R6. A hard cap needs a spec change and is offered as a follow-up ticket in the review thread; none is open yet.
> - `limit` validation is unchanged: non-positive values already raise `ValueError` (R4).

**Re-request review**: rev-maria (she requested changes and both her threads get a reply). rev-tom only commented, so he is not re-requested; he is notified by the replies on his two threads.

**Held by the dry run**: nothing. All four threads are unchanged since the snapshot.

You may strike any part (for example: push and reply, but leave the description alone).

Recommended: Yes - publish all of it.

*(Taken as answered: yes.)*
