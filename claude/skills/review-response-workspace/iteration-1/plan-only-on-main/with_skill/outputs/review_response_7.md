# Review response - PR #7

## Header

- **PR:** https://github.example.invalid/acme/ratelimit/pull/7 - "RATE-12: sliding-window rate limiter"
- **Author:** dev-author (replies post as `dev-author`)
- **Branches:** `feat/RATE-12-limiter` -> `main`, head `c54571802eb02c2bd420503c9682ac9dc021a401`, state OPEN
- **Ticket:** RATE-12 (key taken from the branch name). **Jira context unavailable**: Jira was unreachable in this session, so no summary, status, or acceptance criteria were read. `specs/rate-12-limiter/requirements.md` (R1-R6) stands in as the statement of intended behavior.
- **Date:** 2026-11-20
- **Mode:** plan-only (D1). Nothing below has been implemented, committed, pushed, or posted.
- **Items:** 6 total - 5 to answer (4 unresolved threads + 1 review summary), 1 resolved thread. 0 outdated. Conversation comments 8001 (author) and 8002 (CI bot) ask for nothing.

All code, test, and spec citations are at the PR head `c545718`, not at `main`.

## Summary table

| # | Anchor | Classification | Size | Priority |
|---|---|---|---|---|
| 5001 | `ratelimit/limiter.py:21` - rev-maria - "A hit that is exactly `window_seconds` old should already have expired..." | Agree | S | P1 (spec violation, changes requested) |
| 5003 | `ratelimit/limiter.py:20` - rev-maria - "`_hits` grows without bound: once a key is seen it is never removed..." | Agree with modification | M | P1 (spec violation, changes requested) |
| 7001 | review summary - rev-maria - "...please document `burst` in the README before this merges..." | Agree | S | P1 (named merge blocker) |
| 5002 | `ratelimit/limiter.py:11` - rev-tom - "`limit` is never validated..." | Push back | - | P2 |
| 5004 | `ratelimit/limiter.py:10` - rev-tom - "Hmm, is this right?" | Needs clarification | - | P3 |
| 5005 | `tests/test_limiter.py:32` - rev-tom - "nit: this was `test_hits_expire_after_windw`..." | Resolved, no action | - | - |

## Settled decisions

- **D1** - Mode is plan-only. The user stays on `main`; nothing is checked out, changed, committed, pushed, or posted in this run.
- **D2** - 5002: push back, citing `limiter.py:15`, `limiter.py:34-35`, `tests/test_limiter.py:44-47`, and R4. No code change (the validation call is not moved).
- **D3** - 5003: agree with modification. Expiry-based key eviction (R5) instead of the requested LRU with `maxsize=1024`, because the LRU conflicts with R6. Size M, in this PR, no spec edit.
- **D4** - 5004: needs clarification. Post the three-option question; no code change until rev-tom answers.
- **D5** - Unraised findings: fix the class docstring (`limiter.py:8`) together with the README change for review 7001. Type validation (wrong-typed arguments raise `TypeError` where R4 says `ValueError`; needs an explicit type check), NaN acceptance for all three arguments, and the missing negative-`burst` / negative-window tests stay out of this PR and are recorded as open questions. (Reconfirmed in Step 5 after the plan review corrected the cause of the `TypeError`.)
- **D6** - A hard cap on distinct keys is out of scope for this PR. The 5003 reply says so and the user files a follow-up ticket to RATE-12; it is listed under Open questions.
- **D7** - Ticket evidence: Jira context unavailable; the spec stands in as the statement of intended behavior.

## Cross-cutting themes

- **T1 - The code drifted from the spec where no test pins it (5001, 5003).** R3's boundary and R5's key lifetime are both stated in the spec and both violated at the head; the six existing tests exercise neither (the expiry test advances 11s on a 10s window, and nothing calls `tracked_keys()`). One action: bring `allow()` back to R3 and R5 in a single change to `ratelimit/limiter.py`, with tests per requirement touched (R3 on both sides of the boundary and with a newer hit still live, R5 through `tracked_keys()` and through `allow()` alone, the eviction order, and R6 as a guard against the LRU remedy). Both fixes edit the same loop in `allow()`, so they are made together and land in one commit.
- **T2 - The constructor's contract is not readable from the outside (7001, and likely what 5002 and 5004 trip over).** `burst` is absent from the README and the class docstring contradicts R1; the validation exists but sits after the assignments, which is why 5002 reads it as missing; 5004 questions the signature without saying why. One action for the documentation half: README section plus a corrected docstring (D5). The position of the validation call is deliberately not touched (D2).

