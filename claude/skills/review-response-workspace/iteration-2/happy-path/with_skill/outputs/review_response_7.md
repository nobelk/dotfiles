# Review response: PR #7

- **PR:** https://github.example.invalid/acme/ratelimit/pull/7 - "RATE-12: sliding-window rate limiter"
- **Author:** dev-author (replies post as `dev-author`)
- **Branches:** `feat/RATE-12-limiter` -> `main`, head `9fa93f46e91f32bc600faba0331e68dabde4cc15` at snapshot
- **Ticket:** RATE-12 (from the branch name). Jira context unavailable: no Atlassian server connected. Intent is taken from `specs/rate-12-limiter/requirements.md` (R1-R6).
- **Date:** 2026-11-20
- **Mode:** execute
- **Items:** 6 total / 5 unresolved (4 threads, 1 review summary) / 1 resolved or outdated

## Summary

| # | Anchor | Classification | Size |
|---|--------|----------------|------|
| T1 | `ratelimit/limiter.py:21` - rev-maria - "A hit that is exactly `window_seconds` old should already have expired..." | Agree | S |
| T2 | `ratelimit/limiter.py:11` - rev-tom - "`limit` is never validated." | Push back | - |
| T3 | `ratelimit/limiter.py:20` - rev-maria - "`_hits` grows without bound..." | Agree with modification | M |
| T4 | `ratelimit/limiter.py:10` - rev-tom - "Hmm, is this right?" | Needs clarification | S (docstring, with R1) |
| R1 | review summary 7001 - rev-maria (changes requested) - "please document `burst` in the README" | Agree | S |
| T5 | `tests/test_limiter.py:32` - rev-tom - "nit: this was `test_hits_expire_after_windw`..." | Resolved, no action | - |

