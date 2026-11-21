# Step 3 - Grilling session: opening status and round 1

**Review response for PR #7** - https://github.example.invalid/acme/ratelimit/pull/7

- **PR:** "RATE-12: sliding-window rate limiter", `feat/RATE-12-limiter` -> `main`, head `9fa93f4`, open. You are the author; replies post as `dev-author`.
- **Ticket:** `RATE-12` (from the branch name). Jira context unavailable: no Atlassian server is connected in this session, so `specs/rate-12-limiter/requirements.md` (R1-R6) is the statement of intent I used.
- **Mode:** execute. The PR head is checked out here, `HEAD` is the PR head, tracked files are clean. Nothing is pushed or posted before the publish round.
- **Items:** 5 to answer (4 unresolved threads, 1 review summary that asks for something). 1 resolved thread (`tests/test_limiter.py:32`, the `windw` typo) is listed in the plan with no action: the test is named `test_hits_expire_after_window` at head. Tom's empty review summary, your own "Ready for review" comment, and the CI bot comment ask for nothing.
- **Classification:** Agree 2 - Agree with modification 1 - Push back 1 - Needs clarification 1.

Settled by the evidence (not questions):

- `ratelimit/limiter.py:21` (rev-maria, window boundary) - **Agree, S.** `hits[0] < now - self._window` keeps a hit that is exactly `window_seconds` old; R3 says it no longer counts. Fix is `<=` plus a boundary test. The existing expiry test advances 11s on a 10s window, so it never touches the boundary.
- Review summary (rev-maria, "document `burst` in the README") - **Agree, S.** `README.md` never mentions `burst`. I will add a short section with an example.

Three calls are yours:

❓ **Q1** - **Push back on Tom's "`limit` is never validated" (`ratelimit/limiter.py:11`)**: Tom asks for a raise on a non-positive limit. The code already does that: `__init__` calls `_check_arguments` (`limiter.py:15`), which raises `ValueError` when `limit <= 0` (`limiter.py:34-35`), `test_rejects_non_positive_limit` covers `0` and `-1` (`tests/test_limiter.py:44-47`), and R4 requires exactly this. The likely cause of the comment: the call sits on the last line of `__init__`, outside the hunk he was reading. The reply would thank him for checking, point at `_check_arguments` and the test by name, and change no code. The alternative is to also move the `_check_arguments` call to the first line of `__init__` so the next reader sees it sooner; that is a readability preference, not a fix, and I would leave it out. Push back with no code change?

➡️ Yes: push back, citing `_check_arguments`, `test_rejects_non_positive_limit`, and R4; no code change.

---

❓ **Q2** - **Maria's unbounded `_hits` (`ratelimit/limiter.py:20`): expiry-based eviction instead of her LRU(1024)**: Her concern is right. `self._hits.setdefault(key, deque())` adds a key and nothing ever removes it, which also breaks R5 ("holds no state for a key that has no hits in the current window"); no test covers R5. Her remedy is wrong for this limiter, though: an LRU with `maxsize=1024` evicts a key that still has live hits as soon as 1024 other keys are touched, which resets its count and breaks R6 ("a key's count is never reset by activity on other keys"). I simulated it against the head code: one hit on `a`, 1024 other keys, and `a` is allowed again inside the same window, so a caller rotating keys can defeat the limit.

The remedy I would plan instead: keep `_hits` in an `OrderedDict` ordered by each key's newest hit, and at the start of `allow()` (and in `tracked_keys()`) drop keys from the front whose newest hit has left the window. Amortized O(1) per call, no live state is ever dropped, R5 and R6 both hold. I prototyped it against the head code: the six existing tests pass, an idle key is dropped once its window passes, and a key keeps its count across 2000 other keys. Size M: `limiter.py` plus three tests (R5 on the same key, R5 via other keys' activity, R6 under many keys). No spec change, since this brings the code to R5 as written.

The trade-off to state honestly in the reply: memory is then bounded by the keys active within one window, not by a fixed number. Go with expiry-based eviction over the LRU?

➡️ Yes: agree with modification - expiry-based eviction, with the R6 simulation as the reason the LRU is not used.

---

❓ **Q3** - **Tom's "Hmm, is this right?" (`ratelimit/limiter.py:10`)**: The comment sits on the `__init__` signature, `def __init__(self, limit, window_seconds, burst=0, clock=time.monotonic)`, and does not say which part he doubts. I checked the three readings I could think of and found nothing wrong: `burst=0` matches R1 (ceiling is `limit + burst`), `clock=time.monotonic` is the right default for a window that must not move when the wall clock is adjusted, and the argument order matches the README example. If you know what he meant (from a call or a chat), tell me and I will classify it properly. Otherwise I would reply asking him which of the three he means, with one line on what each does today, and make no code change. Ask Tom?

➡️ Yes: post the clarifying question to Tom; no code change until he answers.