## Per-item detail

### 5001 - `ratelimit/limiter.py:21` - rev-maria

> A hit that is exactly `window_seconds` old should already have expired: R3 in the spec says the window is half-open, `(now - W, now]`. This `<` keeps that hit for one more tick. Can you fix it and add a boundary test?

- **root_comment_id:** 5001
- **comment_count:** 1
- **Classification:** Agree
- **Evidence:**
  - Code: `ratelimit/limiter.py:21` is `while hits and hits[0] < now - self._window:`. A hit with `hits[0] == now - W` is kept, so the effective window is closed, `[now - W, now]`. Confirmed by running the head code with a fake clock: limit=1, W=10, hit at t=1000, `allow("a")` at t=1010 returns `False`.
  - Tests: `test_hits_expire_after_window` (`tests/test_limiter.py:32-36`) advances 11s on a 10s window, so it passes with `<` and with `<=`. The exact-boundary case is untested.
  - Spec: R3 - "A hit at time `t` counts against the half-open window `(now - W, now]`. A hit exactly `W` seconds old no longer counts."
  - Ticket: Jira context unavailable.
- **Action (S):**
  - `tests/test_limiter.py`, written first:
    - `test_hit_exactly_one_window_old_no_longer_counts` (limit=1, W=10; hit, `advance(10)`, second hit is allowed) - fails at the head.
    - `test_boundary_hit_expires_while_newer_hit_still_counts` (limit=2, W=10; hits at t and t+5; the hit at t+10 is allowed and the next one is rejected) - fails at the head. This is the test that pins the `<=` on the flagged line: once 5003 lands, the limit=1 case is settled by the key-level drop before the per-key loop runs, and reverting the per-key loop to `<` passed every other test in a scratch build.
    - `test_hit_just_inside_window_still_counts` (hit, `advance(9.5)`, second hit is rejected) pins the other side - passes before and after.
  - `ratelimit/limiter.py:21`: `<` becomes `<=`.
  - Spec: no edit. The code moves to what R3 already says.
- **Reply:**

  > You're right. R3 defines the window as `(now - W, now]`, and the `<` here kept a hit that was exactly `window_seconds` old for one more tick. I changed the comparison to `<=` in `<sha>` and added three tests: `test_hit_exactly_one_window_old_no_longer_counts` (a 10s window, second hit exactly 10s after the first, now allowed), `test_boundary_hit_expires_while_newer_hit_still_counts` (the same boundary while a newer hit keeps the key alive), and `test_hit_just_inside_window_still_counts` for the other side of the boundary. The existing expiry test advanced 11s, which is why it never caught this.

- **Dependencies:** shares the pruning loop in `allow()` with 5003; implemented and committed together (T1).
- **Posted:**

### 5003 - `ratelimit/limiter.py:20` - rev-maria

> `_hits` grows without bound: once a key is seen it is never removed. Wrap this in an LRU with `maxsize=1024` so memory stays capped.

- **root_comment_id:** 5003
- **comment_count:** 1
- **Classification:** Agree with modification (D3)
- **Evidence:**
  - Code: `ratelimit/limiter.py:14` is `self._hits = {}` and `limiter.py:20` is `hits = self._hits.setdefault(key, deque())`. `popleft()` at line 22 empties a deque but nothing deletes a key. Confirmed by running the head code: 5 keys hit once, clock advanced 100s on a 10s window, `tracked_keys()` still returns 5. The diagnosis holds.
  - Tests: untested. No test calls `tracked_keys()` (`limiter.py:28-30`) or covers key removal.
  - Spec: R5 - "The limiter holds no state for a key that has no hits in the current window." The head already violates it. R6 - "A key's count is never reset by activity on other keys." An LRU capped at 1024 evicts the least-recently-used key even while it has hits inside its window, which resets its count because other keys were active. The spec names no cap, no LRU, and no 1024.
  - Ticket: Jira context unavailable.
