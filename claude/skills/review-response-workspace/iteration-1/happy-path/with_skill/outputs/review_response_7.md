# Review response - PR #7

## Header

- **PR**: https://github.example.invalid/acme/ratelimit/pull/7 - "RATE-12: sliding-window rate limiter"
- **Author**: dev-author (replies post as `dev-author`)
- **Branches**: `feat/RATE-12-limiter` -> `main`; snapshot head `c54571802eb02c2bd420503c9682ac9dc021a401`
- **Ticket**: RATE-12 (from the branch name) - Jira context unavailable (no Jira connection in this session). Intended behavior is taken from `specs/rate-12-limiter/requirements.md` (R1-R6).
- **Date**: 2026-11-20
- **Mode**: Execute
- **Items**: 6 total / 5 unresolved (4 threads + 1 review summary that asks for something) / 1 resolved, 0 outdated
- **Classification**: Agree 2, Agree with modification 1, Push back 1, Needs clarification 1
- **Not items**: rev-tom's review 7002 (empty body), conversation 8001 (my own comment), conversation 8002 (CI bot)

## Summary table

| # | Anchor | Classification | Size | Priority |
|---|--------|----------------|------|----------|
| 5001 | `ratelimit/limiter.py:21` - rev-maria - "A hit that is exactly `window_seconds` old should already have expired..." | Agree | S | P1 |
| 5003 | `ratelimit/limiter.py:20` - rev-maria - "`_hits` grows without bound: once a key is seen it is never removed..." | Agree with modification | M | P1 |
| 7001 | review summary - rev-maria (changes requested) - "...please document `burst` in the README before this merges..." | Agree | S | P1 |
| 5002 | `ratelimit/limiter.py:11` - rev-tom - "`limit` is never validated..." | Push back | - | P2 |
| 5004 | `ratelimit/limiter.py:10` - rev-tom - "Hmm, is this right?" | Needs clarification | - | P2 |
| 5005 | `tests/test_limiter.py:32` - rev-tom - "nit: this was `test_hits_expire_after_windw` in the first push" | Resolved - no action | - | - |

P1 = raised by the reviewer who requested changes, blocks the merge. P2 = reply only.

## Settled decisions

- **D1** - Thread 5002 (rev-tom, `limit` validation): push back. Cite `ratelimit/limiter.py:15` and `:34-35`, `test_rejects_non_positive_limit`, and R4. No code change. The reply offers to move the validation to the top of `__init__` if he wants it.
- **D2** - Thread 5003 (rev-maria, `_hits` growth): agree with modification. Expiry-based eviction of idle keys (ordered by most recent accepted hit, applied in `allow()` and `tracked_keys()`), not an LRU, because an LRU breaks R1 and R6 and still misses R5. Done in this PR. No spec edit.
- **D3** - A hard cap on tracked keys is out of scope for this PR: it needs a product answer and a spec change either way (R1/R6 if it evicts live keys, R2 if it refuses new ones). Offered to Maria as a follow-up ticket. No ticket is created by this run. *(Reopened and kept after the plan review corrected its reason: finding F8.)*
- **D4** - Thread 5004 (rev-tom, "Hmm, is this right?"): needs clarification. Ask which of the `burst` default, the `clock` default, or the parameter order he means; no code change on a guess. The thread stays open.
- **D5** - The class docstring ("at most `limit` hits") is corrected to `limit + burst` as part of documenting `burst`, and mentioned in the 5004 reply and the summary reply.
- **D6** - Jira is unreachable, so the spec stands as the statement of intended behavior and this plan says "Jira context unavailable" where ticket evidence would apply.
- **D7** - Execute mode: implement, run `make lint` and `make test`, commit on top of `c545718`, then one publish round before anything is pushed or posted.

## Cross-cutting themes