# Step 3 - Grilling session: round 2

Settled so far: Q1 push back with no code change; Q2 expiry-based eviction instead of the LRU; Q3 ask Tom. Q2 opens one question:

❓ **Q4** - **Hard memory cap: follow-up, not this PR**: With expiry-based eviction, a flood of distinct keys inside one window still grows `_hits` for that window. A fixed cap (Maria's `maxsize=1024`, or any number) can only be met by dropping live state, which R6 forbids, so it needs a product decision on what happens at the cap (reject new keys, or relax R6) and a spec change. That is beyond what RATE-12's requirements ask for. I would keep it out of this PR, say so in the reply to Maria, offer to open a ticket if she wants a hard cap, and record it in the PR description as deferred with "no ticket yet". Keep the hard cap out of this PR?

➡️ Yes: defer the hard cap; mention it in the reply and the PR description as deferred, no ticket yet.

# Step 3 - Grilling session: round 3 (confirmation)

The frontier is empty. Settled decisions:

- **D1** - Execute mode on `feat/RATE-12-limiter`; RATE-12's spec (`specs/rate-12-limiter/requirements.md`) stands in for the Jira ticket, which is unavailable.
- **D2** - `limiter.py:21` window boundary (rev-maria): Agree. Change the expiry comparison to `<=` and add a boundary test.
- **D3** - `limiter.py:11` limit validation (rev-tom): Push back, citing `_check_arguments`, `test_rejects_non_positive_limit`, and R4. No code change; the `_check_arguments` call is not moved.
- **D4** - `limiter.py:20` unbounded `_hits` (rev-maria): Agree with modification. Expiry-based eviction (`OrderedDict` ordered by newest hit, swept in `allow()` and `tracked_keys()`), not an LRU, because an LRU breaks R6. Tests for R5 and R6. No spec change.
- **D5** - `limiter.py:10` "Hmm, is this right?" (rev-tom): Needs clarification. Ask Tom which part of the signature he means; no code change.
- **D6** - README `burst` documentation (rev-maria's review summary): Agree. Answered in the one conversation comment.
- **D7** - A hard memory cap is out of scope for this PR: deferred, no ticket yet, offered to Maria in the reply.
- **D8** - Three commits on top of the PR head, in this order: boundary fix, eviction, README. The resolved `windw` thread gets no reply.

❓ **Q5** - **Shared understanding**: Next I write `review_response_7.md` from D1-D8, have the plan reviewed (codex is not installed here, so two adversarial reviewers take its place), implement the three commits test-first, and run `make lint` and `make test`. Nothing is pushed or posted until you approve the publish round. Are D1-D8 right and complete?

➡️ Yes: proceed on D1-D8.

# Step 5 - Plan review: reopened decisions (round 4)

The plan review (two adversarial reviewers standing in for codex, which is not installed) returned 16 findings after merging duplicates. I checked each against the code: 13 accepted, 2 rejected, 1 deferred; the table is in the plan's Plan review section. Three accepted findings touch decisions you already settled, so they come back to you before I apply them. I reproduced each one.

❓ **Q6** - **T4 and R1: the class docstring contradicts R1 (reopens D5 and D6)**: Two lines above Tom's "Hmm, is this right?", inside the hunk he was reading, the class docstring says "Allows at most `limit` hits per key" (`ratelimit/limiter.py:8`). The ceiling is `limit + burst` (`limiter.py:11`, R1, `test_burst_raises_the_ceiling`). My first pass said there was no defect near that line; that was wrong. It is the most likely thing Tom meant, and it is the same gap Maria's summary names: `burst` is undocumented. I would correct the docstring in the documentation commit alongside the README section, tell Tom that this is the one thing I found wrong near the line, and still ask him whether it is what he meant. T4 stays "needs clarification", but it is no longer "no code change". Fix the docstring with the README and name it in the reply to Tom?

➡️ Yes: one documentation commit covers the README and the docstring; the T4 reply names the docstring fix and asks Tom to confirm.

---

❓ **Q7** - **T2: the validation lets NaN through (reopens the wording of D3)**: The push back stands: `0` and `-1` raise, as Tom asked, and the test proves it. But my drafted reply ended "if you saw a path that gets around the check, point me at it", and there is one: `limit=float('nan')` passes the `limit <= 0` comparison and gives a limiter that never limits (the same holds for a NaN `burst`; a NaN `window_seconds` gives hits that never expire). R4 says anything not positive raises. Nobody raised it, it is the opposite failure from Tom's, and it shares no root cause with a planned change, so it belongs in a follow-up, not this PR. I would not invite Tom to find a gap I already know about: the reply would state the NaN gap in one sentence and say it is noted as a follow-up, the PR description would list it as deferred with "no ticket yet", and no code changes. Disclose and defer?

➡️ Yes: keep the push back, replace the closing sentence with a one-line disclosure of the NaN gap, defer the fix (no ticket yet).

---

❓ **Q8** - **T3: the eviction sweep needs a lock (reopens D4)**: The sweep iterates and deletes from the shared `OrderedDict` on every `allow()`. With four threads calling `allow()` on distinct keys, the head code never raises (it can over-admit, but it returns), while my prototype raised `RuntimeError: OrderedDict mutated during iteration` in 20 of 20 short runs. A rate limiter is called per request, so that would be a regression this PR introduced in answering a review comment. Holding a `threading.Lock` in `allow` and `tracked_keys` fixed it: 0 of 20 runs raised. The test is a bounded stress test in the repo's idiom (four threads, 5000 calls each, an injected counter clock, about 0.1s) that fails without the lock every time. The alternative is to leave the lock out and write "not thread-safe, callers must serialize" in the reply and the README. I would add the lock, and not add a thread-safety requirement to the spec in this PR: the spec is silent on threads, so whether RATE-12 should promise it goes to Open questions. Add the lock in the eviction commit?

➡️ Yes: add the lock and the stress test in the eviction commit; no new spec requirement, thread-safety as a spec promise goes to Open questions.

# Step 5 - Plan review: settled decisions after round 4

- **D3 (amended)** - T2: Push back stands, no code change. The reply discloses the NaN gap in R4's validation and defers it (no ticket yet).
- **D4 (amended)** - T3: expiry-based eviction as before, with `allow` and `tracked_keys` holding a `threading.Lock`, and a bounded stress test. No spec change.
- **D5 (amended)** - T4: Needs clarification stands. The reply names the docstring fix as the likely meaning and asks Tom to confirm.
- **D6 (amended)** - R1: one documentation commit covers the README "Burst allowance" section and the class docstring.
- **D9** - Thread-safety as a spec requirement, and the NaN validation gap, are deferred: Open questions and the PR description, no ticket yet.

D1, D2, D7, and D8 are unchanged.

# Step 7 - Publish round

The three commits are in and the gates are green on `HEAD` (`make lint` pass, `make test` pass with 13 tests; no formatter or build step is configured). Nothing has left this machine yet.

❓ **Q9** - **Publish the review response for PR #7**: "Yes" sends everything below, in this order: push, replies, PR description, re-request. Strike any part you do not want sent.

**Push** to `origin`, branch `feat/RATE-12-limiter` (fast-forward from `9fa93f4`, no force):

- `78e6f66` fix(limiter): expire hits exactly one window old (RATE-12)
- `1e0c71e` fix(limiter): drop keys whose hits have all expired (RATE-12)
- `c3601b5` docs(limiter): document the burst allowance (RATE-12)

**Replies**, posted as `dev-author` (full text in `/tmp/rr-eval/happy-path-2/repo/review_response_7.md`):

- `ratelimit/limiter.py:21` - Agree - "You're right."
- `ratelimit/limiter.py:11` - Push back - "A limiter that silently rejects everything would be a bad failure mode, so it was worth checking."
- `ratelimit/limiter.py:20` - Agree with modification - "You're right that `_hits` only ever grew: `setdefault` added a key and nothing removed it, which also broke R5 (no state for a key with no hits in the current window)."
- `ratelimit/limiter.py:10` - Needs clarification - "Could you say which part you have in mind?"
- conversation comment (rev-maria's review summary) - Agree - "Done in c3601b5."

The dry run holds nothing: all four threads and the conversation comment would post. The resolved thread at `tests/test_limiter.py:32` gets no reply. Threads stay unresolved; resolving them is the reviewers' call.

**PR description**, appended as a marked block; the description you wrote stays as it is:

> ## Review response
>
> Changes since the review of 9fa93f4:
>
> - **Window boundary** (78e6f66): a hit exactly `window_seconds` old no longer counts, as R3 requires. Tests pin both sides of the boundary.
> - **Key eviction** (1e0c71e): a key whose hits have all expired is dropped on the next `allow()` or `tracked_keys()` call (R5). Eviction is by expiry, not an LRU, so a key's count is never reset by activity on other keys (R6). `allow()` and `tracked_keys()` now take a lock, because the sweep changes shared state on every call.
> - **Documentation** (c3601b5): the README has a "Burst allowance" section, and the class docstring states the ceiling as `limit + burst`.
>
> Deferred:
>
> - A hard cap on the number of tracked keys. It needs a spec decision, since R6 forbids dropping live state. No ticket yet.
> - Thread-safety as a spec requirement. The lock is in; the spec is silent on threads. No ticket yet.
> - NaN for `limit`, `burst`, or `window_seconds` passes argument validation, contrary to R4. No ticket yet.

**Re-request review** from `rev-maria`: she requested changes, and both of her threads and her summary get a reply. `rev-tom` only commented, so he is not re-requested; he is notified by the two replies.

Publish all of it?

➡️ Yes: push the three commits, post the five replies, update the PR description, and re-request rev-maria.