- **Action (M):**
  - `tests/test_limiter.py`, written first:
    - `test_holds_no_state_for_keys_without_hits_in_window` - three keys hit once, `tracked_keys() == 3`; `advance(10)`; `tracked_keys() == 0`; one more hit, `tracked_keys() == 1`. Fails at the head (3 != 0).
    - `test_idle_key_expires_behind_a_recently_hit_key` - limit=2; `a` at t, `b` at t+1, `a` again at t+5; at t+11 `tracked_keys() == 1`. Fails at the head; pins the `move_to_end` after an accepted hit.
    - `test_rejected_hit_does_not_extend_key_lifetime` - two keys: `a` at t, `b` at t+5, `a` rejected at t+6; at t+10 `tracked_keys() == 1`. Fails at the head; pins that a rejected hit does not reorder or keep a key alive.
    - `test_allow_alone_releases_expired_keys` - 100 distinct keys, each 11s apart on a 10s window, calling only `allow()`; asserts `len(limiter._hits) == 1`. Fails at the head. It reads the private `_hits` on purpose: `tracked_keys()` prunes on its own, so it cannot show that `allow()` does. It is the only test that reaches into a private attribute.
    - `test_other_keys_never_reset_a_live_count` - limit=1; hit `a`; hit 5000 other keys; `allow("a")` is still rejected. Passes before and after; it pins R6 so a size-capped cache cannot be swapped in later without a spec change.
  - `ratelimit/limiter.py`:
    - `_hits` becomes a `collections.OrderedDict` kept in order of each key's newest hit (`move_to_end(key)` after an accepted hit; the clock is monotonic, so the order holds).
    - New `_drop_expired_keys(now)`: pop keys from the front while the front key's newest hit satisfies `hits[-1] <= now - self._window`.
    - `allow()` calls it before looking the key up; `tracked_keys()` calls it with `self._clock()` so the reported count honors R5 without waiting for the next `allow()`.
    - `setdefault(key, deque())` is replaced by a get-or-create so no deque is allocated per call.
  - Cost: amortized O(1) per call; each key is inserted and removed once per idle period.
  - Spec: no edit. The code moves to what R5 and R6 already say.
  - Prototyped against a scratch copy of the head with the full planned test set (6 existing + 8 new = 14): six of the new tests fail at the head, all 14 pass after the change, and `make lint`'s compile check passes. Four mutants of the fix (per-key loop back to `<`; no drop in `allow()`; no `move_to_end`; `move_to_end` on a rejected hit) each fail exactly one of the new tests.
- **Reply:**

  > Agreed on the problem: a key was never removed once seen, so `_hits` grew with every distinct key, and that also broke R5 (no state for a key with no hits in the current window). I fixed it a different way from the LRU, though. A cache capped at 1024 evicts the least-recently-used key even when it still has hits inside its window, so its count restarts because other keys were active. R6 rules that out: hits on any 1024 other keys would reset it, and wherever callers choose their own key (an IP, a token) a client could do that to itself.
  >
  > In `<sha>`, `_hits` is an `OrderedDict` kept in order of each key's newest hit, and `allow()` and `tracked_keys()` drop keys from the front once their newest hit has left the window. Memory is now bounded by the keys active within one `window_seconds`, at amortized O(1) per call. Tests: `test_holds_no_state_for_keys_without_hits_in_window`, `test_idle_key_expires_behind_a_recently_hit_key`, `test_rejected_hit_does_not_extend_key_lifetime`, `test_allow_alone_releases_expired_keys`, and `test_other_keys_never_reset_a_live_count` (5000 other keys do not reset a live count).
  >
  > What this does not give you is a fixed ceiling: a flood of distinct keys inside a single window still grows the map until the window passes. Capping that needs a decision on what happens at the cap (reject new keys, or evict and relax R6) and a spec change, so I'll file a follow-up to RATE-12 for it instead of folding it into this PR.