Not items: review 7002 (rev-tom, empty body), conversation comment 8001 (the author's own), 8002 (ci-bot).

## Settled decisions

- **D1** - Execute mode on `feat/RATE-12-limiter`; the RATE-12 spec stands in for the Jira ticket, which is unavailable.
- **D2** - T1: Agree. Change the expiry comparison to `<=` and add a boundary test.
- **D3** (amended after plan review) - T2: Push back, citing `_check_arguments`, `test_rejects_non_positive_limit`, and R4. No code change; the `_check_arguments` call is not moved. The reply discloses the NaN gap in the validation and defers it.
- **D4** (amended after plan review) - T3: Agree with modification. Expiry-based eviction (`OrderedDict` ordered by newest hit, swept in `allow()` and `tracked_keys()`), not an LRU, because an LRU breaks R6. `allow` and `tracked_keys` hold a `threading.Lock`, because the sweep would otherwise raise under concurrent callers. Tests for R5, R6, and concurrent callers. No spec change.
- **D5** (amended after plan review) - T4: Needs clarification. The reply names the docstring fix as the likely meaning and asks Tom to confirm.
- **D6** (amended after plan review) - R1: Agree. One documentation commit covers the README "Burst allowance" section and the class docstring; answered in the one conversation comment.
- **D7** - A hard memory cap is out of scope for this PR: deferred, no ticket yet, offered to Maria in the T3 reply.
- **D8** - Three commits on top of the PR head, in this order: boundary fix, eviction, documentation. The resolved thread T5 gets no reply.
- **D9** (from plan review) - Thread-safety as a spec requirement, and the NaN validation gap, are deferred: Open questions and the PR description, no ticket yet.

## Cross-cutting themes

- **Expiry in `SlidingWindowLimiter.allow` (T1, T3).** Both of Maria's inline comments are about when state stops counting: T1 is the per-hit boundary, T3 is the per-key lifetime. They touch the same lines of `allow`, so T1 lands first and T3's key sweep uses the same cutoff rule (`<= now - window`), keeping one definition of "expired" (R3) for hits and keys. A test pins the boundary at each level.
- **`burst` is undocumented (R1, T4).** The README never mentions it and the class docstring says "at most `limit` hits", which contradicts R1. One documentation commit fixes both; it answers Maria's summary and is the likeliest meaning of Tom's question.

## Per-item detail

### T1 - `ratelimit/limiter.py:21` - rev-maria

> A hit that is exactly `window_seconds` old should already have expired: R3 in the spec says the window is half-open, `(now - W, now]`. This `<` keeps that hit for one more tick. Can you fix it and add a boundary test?

- **Thread:** `root_comment_id` 5001, `comment_count` 1
- **Classification:** Agree
- **Evidence:**
  - Code: `ratelimit/limiter.py:21` is `while hits and hits[0] < now - self._window:`. A hit at `t` checked at `now = t + W` gives `t < t`, false, so the hit stays and counts.
  - Tests: `test_hits_expire_after_window` (`tests/test_limiter.py:32-36`) advances 11s on a 10s window; nothing tests exactly `W`. Untested.
  - Spec: R3 (`specs/rate-12-limiter/requirements.md:5`): "A hit exactly `W` seconds old no longer counts."
  - Reproduced at head: `limit=1, window_seconds=10`, hit, advance 10, second `allow` returns False.
  - The reviewer's claim holds: yes.
- **Action (S):** in `ratelimit/limiter.py`, change the comparison in `allow` to `<=`. In `tests/test_limiter.py`, add `test_hit_exactly_window_old_has_expired` (fails at head) and `test_hit_just_inside_window_still_counts` (guards the other side). No spec change: the code moves to R3 as written.
- **Reply:**

  > You're right. The expiry check compared with `<`, so a hit exactly `window_seconds` old survived one more call, which contradicts R3's half-open window `(now - W, now]`. I changed the comparison in `SlidingWindowLimiter.allow` to `<=` in 78e6f66 and added two tests, `test_hit_exactly_window_old_has_expired` (a hit at `t` no longer counts at `t + W`) and `test_hit_just_inside_window_still_counts`, so both sides of the boundary are pinned. The existing `test_hits_expire_after_window` advanced 11s on a 10s window, which is why it never caught this.

- **Depends on:** nothing. T3 builds on it.
- **Posted:** https://github.example.invalid/acme/ratelimit/pull/7#discussion_r9001

### T2 - `ratelimit/limiter.py:11` - rev-tom

> `limit` is never validated. Zero or a negative value gives a limiter that silently rejects everything. Please raise on a non-positive limit.

- **Thread:** `root_comment_id` 5002, `comment_count` 1
- **Classification:** Push back
- **Evidence:**
  - Code: `__init__` calls `self._check_arguments(limit, window_seconds, burst)` at `ratelimit/limiter.py:15`; `_check_arguments` raises `ValueError` when `limit <= 0` (`ratelimit/limiter.py:34-35`). The call is the last line of `__init__`, below the hunk the comment is attached to (lines 5-11).
  - Tests: `test_rejects_non_positive_limit` (`tests/test_limiter.py:44-47`) asserts `ValueError` for `0` and `-1`.
  - Spec: R4 (`requirements.md:6`) requires exactly this.
  - The reviewer's claim holds: no. The validation exists and is tested for the values he names.
  - Found in plan review, not raised by the reviewer: `limit=float('nan')` passes `limit <= 0` and yields a limiter that never rejects (reproduced at head; also a NaN `burst`, and a NaN `window_seconds` gives hits that never expire). It is the opposite failure mode and shares no root cause with a planned action. See Open questions.
- **Action:** no code change.
- **Reply:**

  > A limiter that silently rejects everything would be a bad failure mode, so it was worth checking. It is already covered, though: `__init__` ends with a call to `_check_arguments`, which raises `ValueError` when `limit <= 0` (and for a non-positive `window_seconds` or a negative `burst`), as R4 requires. `test_rejects_non_positive_limit` exercises both `0` and `-1`. The call is the last line of `__init__`, just below the hunk this comment is attached to, so it is easy to miss from the diff. I've left the code as is.
  >
  > One gap I did find while re-checking, separate from the one you describe: a NaN `limit` gets past the `<= 0` comparison and gives a limiter that never rejects. That is the opposite failure mode and outside what this review asked for, so I've listed it in the PR description as a follow-up instead of widening this PR.

- **Depends on:** nothing.
- **Posted:** https://github.example.invalid/acme/ratelimit/pull/7#discussion_r9002

### T3 - `ratelimit/limiter.py:20` - rev-maria

> `_hits` grows without bound: once a key is seen it is never removed. Wrap this in an LRU with `maxsize=1024` so memory stays capped.

- **Thread:** `root_comment_id` 5003, `comment_count` 1
- **Classification:** Agree with modification
- **Evidence:**
  - Code: `ratelimit/limiter.py:20` is `hits = self._hits.setdefault(key, deque())`; nothing in the class deletes from `self._hits`. `tracked_keys()` (`limiter.py:28-30`) reports `len(self._hits)`.
  - Tests: none covers key lifetime. Untested.
  - Spec: R5 (`requirements.md:7`): "The limiter holds no state for a key that has no hits in the current window." The head code violates it. R6 (`requirements.md:8`): "A key's count is never reset by activity on other keys."
  - The reviewer's remedy against R6: an LRU of 1024 evicts a key with live hits once 1024 other keys are touched. Simulated over the head logic with `limit=1`: one hit on `a`, 1024 other keys, then `a` is allowed again inside the same window (1023 other keys: still rejected).
  - The planned remedy, prototyped against the head code: the six existing tests pass; an idle key is dropped once its window has passed; a key keeps its count across 2000 other keys. A reviewer's 3000-sequence fuzz against a reference model found no R5 or R6 violation and no change in `allow()` decisions under a non-decreasing clock.
  - Concurrency (found in plan review, reproduced): four threads calling `allow()` on distinct keys never raise at head; the sweep without a lock raised `RuntimeError: OrderedDict mutated during iteration` in 20 of 20 runs; with a `threading.Lock` held in `allow` and `tracked_keys`, 0 of 20.
  - The reviewer's claim holds: partially. The growth is real; the LRU would trade it for a correctness bug.
- **Action (M):** in `ratelimit/limiter.py`:
  - make `_hits` an `OrderedDict` kept in order of each key's newest hit, with `move_to_end` on every accepted hit; a comment states that this relies on `clock` never going backwards;
  - add `_drop_expired_keys(now)`, which removes keys from the front while their newest hit is `<= now - window`, and call it at the start of `allow` and in `tracked_keys`;
  - hold a `threading.Lock` for the body of `allow` and of `tracked_keys`;
  - keep the `setdefault` lookup as it is (it never leaves an empty deque stored, because the ceiling is at least 1).

  In `tests/test_limiter.py`, add:
  - `test_idle_key_is_dropped_after_window` (R5): one hit, advance exactly `window_seconds`, `tracked_keys() == 0`. Fails at head. Advancing exactly `W` pins the key-level boundary.
  - `test_expired_keys_are_dropped_by_activity_on_other_keys` (R5): hit `a`, advance `W`, hit `b`, then assert `list(limiter._hits) == ["b"]` with no `tracked_keys()` call. The one white-box assertion in the file: `tracked_keys()` sweeps before it counts, so only `_hits` shows whether `allow` swept. Fails at head.
  - `test_refreshed_key_does_not_shield_expired_keys` (R5): `limit=2`, `a`, +1s `b`, +8s `a`, +2.5s, `tracked_keys() == 1`. Fails at head, and fails without `move_to_end`.
  - `test_count_survives_activity_on_many_other_keys` (R6): 2000 other keys. Passes before and after; it guards against a capped cache.
  - `test_concurrent_callers_do_not_raise`: four threads, 5000 calls each on distinct keys, an injected counter clock, a short switch interval. Passes at head; fails without the lock once the sweep exists.

  No spec change: the code moves to R5 as written, R6 keeps holding, and the spec stays silent on threads (D9).
- **Reply:**

  > You're right that `_hits` only ever grew: `setdefault` added a key and nothing removed it, which also broke R5 (no state for a key with no hits in the current window). I fixed it in 1e0c71e, with expiry-based eviction rather than an LRU. An LRU with `maxsize=1024` would evict a key that still has live hits once 1024 other keys are touched, and that resets its count. With `limit=1`: one hit on `a`, then 1024 other keys, and `a` is allowed again inside the same window. That breaks R6: enough traffic on other keys, organic or induced, resets a throttled key's count.
  >
  > Instead, `_hits` is now an `OrderedDict` kept in order of each key's newest hit, and `_drop_expired_keys` removes keys from the front. It only removes a key whose newest hit has left the window, so no live state is dropped; expired keys go on the next `allow` or `tracked_keys` call, amortized O(1). Because the sweep changes the dict on every call, `allow` and `tracked_keys` now hold a lock; without it, concurrent callers hit `RuntimeError: OrderedDict mutated during iteration`. Tests: `test_idle_key_is_dropped_after_window`, `test_expired_keys_are_dropped_by_activity_on_other_keys`, `test_refreshed_key_does_not_shield_expired_keys`, `test_count_survives_activity_on_many_other_keys` (2000 other keys, the case an LRU of 1024 fails), and `test_concurrent_callers_do_not_raise`.
  >
  > The trade-off: eviction is lazy and there is no fixed cap. After any call the limiter holds only keys with a hit in the current window, so memory follows the number of keys active within one window. A hard cap would mean dropping live state or rejecting new keys, which needs a spec decision, so I've kept it out of this PR. If you want one, I'll open a ticket for it.

- **Depends on:** T1 (same lines of `allow`; the key sweep uses T1's `<=` cutoff).
- **Posted:** https://github.example.invalid/acme/ratelimit/pull/7#discussion_r9003

### T4 - `ratelimit/limiter.py:10` - rev-tom

> Hmm, is this right?

- **Thread:** `root_comment_id` 5004, `comment_count` 1
- **Classification:** Needs clarification
- **Evidence:**
  - Code: `ratelimit/limiter.py:10` is `def __init__(self, limit, window_seconds, burst=0, clock=time.monotonic):`. The comment does not say which part is in doubt.
  - Found in plan review: two lines up, inside the comment's hunk, the class docstring (`limiter.py:8`) says "Allows at most `limit` hits per key in any window of `window_seconds`." The ceiling is `limit + burst` (`limiter.py:11`; R1, `requirements.md:3`; `test_burst_raises_the_ceiling`). The docstring is wrong, and it is the likeliest meaning of a question on the line that introduces `burst`.
  - `burst=0`: R1 sets the ceiling at `limit + burst`; `test_burst_raises_the_ceiling` covers a non-zero burst, `test_allows_up_to_limit` the default.
  - `clock=time.monotonic`: a monotonic clock keeps the window from moving when the wall clock is adjusted; every test injects `FakeClock` (CLAUDE.md: tests never read the wall clock).
  - The reviewer's claim holds: cannot be judged; no claim is stated. One inaccuracy found in the hunk (the docstring).
- **Action:** the docstring fix, made under R1's action (same root cause: `burst` is undocumented). Nothing else changes until Tom answers.
- **Reply:**

  > Could you say which part you have in mind? Re-reading the lines around it, I found one thing that was wrong: the class docstring said "at most `limit` hits", which ignored `burst`. The ceiling is `limit + burst` (R1), and I corrected the docstring in c3601b5. If that is what you meant, it's done. If it was the signature itself, the two defaults look intended to me: `burst=0` means no allowance beyond `limit`, and `clock=time.monotonic` keeps the window from moving when the wall clock is adjusted and is injectable so the tests can use a fake clock. If it's something else, point me at it and I'll take a look.

- **Depends on:** R1 (the docstring fix lands in its commit).
- **Posted:** https://github.example.invalid/acme/ratelimit/pull/7#discussion_r9004

### R1 - review summary - rev-maria (CHANGES_REQUESTED)

> Close. Two things inline, and please document `burst` in the README before this merges: right now nobody reading it can tell the parameter exists.

- **Review:** `id` 7001. Answered in the one conversation comment.
- **Classification:** Agree
- **Evidence:**
  - `README.md` shows only `SlidingWindowLimiter(limit=100, window_seconds=60)`; the word `burst` does not appear.
  - Code: `burst` is a constructor parameter (`ratelimit/limiter.py:10`), added to the ceiling (`limiter.py:11`), rejected when negative (`limiter.py:38-39`). The class docstring (`limiter.py:8`) omits it.
  - Spec: R1 and R4 define it.
  - The reviewer's claim holds: yes.
- **Action (S):** add a "Burst allowance" section to `README.md`: what `burst` does (extra hits on top of `limit` within a window), its default of 0, that a negative value raises `ValueError`, and an example inside the section. Change the class docstring in `ratelimit/limiter.py` to state the ceiling as `limit + burst`.
- **Reply (conversation comment):**

  > On the review summary from rev-maria:
  >
  > > please document `burst` in the README before this merges: right now nobody reading it can tell the parameter exists.
  >
  > Done in c3601b5. The README now has a "Burst allowance" section: `burst` is the number of extra hits allowed on top of `limit` within a window, it defaults to 0, a negative value raises `ValueError`, and the section has its own example. The class docstring had the same gap (it said "at most `limit` hits") and now states the ceiling as `limit + burst`. The two inline points are answered in their threads.

- **Depends on:** nothing.
- **Posted:** https://github.example.invalid/acme/ratelimit/pull/7#issuecomment-9005

### T5 - `tests/test_limiter.py:32` - rev-tom (resolved)

> nit: this was `test_hits_expire_after_windw` in the first push

- **Thread:** `root_comment_id` 5005, `comment_count` 2, resolved by rev-tom after the author's "Fixed."
- **Evidence:** the test is named `test_hits_expire_after_window` at head (`tests/test_limiter.py:32`). The concern is not live.
- **Action:** none. No reply.

## Execution order

Every commit stages explicit paths; this plan file is never staged. `make test` passes before each commit.

Commit 1 - `78e6f66` - `fix(limiter): expire hits exactly one window old (RATE-12)`

- [x] 1. `tests/test_limiter.py`: add `test_hit_exactly_window_old_has_expired`; confirm it fails at head.
- [x] 2. `tests/test_limiter.py`: add `test_hit_just_inside_window_still_counts`.
- [x] 3. `ratelimit/limiter.py`: change the expiry comparison in `allow` to `<=`; both tests pass.

Commit 2 - `1e0c71e` - `fix(limiter): drop keys whose hits have all expired (RATE-12)`

- [x] 4. `tests/test_limiter.py`: add `test_idle_key_is_dropped_after_window`, `test_expired_keys_are_dropped_by_activity_on_other_keys` (asserts on `_hits`), and `test_refreshed_key_does_not_shield_expired_keys`; confirm all three fail.
- [x] 5. `tests/test_limiter.py`: add `test_count_survives_activity_on_many_other_keys` and `test_concurrent_callers_do_not_raise` (both pass before the change; they guard R6 and the lock).
- [x] 6. `ratelimit/limiter.py`: `OrderedDict` for `_hits` with `move_to_end` on every accepted hit, `_drop_expired_keys` called from `allow` and `tracked_keys`, a `threading.Lock` held in both, and the comment on the clock; all tests pass. Confirm `test_concurrent_callers_do_not_raise` fails with the lock removed.

Commit 3 - `c3601b5` - `docs(limiter): document the burst allowance (RATE-12)`

- [x] 7. `README.md`: add the "Burst allowance" section.
- [x] 8. `ratelimit/limiter.py`: class docstring states the ceiling as `limit + burst`.

Gates

- [x] 9. `make lint` and `make test` on `HEAD` (no formatter and no build step are configured).

## Open questions

- **T4 awaits rev-tom:** whether the docstring was what he meant, or something else on the `__init__` signature.
- **Hard memory cap (D7):** deferred, no ticket yet. Needs a spec decision on what happens at the cap, since R6 forbids dropping live state.
- **Thread-safety as a spec requirement (D9):** the eviction commit adds a lock so the sweep cannot raise under concurrent callers, but the spec is silent on threads. Whether RATE-12 should promise it is undecided; no ticket yet.
- **Not raised by a reviewer - NaN gets past R4's validation (D9):** `limit`, `burst`, or `window_seconds` of `float('nan')` constructs without error (`ratelimit/limiter.py:34-39` compare with `<= 0` / `< 0`). Disclosed in the T2 reply; deferred, no ticket yet. `float('inf')` is also accepted; whether an infinite limit is valid is a product call.
- **Not raised by a reviewer - untested clause of R4:** a negative `burst` raises `ValueError` (`ratelimit/limiter.py:38-39`) but has no test. It shares no root cause with a planned action, so it is not fixed here.

## Plan review

Codex is not installed, so two adversarial reviewers audited the plan: one the diagnosis, one the response. 15 findings, 16 after merging two duplicates and splitting one three-part finding. Each was checked against the head code.

| # | Finding | Item | Disposition | Evidence |
|---|---------|------|-------------|----------|
| F1 | The class docstring in T4's hunk says "at most `limit` hits", contradicting R1; the plan said no defect near the line | T4, R1 | Accept (reopened D5, D6) | `limiter.py:8` vs `limiter.py:11` and R1. Docstring fix joins R1's commit; T4 reply names it. |
| F2 | NaN (and inf) pass `_check_arguments`, so the T2 reply's "point me at a path around the check" has an answer | T2 | Defer (reply reworded; reopened D3) | Reproduced: `limit=nan` constructs and never rejects. No reviewer raised it and it shares no root cause with a planned action: Open questions, disclosed in the reply. |
| F3 | Theme "reading the hunk, not the method" is unsupported for T4 | Themes | Accept | T4 states no claim, and F1 found a defect in its hunk. Theme replaced by "`burst` is undocumented". |
| F4 | "Argument order matches the README" is not evidence: every call passes keywords | T4 | Accept | `README.md:8` and all six constructor calls in the tests use keywords. Clause dropped. |
| F5 | `test_expired_keys_are_dropped_by_activity_on_other_keys` cannot fail through `tracked_keys()`, which sweeps first | T3 | Accept | Mutant without the sweep in `allow` passes the black-box form and fails `len(_hits) == 1`. Test asserts on `_hits`. |
| F6 | No planned test fails without `move_to_end` | T3 | Accept | Mutant passes all planned tests and violates R5 on `a, b, a`. Added `test_refreshed_key_does_not_shield_expired_keys`. |
| F7 | The sweep makes `allow()` raise under concurrent callers; head never raises | T3 | Accept (reopened D4) | Reproduced: 20 of 20 runs raise without a lock, 0 of 20 with one. Lock and stress test added to commit 2. |
| F8 | The key-level boundary is unpinned if the idle test advances 11s | T3 | Accept | Mutant with `>=` passes at 11s and fails at exactly 10s. Test advances exactly `window_seconds`. |
| F9 | The sweep assumes a non-decreasing clock; undeclared | T3 | Accept | A backward-stepping clock drops a key with a live hit. Comment added; no behavior change. |
| F10 | T3 reply: the LRU counter-example holds only for `limit=1`; "rotating keys gets around the limit" overstates | T3 reply | Accept | 1024 is the right threshold only at `limit=1`. Reply says so and drops the rotation clause. |
| F11 | T3 reply: "runs in `allow`..., so no live state is dropped" is a non sequitur; the memory bound holds only as of the last call | T3 reply | Accept | Eviction is lazy. Reply reworded. |
| F12 | "So no empty deque is ever held" is not what replacing `setdefault` buys | T3 action | Accept | A mutant keeping `setdefault` is indistinguishable. `setdefault` stays; smaller diff. |
| F13 | Run the gates before each commit, since a late failure forces an amend that changes cited SHAs | Execution order | Reject | A gate failure is fixed in a further commit, never an amend, and SHAs are filled in only after the gates pass. `make test` already runs before each commit. |
| F14 | The execution order has no steps for pushing, filling placeholders, or posting | Execution order | Reject | The execution order covers code, test, and spec changes. Publishing is a separate step gated on the author's approval. |
| F15 | The plan file is untracked and not ignored; say "stage by path" | Execution order | Accept | `git status` shows `?? review_response_7.md`. Note added above commit 1. |
| F16 | Reply wording: R1 "example next to the basic one" vs the action; T1 "next to" reads as if one test pre-existed | R1, T1 replies | Accept | Both replies reworded to match the actions. |