- **T1 - Expiry in `allow()` does not implement the spec (5001, 5003).** Both comments land on the same four lines. Hits expire one tick late (R3) and keys never expire at all (R5). One action: rewrite the expiry so a hit expires at exactly `W` and a key is dropped once its newest hit has expired. One commit (`ratelimit/limiter.py`, `tests/test_limiter.py`).
- **T2 - `burst` is invisible to a reader (7001, and the docstring candidate under 5004).** The README never mentions it and the class docstring states the ceiling without it. One action: document `burst` in the README and correct the docstring. The README goes in its own commit; the docstring line lives in `ratelimit/limiter.py`, so it rides in the T1 commit (see Execution order).

## Per-item detail

### 5001 - `ratelimit/limiter.py:21` - rev-maria

> A hit that is exactly `window_seconds` old should already have expired: R3 in the spec says the window is half-open, `(now - W, now]`. This `<` keeps that hit for one more tick. Can you fix it and add a boundary test?

- **root_comment_id**: 5001
- **comment_count**: 1
- **Classification**: Agree
- **Evidence**:
  - Code: `ratelimit/limiter.py:21` is `while hits and hits[0] < now - self._window:`. A hit with `hits[0] == now - W` is not popped and still counts at line 23. Probe: `limit=1, window_seconds=10`, hit at t=1000, `allow` at t=1010 returns False.
  - Tests: untested. `test_hits_expire_after_window` (`tests/test_limiter.py:32-36`) advances 11 on a window of 10, so it passes under both `<` and `<=`.
  - Spec: R3 (`specs/rate-12-limiter/requirements.md:5`): "A hit at time `t` counts against the half-open window `(now - W, now]`. A hit exactly `W` seconds old no longer counts."
  - Ticket: Jira context unavailable.
  - The reviewer's claim holds: yes.
- **Action** (S): in `ratelimit/limiter.py`, expire a hit when it is `<= now - W` (one `_expire` helper holds the comparison, shared with 5003). Test first: add `test_hit_exactly_one_window_old_has_expired` to `tests/test_limiter.py` with `limit=2, window_seconds=10`: hit, `advance(5)`, hit, `advance(5)`, then one call allowed and the next rejected. Two hits are needed so the key still has a live hit and the per-hit comparison is what the test exercises (with `limit=1` the whole key would be dropped as idle first: finding F2). No spec update: the code is brought to what R3 already says.
- **Reply**:

  > You're right. R3 defines the window as `(now - W, now]`, and `hits[0] < now - self._window` kept a hit that was exactly `W` old: with `limit=1, window_seconds=10`, a second call at exactly t+10 was rejected.
  >
  > Changed the comparison to `<=` in b1f85dd and added `test_hit_exactly_one_window_old_has_expired`: on the fake clock, a hit is exactly `window_seconds` old when the next call arrives and must no longer count. It fails on the old comparison. The existing `test_hits_expire_after_window` advanced 11s on a 10s window, which is why it never caught this.

- **Dependencies**: shares the expiry code with 5003 (T1); implemented together.
- **Posted**: https://github.example.invalid/acme/ratelimit/pull/7#discussion_r9001

### 5003 - `ratelimit/limiter.py:20` - rev-maria

> `_hits` grows without bound: once a key is seen it is never removed. Wrap this in an LRU with `maxsize=1024` so memory stays capped.

- **root_comment_id**: 5003
- **comment_count**: 1
- **Classification**: Agree with modification (D2, D3)
- **Evidence**:
  - Code: `ratelimit/limiter.py:20` is `hits = self._hits.setdefault(key, deque())`; nothing in the file deletes from `self._hits`. Lines 21-22 prune only the deque of the key being called. Probe: 5,000 distinct keys give `tracked_keys() == 5000`, still 5000 after 1,000 s on a 10 s window. Per-key memory is bounded (a rejected hit is not appended, so a deque holds at most `limit + burst` timestamps); only the key count grows.
  - LRU probe: `limit=1`, key "a" hit once, 1,024 other keys touched at the same instant, "a" evicted, the next `allow("a")` at that instant returns True: two allowed hits against a limit of 1.
  - Tests: untested. Nothing calls `tracked_keys()`, nothing asserts that state is dropped after expiry, and `test_keys_are_independent` (`tests/test_limiter.py:27-30`) only checks that two keys each get a first hit.
  - Spec: R5 (`requirements.md:7`): "The limiter holds no state for a key that has no hits in the current window." - violated today. R6 (`requirements.md:8`): "A key's count is never reset by activity on other keys." and R1 (`requirements.md:3`): "`allow(key)` returns True for at most `limit + burst` hits per key within any window." - both broken by evicting a live key. The spec has no memory cap, key-count cap, or eviction policy.
  - Repo rule: `CLAUDE.md:6` - "a behavior change updates the spec in the same commit", so an LRU would mean rewriting R1 and R6.
  - Ticket: Jira context unavailable.
  - The reviewer's claim holds: partially. The growth is real; the proposed remedy contradicts R1 and R6 and still does not meet R5.
