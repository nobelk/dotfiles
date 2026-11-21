#!/usr/bin/env python3
"""Build an offline sandbox for testing the review-response skill.

  build_sandbox.py <case-dir> [--on-main]

Creates <case-dir>/{repo,remote.git,bin/gh,gh-state/state.json}: a small Python
project on a feature branch with an open fake PR carrying review comments, a bare
remote to push to, and a fake `gh` that serves the PR and records every write.
"""

import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BRANCH = "feat/RATE-12-limiter"

FILES = {
    ".gitignore": "__pycache__/\n",
    "Makefile": (
        ".PHONY: lint test\n\n"
        "lint:\n\tpython3 -m compileall -q ratelimit tests\n\n"
        "test:\n\tpython3 -m unittest discover -s tests\n"
    ),
    "CLAUDE.md": (
        "# ratelimit\n\n"
        "- Gates: `make lint` and `make test`. There is no formatter and no build step.\n"
        "- Tests use `unittest` with an injected fake clock; never read the wall clock in a test.\n"
        "- Commits follow Conventional Commits with the ticket key in parentheses at the end, e.g. `fix(limiter): reject zero window (RATE-12)`.\n"
        "- Behavior is specified in `specs/<ticket>-<name>/requirements.md`; a behavior change updates the spec in the same commit.\n"
    ),
    "README.md": (
        "# ratelimit\n\n"
        "A sliding-window rate limiter.\n\n"
        "```python\n"
        "from ratelimit.limiter import SlidingWindowLimiter\n\n"
        "limiter = SlidingWindowLimiter(limit=100, window_seconds=60)\n"
        "if not limiter.allow(client_id):\n"
        "    reject()\n"
        "```\n"
    ),
}

FEATURE_FILES = {
    "specs/rate-12-limiter/requirements.md": (
        "# RATE-12 Sliding-window limiter: requirements\n\n"
        "- R1. `allow(key)` returns True for at most `limit + burst` hits per key within any window.\n"
        "- R2. Keys are limited independently.\n"
        "- R3. A hit at time `t` counts against the half-open window `(now - W, now]`. A hit exactly `W` seconds old no longer counts.\n"
        "- R4. `limit` and `window_seconds` must be positive and `burst` must not be negative; anything else raises `ValueError` at construction.\n"
        "- R5. The limiter holds no state for a key that has no hits in the current window.\n"
        "- R6. A key's count is never reset by activity on other keys.\n"
    ),
    "ratelimit/__init__.py": "",
    "ratelimit/limiter.py": '''"""Sliding-window rate limiter."""

import time
from collections import deque


class SlidingWindowLimiter:
    """Allows at most `limit` hits per key in any window of `window_seconds`."""

    def __init__(self, limit, window_seconds, burst=0, clock=time.monotonic):
        self._limit = limit + burst
        self._window = window_seconds
        self._clock = clock
        self._hits = {}
        self._check_arguments(limit, window_seconds, burst)

    def allow(self, key):
        """Record a hit for `key` and report whether it is within the limit."""
        now = self._clock()
        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] < now - self._window:
            hits.popleft()
        if len(hits) >= self._limit:
            return False
        hits.append(now)
        return True

    def tracked_keys(self):
        """Number of keys the limiter currently holds state for."""
        return len(self._hits)

    @staticmethod
    def _check_arguments(limit, window_seconds, burst):
        if limit <= 0:
            raise ValueError(f"limit must be positive, got {limit}")
        if window_seconds <= 0:
            raise ValueError(f"window_seconds must be positive, got {window_seconds}")
        if burst < 0:
            raise ValueError(f"burst must not be negative, got {burst}")
''',
    "tests/__init__.py": "",
    "tests/test_limiter.py": '''import unittest

from ratelimit.limiter import SlidingWindowLimiter


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class SlidingWindowLimiterTest(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()

    def test_allows_up_to_limit(self):
        limiter = SlidingWindowLimiter(limit=2, window_seconds=10, clock=self.clock)
        self.assertTrue(limiter.allow("a"))
        self.assertTrue(limiter.allow("a"))
        self.assertFalse(limiter.allow("a"))

    def test_keys_are_independent(self):
        limiter = SlidingWindowLimiter(limit=1, window_seconds=10, clock=self.clock)
        self.assertTrue(limiter.allow("a"))
        self.assertTrue(limiter.allow("b"))

    def test_hits_expire_after_window(self):
        limiter = SlidingWindowLimiter(limit=1, window_seconds=10, clock=self.clock)
        self.assertTrue(limiter.allow("a"))
        self.clock.advance(11)
        self.assertTrue(limiter.allow("a"))

    def test_burst_raises_the_ceiling(self):
        limiter = SlidingWindowLimiter(limit=1, window_seconds=10, burst=1, clock=self.clock)
        self.assertTrue(limiter.allow("a"))
        self.assertTrue(limiter.allow("a"))
        self.assertFalse(limiter.allow("a"))

    def test_rejects_non_positive_limit(self):
        for limit in (0, -1):
            with self.assertRaises(ValueError):
                SlidingWindowLimiter(limit=limit, window_seconds=10, clock=self.clock)

    def test_rejects_non_positive_window(self):
        with self.assertRaises(ValueError):
            SlidingWindowLimiter(limit=1, window_seconds=0, clock=self.clock)


if __name__ == "__main__":
    unittest.main()
''',
}