- **Dependencies:** same loop as 5001 (T1). The last paragraph of the reply depends on D6. The follow-up ticket does not exist yet (see Open questions): Execution order step 11 asks the user for its key before publishing and rewrites the sentence to cite it ("I've filed <KEY> for it") if it has been filed; otherwise the "I'll file" wording stands as the user's commitment.
- **Posted:**

### 7001 - review summary (CHANGES_REQUESTED) - rev-maria

> Close. Two things inline, and please document `burst` in the README before this merges: right now nobody reading it can tell the parameter exists.

- **review id:** 7001 (a review summary has no thread; it is answered in the single conversation comment, `{"conversation": true}`)
- **Classification:** Agree
- **Evidence:**
  - Code: `README.md` at the head is 11 lines with one example, `SlidingWindowLimiter(limit=100, window_seconds=60)` (`README.md:8`); the word `burst` does not appear. The parameter exists at `ratelimit/limiter.py:10-11`. The class docstring at `limiter.py:8` says "Allows at most `limit` hits per key", which is false when `burst > 0`.
  - Tests: `test_burst_raises_the_ceiling` (`tests/test_limiter.py:38-42`) pins the behavior to document: limit=1, burst=1 allows two hits and rejects the third.
  - Spec: R1 - "`allow(key)` returns True for at most `limit + burst` hits per key within any window." R4 - "`burst` must not be negative".
  - Ticket: Jira context unavailable.
  - "Two things inline" are her threads 5001 and 5003.
- **Action (S):**
  - `README.md`: add a "Burst" section after the example: `burst` (default 0) raises the per-key ceiling to `limit + burst` hits in any window; it is a fixed addition, not an allowance that refills separately; it must not be negative (`ValueError`). Include `SlidingWindowLimiter(limit=100, window_seconds=60, burst=20)` with a one-line comment that it allows 120 hits per key per 60s.
  - `ratelimit/limiter.py:8` (D5): docstring becomes "Allows at most `limit + burst` hits per key in any window of `window_seconds`."
  - Tests: none; documentation only, behavior already pinned by `test_burst_raises_the_ceiling`.
  - Spec: no edit.
- **Reply** (conversation comment):

  > > please document `burst` in the README before this merges
  >
  > Done in `<sha>`. The README now has a Burst section: `burst` defaults to 0, raises the per-key ceiling to `limit + burst` hits in any window (R1), is a fixed addition and not a separately refilling allowance, and must not be negative (R4), with an example. The class docstring said "at most `limit` hits", which was wrong once a burst is set, so I corrected that in the same commit. The two inline points are answered on their threads.

- **Dependencies:** the docstring line is in `ratelimit/limiter.py`, which the T1 commit also edits; see Execution order for which commit carries it.
- **Posted:**

### 5002 - `ratelimit/limiter.py:11` - rev-tom

> `limit` is never validated. Zero or a negative value gives a limiter that silently rejects everything. Please raise on a non-positive limit.

- **root_comment_id:** 5002
- **comment_count:** 1
- **Classification:** Push back (D2)
- **Evidence:**
  - Code: `ratelimit/limiter.py:15` calls `self._check_arguments(limit, window_seconds, burst)`; `limiter.py:34-35` is `if limit <= 0: raise ValueError(f"limit must be positive, got {limit}")`. Confirmed by running the head code: `limit=0` and `limit=-1` both raise `ValueError`. No limiter with a non-positive limit can be constructed.
  - Tests: `test_rejects_non_positive_limit` (`tests/test_limiter.py:44-47`) asserts `ValueError` for `limit in (0, -1)`.
  - Spec: R4 - "`limit` and `window_seconds` must be positive and `burst` must not be negative; anything else raises `ValueError` at construction."
  - Ticket: Jira context unavailable.
  - What is right in the comment: the check runs after the assignments at lines 11-14, so it is not visible at the line he flagged.
- **Action:** no code change.
- **Reply:**

  > `limit` is validated, just not on this line. The last statement of `__init__` is `self._check_arguments(limit, window_seconds, burst)`, and `_check_arguments` raises `ValueError("limit must be positive, got ...")` on `limit <= 0`, which is what R4 asks for. `test_rejects_non_positive_limit` constructs with 0 and -1 and asserts the `ValueError`, so a limiter that silently rejects everything can't be built. Fair point that the call sits after the assignments and is easy to miss reading down from this line. I've left the code as it is; if you have a zero or negative limit that gets past the check, send it over and I'll add it to that test.