- **Action** (M): in `ratelimit/limiter.py`:
  - Make `_hits` a `collections.OrderedDict` kept in order of each key's most recent accepted hit: `move_to_end(key)` when a hit is recorded. A plain `dict` is not enough: finding its oldest key rescans deleted slots, which makes draining n idle keys quadratic (finding F1).
  - Add a private `_drop_idle_keys(now)`: take the oldest key, expire its hits with the same `_expire` rule as 5001, delete the key if no hit is left and repeat, stop at the first key that still has a live hit. Dropping a key only when its hits are all gone keeps today's fail-closed behavior if an injected clock ever steps back (finding F9); the ordering itself assumes a non-decreasing clock, which `time.monotonic` guarantees.
  - Call `_drop_idle_keys` from `allow()` before the lookup and from `tracked_keys()`. A key is inserted only when a hit is accepted. Amortized O(1) per call: each hit and each key is removed once.
  - Tests first, in `tests/test_limiter.py`, all on the fake clock:
    - `test_state_is_dropped_once_a_key_has_no_hits_in_the_window` (R5): `limit=1`; a hit, a rejected hit mid-window, still tracked; at exactly `W` after the accepted hit, `tracked_keys() == 0`. Fails at head.
    - `test_idle_key_is_dropped_while_a_busier_key_stays` (R5, pins the ordering): `limit=5`; "a" at t, "b" at t+1, "a" at t+9; at t+11 `tracked_keys() == 1`. Fails at head.
    - `test_key_with_a_live_hit_survives_eviction_of_idle_keys` (R1 under eviction): `limit=2`; "a" at t and t+6; at t+11 hit "b", then "a" is allowed once and rejected once. Passes at head; a guard.
    - `test_activity_on_other_keys_does_not_reset_a_key` (R6): `limit=1`; "a" hit, 2,000 other keys hit, "a" still rejected. Passes at head; a guard against the rejected LRU remedy.
  - Not observable through the public API: that `allow()` itself evicts (as opposed to `tracked_keys()`), since `tracked_keys()` evicts before it counts. No test asserts it.
  - No spec update: R1, R5, and R6 already state the behavior.
- **Scope**: a hard cap on tracked keys needs a product answer and a spec change either way (R1/R6 if it evicts live keys, R2 if it refuses new keys), so it belongs in a follow-up ticket (D3). Not created by this run.
- **Reply**:

  > The growth is real, and it is also a spec violation: R5 says the limiter holds no state for a key with no hits in the current window, and nothing ever removed a key from `_hits`. I fixed it, but not with an LRU.
  >
  > Evicting by count would drop a key that still has live hits as soon as 1,024 other keys show up, and that key's next call would be allowed again. That resets a key's count through activity on other keys (R6) and lets it exceed `limit + burst` inside one window (R1); a caller rotating keys could use it to get around the limit. A cap of 1,024 would also still hold expired keys, so R5 would stay unmet.
  >
  > What I did instead in b1f85dd: `_hits` is now an `OrderedDict` kept in order of each key's most recent accepted hit, and `allow()` and `tracked_keys()` drop keys from the old end once their last hit has left the window. That is amortized O(1) per call. Eviction is lazy (there is no timer): after any `allow()` or `tracked_keys()` call, the tracked keys are exactly those with a hit in the current window. Tests: `test_state_is_dropped_once_a_key_has_no_hits_in_the_window`, `test_idle_key_is_dropped_while_a_busier_key_stays`, `test_key_with_a_live_hit_survives_eviction_of_idle_keys`, and `test_activity_on_other_keys_does_not_reset_a_key` (2,000 other keys, the first key stays limited).
  >
  > Memory is still proportional to the number of distinct keys active inside one window; R1, R2 and R6 together make that unavoidable. A hard cap on top needs a product answer and a spec change either way: evicting live keys gives up R1/R6, and refusing new keys when the table is full gives up R2. I'd rather take that as a follow-up ticket than fold it in here. Tell me if you want one opened.