def run(args, cwd):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


def write(root, files):
    for rel, text in files.items():
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)


def line_of(text, needle):
    for number, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            return number
    raise SystemExit(f"needle not found: {needle}")


def hunk(text, line, before=6):
    lines = text.splitlines()
    start = max(1, line - before)
    body = "\n".join("+" + l for l in lines[start - 1:line])
    return f"@@ -0,0 +{start},{line - start + 1} @@\n{body}"


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    case = os.path.abspath(sys.argv[1])
    on_main = "--on-main" in sys.argv
    if os.path.exists(case):
        shutil.rmtree(case)
    repo, remote = os.path.join(case, "repo"), os.path.join(case, "remote.git")
    os.makedirs(repo)
    os.makedirs(os.path.join(case, "bin"))
    os.makedirs(os.path.join(case, "gh-state"))

    run(["git", "init", "--bare", "-b", "main", remote], case)
    run(["git", "init", "-b", "main", repo], case)
    for key, value in (("user.name", "Dev Author"), ("user.email", "dev-author@example.invalid"),
                       ("commit.gpgsign", "false"), ("core.hooksPath", "/dev/null")):
        run(["git", "config", key, value], repo)
    write(repo, FILES)
    run(["git", "add", "-A"], repo)
    run(["git", "commit", "-m", "chore: scaffold ratelimit package"], repo)
    run(["git", "remote", "add", "origin", remote], repo)
    run(["git", "push", "-u", "origin", "main"], repo)
    run(["git", "checkout", "-b", BRANCH], repo)
    write(repo, FEATURE_FILES)
    run(["git", "add", "-A"], repo)
    run(["git", "commit", "-m", "feat(limiter): add sliding-window limiter (RATE-12)"], repo)
    run(["git", "push", "-u", "origin", BRANCH], repo)
    oid = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
    if on_main:
        run(["git", "checkout", "main"], repo)

    src = FEATURE_FILES["ratelimit/limiter.py"]
    tests = FEATURE_FILES["tests/test_limiter.py"]

    def thread(first_id, path, text, needle, comments, resolved=False, resolved_by=None):
        line = line_of(text, needle)
        return {"path": path, "line": line, "diff_hunk": hunk(text, line), "resolved": resolved,
                "resolved_by": resolved_by,
                "comments": [{"id": first_id + i, "author": a, "body": b} for i, (a, b) in enumerate(comments)]}

    state = {
        "host": "github.example.invalid", "owner": "acme", "repo": "ratelimit", "viewer": "dev-author", "next_id": 9000,
        "pr": {
            "number": 7, "title": "RATE-12: sliding-window rate limiter", "state": "OPEN", "author": "dev-author",
            "headRefName": BRANCH, "baseRefName": "main",
            "body": "Adds `SlidingWindowLimiter`, a per-key sliding-window rate limiter with an optional burst allowance.\n\n"
                    "Implements RATE-12. Spec: `specs/rate-12-limiter/requirements.md`.\n",
            "commits": [{"oid": oid, "message": "feat(limiter): add sliding-window limiter (RATE-12)"}],
            "files": sorted(FEATURE_FILES),
        },
        "threads": [
            thread(5001, "ratelimit/limiter.py", src, "while hits and hits[0] < now - self._window", [
                ("rev-maria", "A hit that is exactly `window_seconds` old should already have expired: R3 in the spec says the "
                              "window is half-open, `(now - W, now]`. This `<` keeps that hit for one more tick. Can you fix "
                              "it and add a boundary test?")]),
            thread(5002, "ratelimit/limiter.py", src, "self._limit = limit + burst", [
                ("rev-tom", "`limit` is never validated. Zero or a negative value gives a limiter that silently rejects "
                            "everything. Please raise on a non-positive limit.")]),
            thread(5003, "ratelimit/limiter.py", src, "self._hits.setdefault(key, deque())", [
                ("rev-maria", "`_hits` grows without bound: once a key is seen it is never removed. Wrap this in an LRU with "
                              "`maxsize=1024` so memory stays capped.")]),
            thread(5004, "ratelimit/limiter.py", src, "def __init__(self, limit, window_seconds, burst=0", [
                ("rev-tom", "Hmm, is this right?")]),
            thread(5005, "tests/test_limiter.py", tests, "def test_hits_expire_after_window", [
                ("rev-tom", "nit: this was `test_hits_expire_after_windw` in the first push"),
                ("dev-author", "Fixed.")], resolved=True, resolved_by="rev-tom"),
        ],
        "reviews": [
            {"id": 7001, "user": {"login": "rev-maria", "type": "User"}, "state": "CHANGES_REQUESTED", "commit_id": oid,
             "submitted_at": "2026-11-19T10:05:00Z",
             "html_url": "https://github.example.invalid/acme/ratelimit/pull/7#pullrequestreview-7001",
             "body": "Close. Two things inline, and please document `burst` in the README before this merges: right now "
                     "nobody reading it can tell the parameter exists."},
            {"id": 7002, "user": {"login": "rev-tom", "type": "User"}, "state": "COMMENTED", "commit_id": oid,
             "submitted_at": "2026-11-19T11:30:00Z",
             "html_url": "https://github.example.invalid/acme/ratelimit/pull/7#pullrequestreview-7002", "body": ""},
        ],
        "conversation": [
            {"id": 8001, "user": {"login": "dev-author", "type": "User"}, "body": "Ready for review, thanks!",
             "created_at": "2026-11-18T09:00:00Z", "html_url": "https://github.example.invalid/acme/ratelimit/pull/7#issuecomment-8001"},
            {"id": 8002, "user": {"login": "ci-bot[bot]", "type": "Bot"}, "body": "Build #214 passed. Coverage: 93.1%",
             "created_at": "2026-11-18T09:04:00Z", "html_url": "https://github.example.invalid/acme/ratelimit/pull/7#issuecomment-8002"},
        ],
        "review_requests": [],
    }
    with open(os.path.join(case, "gh-state", "state.json"), "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
    shutil.copy(os.path.join(case, "gh-state", "state.json"), os.path.join(case, "gh-state", "state.initial.json"))
    gh = os.path.join(case, "bin", "gh")
    shutil.copy(os.path.join(HERE, "fake_gh.py"), gh)
    os.chmod(gh, 0o755)
    print(json.dumps({"case": case, "repo": repo, "head_oid": oid, "branch": "main" if on_main else BRANCH,
                      "pr_url": "https://github.example.invalid/acme/ratelimit/pull/7"}, indent=2))


if __name__ == "__main__":
    main()
