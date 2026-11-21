PR #7's review is answered: two commits are pushed, all four open threads and Maria's review summary have replies, the description is updated, and Maria is re-requested. Detail is in `/tmp/rr-eval/happy-path/repo/review_response_7.md`.

**Plan**
- 5 items answered: Agree 2, Agree with modification 1, Push back 1, Needs clarification 1. The resolved typo thread got no action.
- Ticket RATE-12: Jira context unavailable, so the spec (`specs/rate-12-limiter/requirements.md`) stood in as the statement of intended behavior.

**Review**
- The plan was reviewed by two native adversarial reviewers instead of codex, because codex was treated as not installed in this environment.
- 9 findings after merging duplicates: 9 accepted, 0 rejected, 0 deferred.
- One finding corrected the reason behind D3 (a hard cap could also be built by refusing new keys, which gives up R2, not R1/R6). I put D3 back to you; it stands, with the corrected reason in the plan and in the reply to Maria.
- The accepted findings that changed the code: `_hits` is an `OrderedDict` (a plain `dict` made eviction quadratic), the boundary test uses two hits so it exercises the per-hit comparison, and a key is dropped only when all its hits have expired.

**Changes**
- `b1f85dd` fix(limiter): expire hits and idle keys at the window boundary (RATE-12) - `ratelimit/limiter.py`, `tests/test_limiter.py`
- `47593b1` docs(readme): document the burst parameter (RATE-12) - `README.md`
- Gates on `HEAD`: `make lint` pass, `make test` pass (11 tests, 5 new). Format and build: not configured in this repo.
- No spec edit: the code was brought to what R1, R3, R5 and R6 already say.

**Published**
- Pushed `c545718..47593b1` to `origin` `feat/RATE-12-limiter` (fast-forward); the PR head is verified at `47593b1`.
- Replies: 5 posted, 0 held, 0 failed.
  - `ratelimit/limiter.py:21` (rev-maria), Agree: https://github.example.invalid/acme/ratelimit/pull/7#discussion_r9001
  - `ratelimit/limiter.py:20` (rev-maria), Agree with modification: https://github.example.invalid/acme/ratelimit/pull/7#discussion_r9002
  - `ratelimit/limiter.py:11` (rev-tom), Push back: https://github.example.invalid/acme/ratelimit/pull/7#discussion_r9004
  - `ratelimit/limiter.py:10` (rev-tom), Needs clarification: https://github.example.invalid/acme/ratelimit/pull/7#discussion_r9005
  - Review summary (rev-maria), Agree, as one conversation comment: https://github.example.invalid/acme/ratelimit/pull/7#issuecomment-9003
- PR description: a "Changes in response to review" block was appended; the original text is untouched.
- Review re-requested from rev-maria. rev-tom only commented, so he was not re-requested.
- No thread was resolved; that is left to the reviewers.

**Open**
- rev-tom, `limiter.py:10`: waiting for him to say what "is this right?" refers to.
- rev-tom, `limiter.py:11`: I offered to move the validation to the top of `__init__` if the ordering is what bothered him. Not done.
- rev-maria, `limiter.py:20`: she asked for an LRU and got expiry-based eviction, so she may push back. I offered a follow-up ticket for a hard cap on tracked keys; none was created.
- Remaining risk: memory is still proportional to the keys active inside one window, and eviction is lazy (it runs inside `allow()` and `tracked_keys()`, not on a timer).
- Found but not raised by any reviewer, left alone: a non-numeric `limit` raises `TypeError` instead of the `ValueError` R4 asks for, `nan`/`inf` pass validation, and a fractional `limit` such as 1.5 allows 2 hits. These are candidates for a follow-up.
- `review_response_7.md` is untracked in the repo and was not committed.