- **Dependencies**: shares the expiry code with 5001 (T1); both go through the one `_expire` helper, so hits and keys use the same boundary (`<=`).
- **Posted**: https://github.example.invalid/acme/ratelimit/pull/7#discussion_r9002

### 7001 - review summary - rev-maria (CHANGES_REQUESTED)

> Close. Two things inline, and please document `burst` in the README before this merges: right now nobody reading it can tell the parameter exists.

- **root_comment_id**: none (review summary 7001; answered in the single conversation comment)
- **comment_count**: n/a
- **Classification**: Agree
- **Evidence**:
  - Code: `README.md` has no occurrence of "burst"; its only example is `README.md:8`. `burst` is an optional parameter, default 0 (`ratelimit/limiter.py:10`), added to `limit` once at construction (`limiter.py:11`), and the sum is the per-key ceiling checked at `limiter.py:23`. It is a flat increase in every window, not a refilling allowance: `limit=1, burst=1` gives allow, allow, reject in each window. Negative `burst` raises `ValueError` (`limiter.py:38-39`); `limit` must be positive on its own (`limit=0, burst=5` raises).
  - Tests: `test_burst_raises_the_ceiling` (`tests/test_limiter.py:38-42`).
  - Spec: R1 ("at most `limit + burst` hits per key within any window"), R4 ("`burst` must not be negative").
  - The class docstring (`limiter.py:8`) says "at most `limit` hits", which contradicts R1 when `burst > 0`.
  - Ticket: Jira context unavailable.
  - The reviewer's claim holds: yes. Her "two things inline" are 5001 and 5003.
- **Action** (S): add a `burst` section to `README.md` and correct the class docstring in `ratelimit/limiter.py` to `limit + burst` (D5). The README section states, because the reply promises each: the ceiling is `limit + burst` in every window; it is a flat allowance, not a bucket that refills; the default is 0; a negative `burst` raises `ValueError`; `limit` must be positive on its own; and an example placed after the existing one. Documentation only: no test, no spec update.
- **Reply** (conversation comment):

  > @rev-maria, on your review:
  >
  > > please document `burst` in the README before this merges: right now nobody reading it can tell the parameter exists.
  >
  > Done in 47593b1. The README now has a section on `burst`: it raises the per-key ceiling to `limit + burst` in every window (a flat allowance, not a bucket that refills), it defaults to 0, it must not be negative, and `limit` still has to be positive on its own. There is an example after the existing one. The class docstring said "at most `limit` hits", which was wrong for `burst > 0`; corrected in b1f85dd.
  >
  > > Two things inline
  >
  > Both answered in their threads. The window boundary is fixed as you asked. For `_hits` I fixed the growth with expiry-based eviction instead of an LRU; the thread has the reasons.

- **Dependencies**: the docstring edit rides in the T1 commit because it is in `ratelimit/limiter.py`.
- **Posted**: https://github.example.invalid/acme/ratelimit/pull/7#issuecomment-9003

### 5002 - `ratelimit/limiter.py:11` - rev-tom

> `limit` is never validated. Zero or a negative value gives a limiter that silently rejects everything. Please raise on a non-positive limit.