- **Dependencies:** none. Related to 5004 (same reviewer, adjacent line). The reply cites code by name, not by line: the line numbers in the Evidence block hold at `c545718` only, and commit 1 moves `_check_arguments` down the file before this reply is posted.
- **Posted:**

### 5004 - `ratelimit/limiter.py:10` - rev-tom

> Hmm, is this right?

- **root_comment_id:** 5004
- **comment_count:** 1
- **Classification:** Needs clarification (D4)
- **Evidence:**
  - Code: `ratelimit/limiter.py:10` is `def __init__(self, limit, window_seconds, burst=0, clock=time.monotonic):`. The comment names no defect. Plausible readings: (1) `burst` applied as a flat addition (`limiter.py:11`, `self._limit = limit + burst`); (2) the `clock=time.monotonic` default; (3) all parameters positional-or-keyword, so `SlidingWindowLimiter(100, 60, 5)` sets `burst` silently.
  - Tests: `test_burst_raises_the_ceiling` (`tests/test_limiter.py:38-42`) pins reading (1) as intended. Every test passes arguments by keyword, so positional order is untested. The clock default is not exercised (all tests inject `FakeClock`, as `CLAUDE.md` requires).
  - Spec: R1 makes the flat `limit + burst` ceiling the specified behavior. No spec coverage for the clock default or for keyword-only parameters.
  - Ticket: Jira context unavailable.
- **Action:** no code change until rev-tom answers.
- **Reply:**

  > Which part of the signature are you questioning? Three things I can see someone doubting on this line:
  >
  > 1. `burst` is a flat addition to the ceiling (`limit + burst` hits per window, per R1 and `test_burst_raises_the_ceiling`), not an allowance that refills on its own schedule.
  > 2. `clock=time.monotonic` as the default clock.
  > 3. All four parameters are positional-or-keyword, so `SlidingWindowLimiter(100, 60, 5)` sets `burst` without naming it.
  >
  > Tell me which one, or what else you had in mind, and I'll address that specifically.

- **Dependencies:** none for this round. His answer may bring in the type-validation finding (Open questions).
- **Posted:**

### 5005 - `tests/test_limiter.py:32` - rev-tom (resolved)

> nit: this was `test_hits_expire_after_windw` in the first push

- **root_comment_id:** 5005
- **comment_count:** 2 (author replied "Fixed."; resolved by rev-tom)
- **Classification:** none - resolved, listed for completeness
- **Evidence:** `tests/test_limiter.py:32` is `def test_hits_expire_after_window(self):`; `windw` appears nowhere in the tree at the head. The concern is not live.
- **Action:** no code change, no reply.
- **Posted:** (not applicable)

## Execution order

Not started (plan-only). When executed on `feat/RATE-12-limiter`:

1. [ ] `tests/test_limiter.py`: add the three R3 tests (5001) and the five R5/R6 tests (5003). Confirm that six fail at the head (`test_hit_exactly_one_window_old_no_longer_counts`, `test_boundary_hit_expires_while_newer_hit_still_counts`, `test_holds_no_state_for_keys_without_hits_in_window`, `test_idle_key_expires_behind_a_recently_hit_key`, `test_rejected_hit_does_not_extend_key_lifetime`, `test_allow_alone_releases_expired_keys`) and two pass (`test_hit_just_inside_window_still_counts`, `test_other_keys_never_reset_a_live_count`). All tests use the injected `FakeClock`.
2. [ ] `ratelimit/limiter.py`: `<` to `<=` in the pruning loop (5001).
3. [ ] `ratelimit/limiter.py`: `OrderedDict`, `_drop_expired_keys`, calls from `allow()` and `tracked_keys()`, `move_to_end` after an accepted hit (5003).
4. [ ] Gates: `make lint`, `make test`. No formatter and no build step are defined (`CLAUDE.md`), so those are "not configured".
5. [ ] Commit 1 - `fix(limiter): expire boundary hits and idle keys per R3 and R5 (RATE-12)` - `ratelimit/limiter.py`, `tests/test_limiter.py` (steps 1-3). 5001 and 5003 share both files, so they are one commit.
6. [ ] `ratelimit/limiter.py`: corrected class docstring (7001 / D5). Made only after commit 1, so the whole file can be staged for commit 2 without splitting hunks.
7. [ ] `README.md`: Burst section (7001).
8. [ ] Gates again: `make lint`, `make test`.
9. [ ] Commit 2 - `docs(limiter): document burst in README and docstring (RATE-12)` - `README.md`, `ratelimit/limiter.py` (steps 6-7).
10. [ ] Replace `<sha>`: 5001 and 5003 cite commit 1; the `<sha>` in the 7001 reply cites commit 2. Re-read every reply against the new head: none may cite a line number that commit 1 or 2 moved.
11. [ ] Before publishing, ask the user for the follow-up ticket key (D6). If it exists, change the last sentence of the 5003 reply to cite it; if not, the "I'll file a follow-up" wording stays.
12. [ ] Publish: push, replies on 5001 / 5002 / 5003 / 5004, one conversation comment for 7001, PR description block, re-request rev-maria (she requested changes and every item of hers gets a reply).

No spec file changes in any step: every behavior change moves the code to what R3 and R5 already state, so the `CLAUDE.md` rule "a behavior change updates the spec in the same commit" has nothing to update.

## Open questions

- **Awaiting rev-tom (5004):** which part of the `__init__` signature he is questioning.
- **Follow-up ticket to file (D6, user):** hard cap on distinct keys within one window - behavior at the cap (reject new keys vs. evict) and the R6 amendment it would need. Not created in this run (Jira unreachable). Add its key to the 5003 reply once it exists.
- **Deferred, unraised findings (D5):**
  - Wrong-typed arguments raise `TypeError` where R4 says `ValueError`: from `limit + burst` at `ratelimit/limiter.py:11`, and from the comparisons in `_check_arguments` itself (`"5" <= 0`). Moving the validation call does not fix this (it only changes mixed cases such as `limit=0, burst=None`); meeting R4 needs an explicit type check. Possibly what 5004 is about.
  - `_check_arguments` (`limiter.py:34-39`) accepts NaN for all three arguments. A NaN `limit` or `burst` disables the ceiling (`len(hits) >= nan` is always False, so every hit is allowed); a NaN `window_seconds` means hits never expire.
  - No test for negative `burst` or negative `window_seconds` (both raise correctly at the head).
- **Jira:** RATE-12's acceptance criteria were not read. If they say something the spec does not (a key cap, for instance), 5003 and D6 should be revisited before executing.

## Plan review (Step 5)

Codex was not available (not installed in this environment), so two adversarial reviewers stood in: one on coverage and classification, one on replies, execution order, and scope. 10 findings, 8 distinct; 8 accepted, 0 rejected, 0 deferred. Each was checked against the PR head or a scratch build of the planned fix before being applied.

| # | Finding | Disposition | Applied as |
|---|---|---|---|
| A-F1, B-F5 | Cause of the `TypeError` on wrong-typed arguments was misstated as validation order | Accept (D5 reopened and reconfirmed) | D5 and Open questions reworded |
| A-F2 | NaN is also accepted for `burst`; range is `limiter.py:34-39` | Accept | Open questions |
| A-F3, B-F7 | 5003 reply's "client can clear its own count" claim was unconditional | Accept | 5003 reply made conditional on caller-chosen keys |
| B-F1 | limit=1 boundary test stops pinning the per-key `<=` once 5003 lands | Accept | Added `test_boundary_hit_expires_while_newer_hit_still_counts` |
| B-F2 | 5003 tests did not pin ordering or eviction through `allow()` alone | Accept | Added two tests, made the rejected-hit test two-key |
| B-F3 | Execution order could not produce the two commits as described | Accept | Execution order reordered |
| B-F4 | 5002 reply cited line numbers that commit 1 moves | Accept | 5002 reply cites by name; step 10 re-checks all replies |
| B-F6 | 5003 reply claimed a follow-up was being raised with no step doing it | Accept | Reply reworded; step 11 added |