- **root_comment_id**: 5002
- **comment_count**: 1
- **Classification**: Push back (D1)
- **Evidence**:
  - Code: `ratelimit/limiter.py:15` calls `self._check_arguments(limit, window_seconds, burst)`; `limiter.py:34-35` is `if limit <= 0: raise ValueError(f"limit must be positive, got {limit}")`. The check sits four lines below his hunk (which ends at line 11) and runs after the assignment on line 11. Probes: `limit=0`, `limit=-1`, and `limit=0, burst=5` all raise `ValueError`. No constructed limiter rejects everything.
  - Tests: `test_rejects_non_positive_limit` (`tests/test_limiter.py:44-47`) loops over `(0, -1)` with `assertRaises(ValueError)` and passes.
  - Spec: R4 (`requirements.md:6`): "`limit` and `window_seconds` must be positive and `burst` must not be negative; anything else raises `ValueError` at construction."
  - Ticket: Jira context unavailable.
  - The reviewer's claim holds: no.
- **Action**: no code change. The reply cites code by name, not line number, because the line numbers above describe `c545718` and shift once the T1 commit lands (finding F4).
- **Reply**:

  > I think this is already covered, though the layout makes it easy to miss. The last statement of `__init__`, just below this hunk, is `self._check_arguments(limit, window_seconds, burst)`, and `_check_arguments` raises `ValueError("limit must be positive, got ...")` when `limit <= 0`. `test_rejects_non_positive_limit` in `tests/test_limiter.py` constructs with 0 and -1 and asserts the `ValueError`, which is R4 in the spec. The check uses the raw `limit`, so `limit=0, burst=5` raises too.
  >
  > So a limiter that rejects everything can't be constructed, and I've left this as is. If what bothered you is the ordering (`self._limit = limit + burst` is assigned before the check runs), tell me and I'll move the check to the top of `__init__`.

- **Dependencies**: none.
- **Posted**: https://github.example.invalid/acme/ratelimit/pull/7#discussion_r9004

### 5004 - `ratelimit/limiter.py:10` - rev-tom

> Hmm, is this right?

- **root_comment_id**: 5004
- **comment_count**: 1
- **Classification**: Needs clarification (D4)
- **Evidence**:
  - Code: `ratelimit/limiter.py:10` is `def __init__(self, limit, window_seconds, burst=0, clock=time.monotonic):`. The hunk covers lines 4-10. Candidates:
    - `burst=0` default: right. `limiter.py:11` makes the ceiling plain `limit`; R1 and R4 agree; `test_allows_up_to_limit` (`tests/test_limiter.py:21-25`) omits `burst`.
    - `clock=time.monotonic` default: no spec coverage. Monotonic, so the window is not affected by wall-clock adjustments; every test injects the fake clock as `CLAUDE.md:4` requires. Nothing shows it wrong.
    - Parameter names and order: match the spec's terms; all callers use keywords. Nothing shows it wrong.
    - Class docstring (`limiter.py:8`): wrong for `burst > 0` ("at most `limit` hits" against R1's `limit + burst`).
  - Ticket: Jira context unavailable.
  - The reviewer's claim holds: not determinable. The comment names no subject.
- **Action**: no code change for this thread. (The docstring is corrected under 7001 / T2.)
- **Reply**:

  > Could you say which part you mean? The comment is anchored on the `__init__` signature and I can see three candidates: the `burst=0` default, `clock=time.monotonic` as the default clock, or the parameter order.
  >
  > What I checked: `burst=0` leaves the ceiling at plain `limit`, which is what R1 and `test_allows_up_to_limit` expect, and the monotonic default keeps the window unaffected by wall-clock adjustments (the tests inject a fake clock). The one thing I found wrong in this hunk is the class docstring, which said "at most `limit` hits" while the ceiling is `limit + burst`; that is corrected in b1f85dd.
  >
  > If it was something else, point me at it and I'll look.

- **Dependencies**: cites the T1 commit for the docstring.
- **Posted**: https://github.example.invalid/acme/ratelimit/pull/7#discussion_r9005

### 5005 - `tests/test_limiter.py:32` - rev-tom (resolved by rev-tom)

> nit: this was `test_hits_expire_after_windw` in the first push

- **root_comment_id**: 5005
- **comment_count**: 2
- **Classification**: none - resolved; listed for completeness.
- **Evidence**: `tests/test_limiter.py:32` is `def test_hits_expire_after_window(self):`; no occurrence of `windw` in the tree or history. The concern is not live at head.
- **Action**: no code change. No reply.
- **Posted**: n/a

## Execution order

1. [x] `tests/test_limiter.py`: add `test_hit_exactly_one_window_old_has_expired` (5001). Confirm it fails at head.
2. [x] `tests/test_limiter.py`: add the four 5003 tests. Confirm `test_state_is_dropped_once_a_key_has_no_hits_in_the_window` and `test_idle_key_is_dropped_while_a_busier_key_stays` fail at head; `test_key_with_a_live_hit_survives_eviction_of_idle_keys` and `test_activity_on_other_keys_does_not_reset_a_key` are guards and pass at head.
3. [x] `ratelimit/limiter.py`: `_expire` with `<=` (5001); `_hits` as an `OrderedDict` with `move_to_end` on an accepted hit, `_drop_idle_keys(now)` called from `allow()` and `tracked_keys()` (5003); class docstring corrected to `limit + burst` (7001, D5).
4. [x] `README.md`: add the `burst` section with every point listed in the 7001 action.
5. [x] Gates: `make lint`, `make test` (the only gates `CLAUDE.md` defines; no formatter, no build step).
6. [x] Commit 1, `fix(limiter): expire hits and idle keys at the window boundary (RATE-12)`: `ratelimit/limiter.py`, `tests/test_limiter.py` (T1 plus the docstring line). Commit 2, `docs(readme): document the burst parameter (RATE-12)`: `README.md` (T2). The two commits have disjoint files.
7. [x] In the replies above, replace `<sha-limiter>` with commit 1 (`b1f85dd`) and `<sha-readme>` with commit 2 (`47593b1`).

No spec change: every action brings the code to what R1, R3, R5, and R6 already state.

## Plan review

Reviewed by two native adversarial reviewers (codex was treated as not installed in this environment). 9 findings after merging duplicates: 9 accepted, 0 rejected, 0 deferred.

| # | Finding | Disposition | Applied as |
|---|---------|-------------|------------|
| F1 | "Amortized O(1)" is false on a plain `dict` | Accept | 5003 action names `OrderedDict` |
| F2 | The `limit=1` boundary test stops exercising the per-hit comparison | Accept | 5001 test uses `limit=2`, hits at t and t+5 |
| F3 | 5003 tests do not pin the ordering step or the live-hit guard | Accept | Two tests added; unobservable part recorded |
| F4 | Line citations in the 5002 reply shift after the fix | Accept | Replies cite code by name |
| F5 | `<sha>` ambiguous across two commits | Accept | `<sha-limiter>` / `<sha-readme>` |
| F6 | 5003 reply overstates a lazy design | Accept | Reply says eviction is lazy and when the state is exact |
| F7 | Checklist lacks commit subjects and promised README content | Accept | Steps 4 and 6, 7001 action |
| F8 | WRONG FACT (D3, partial): a cap need not change R1/R6; refusing new keys gives up R2 | Accept; D3 reopened and kept | D3, 5003 scope and reply reworded |
| F9 | Dropping a key on its newest hit alone fails open if the clock steps back | Accept | `_drop_idle_keys` expires hits first, drops only an empty key |

## Open questions

- **Awaiting rev-tom (5004)**: which part of the `__init__` signature "is this right?" refers to.
- **Awaiting rev-tom (5002)**: whether he wants the validation moved to the top of `__init__` (offered, not done).
- **Awaiting rev-maria (5003)**: whether to open a follow-up ticket for a hard cap on tracked keys (D3). Not created: Jira is unreachable from this session.
- **Not raised by any reviewer, left alone** (outside this review's scope; candidates for a follow-up): non-numeric `limit` raises `TypeError` from `ratelimit/limiter.py:11` before the `ValueError` check runs (R4 says "anything else raises `ValueError`"); `nan`/`inf` pass validation; a fractional `limit` such as 1.5 allows 2 hits; negative `window_seconds` and negative `burst` have no tests.
