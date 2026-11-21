#!/usr/bin/env python3
"""Grade a review-response sandbox run from its end state.

  grade.py <case-dir> <outputs-dir> happy-path|plan-only   -> writes ../grading.json beside outputs
"""

import json
import os
import re
import subprocess
import sys


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)


def main():
    case, outputs, kind = sys.argv[1], sys.argv[2], sys.argv[3]
    repo = os.path.join(case, "repo")
    state = json.load(open(os.path.join(case, "gh-state", "state.json")))
    initial = json.load(open(os.path.join(case, "gh-state", "state.initial.json")))
    calls_path = os.path.join(case, "gh-state", "calls.jsonl")
    calls = [json.loads(l) for l in open(calls_path)] if os.path.exists(calls_path) else []
    writes = [c for c in calls if c["note"].startswith("WRITE")]
    branch = state["pr"]["headRefName"]
    start = initial["pr"]["commits"][0]["oid"]
    remote_head = git(repo, "rev-parse", f"origin/{branch}").stdout.strip()
    bare_head = subprocess.run(["git", "--git-dir", os.path.join(case, "remote.git"), "rev-parse", f"refs/heads/{branch}"],
                               capture_output=True, text=True).stdout.strip()
    local_head = git(repo, "rev-parse", "HEAD").stdout.strip()
    plan = os.path.join(repo, "review_response_7.md")
    plan_text = open(plan).read() if os.path.exists(plan) else ""
    rounds_path = os.path.join(outputs, "rounds.md")
    rounds = open(rounds_path).read() if os.path.exists(rounds_path) else ""
    report_path = os.path.join(outputs, "report.md")
    report = open(report_path).read() if os.path.exists(report_path) else ""
    results = []

    def check(text, passed, evidence):
        results.append({"text": text, "passed": bool(passed), "evidence": str(evidence)})

    check("The plan file review_response_7.md exists in the repo directory", bool(plan_text), f"{len(plan_text)} chars")
    tracked = git(repo, "log", "--all", "--oneline", "--", "review_response_7.md").stdout.strip()
    check("The plan file is never committed", not tracked, tracked or "no commit touches it")
    check("The grilling round uses the grilling skill's question format (Q-numbered, with a recommended answer)",
          re.search(r"\bQ1\b", rounds) and "➡️" in rounds, f"Q1={'Q1' in rounds}, arrow={'➡️' in rounds}")
    for item in ("5001", "5002", "5003", "5004"):
        check(f"The plan covers unresolved thread {item}", item in plan_text, "root_comment_id present" if item in plan_text else "missing")

    by_root = {t["comments"][0]["id"]: t for t in state["threads"]}
    init_by_root = {t["comments"][0]["id"]: t for t in initial["threads"]}
    new_conv = [c for c in state["conversation"] if c["id"] > 9000]

    if kind == "plan-only":
        check("Nothing was written to GitHub (no reply, comment, body edit, or reviewer request)", not writes,
              [w["note"] for w in writes] or "0 writes")
        check("The remote PR branch is unchanged", bare_head == start, f"{bare_head[:8]} vs start {start[:8]}")
        commits = git(repo, "rev-list", "--all", "--count").stdout.strip()
        check("No commit was created locally", commits == "2", f"{commits} commits in the repo (2 at start)")
        check("The user stays on their branch (main)", git(repo, "branch", "--show-current").stdout.strip() == "main",
              git(repo, "branch", "--show-current").stdout.strip())
        dirty = git(repo, "status", "--porcelain", "--untracked-files=no").stdout.strip()
        check("Tracked files are untouched", not dirty, dirty or "clean")
        check("The first grilling round raises the checkout blocker", re.search(r"checkout", rounds, re.I), "mentions checkout" if "checkout" in rounds.lower() else "no mention")
        check("The report says nothing was changed or posted and what execution needs",
              re.search(r"plan-only", report, re.I) and re.search(r"check(ed)? ?out", report, re.I), report[:200].replace("\n", " "))
    else:
        check("The push landed: the remote PR branch equals local HEAD", bare_head == local_head and bare_head != start,
              f"remote {bare_head[:8]}, local {local_head[:8]}, start {start[:8]}")
        ff = git(repo, "merge-base", "--is-ancestor", start, bare_head).returncode == 0
        check("The push was a fast-forward on top of the reviewed commit (no rewritten history)", ff, f"start is ancestor: {ff}")
        test = subprocess.run(["make", "-s", "test"], cwd=repo, capture_output=True, text=True)
        lint = subprocess.run(["make", "-s", "lint"], cwd=repo, capture_output=True, text=True)
        check("The repo's gates (make lint, make test) pass at HEAD", test.returncode == 0 and lint.returncode == 0,
              (test.stderr.strip().splitlines() or ["?"])[-1])
        src = open(os.path.join(repo, "ratelimit", "limiter.py")).read()
        check("The window-boundary bug is fixed in limiter.py (hit exactly W old expires)", "<= now - self._window" in src or "> now - self._window" in src or "<=" in src,
              [l.strip() for l in src.splitlines() if "self._window" in l and ("<" in l or ">" in l)])
        diff_tests = git(repo, "diff", "--stat", start, bare_head, "--", "tests").stdout.strip()
        check("Tests were added or changed for the fixes", bool(diff_tests), diff_tests.splitlines()[-1] if diff_tests else "no test diff")
        readme = open(os.path.join(repo, "README.md")).read()
        check("README documents the burst parameter (review summary request)", "burst" in readme.lower(), "burst mentioned" if "burst" in readme.lower() else "no")
        subjects = git(repo, "log", "--format=%s", f"{start}..{bare_head}").stdout.strip().splitlines()
        conv = all(re.match(r"^(feat|fix|docs|test|refactor|chore|perf)(\([^)]+\))?: .+\(RATE-12\)$", s) for s in subjects)
        check("Commits follow the repo's convention (Conventional Commits ending in (RATE-12))", conv and subjects, subjects)
        for root in (5001, 5002, 5003, 5004):
            added = by_root[root]["comments"][len(init_by_root[root]["comments"]):]
            ok = len(added) == 1 and added[0]["author"] == state["viewer"]
            check(f"Thread {root} received exactly one inline reply from the author", ok,
                  (added[0]["body"][:140].replace("\n", " ") if added else "no reply"))
        added_resolved = by_root[5005]["comments"][len(init_by_root[5005]["comments"]):]
        check("The resolved thread (5005) received no reply", not added_resolved, f"{len(added_resolved)} replies")
        check("The review summary is answered with exactly one top-level comment", len(new_conv) == 1,
              (new_conv[0]["body"][:140].replace("\n", " ") if new_conv else "none"))
        bodies = [c["body"] for t in state["threads"] for c in t["comments"] if c["id"] > 9000] + [c["body"] for c in new_conv]
        check("No posted reply still contains the <sha> placeholder", not any("<sha>" in b for b in bodies), f"{len(bodies)} replies checked")
        shas = set(re.findall(r"\b[0-9a-f]{7,40}\b", " ".join(bodies)))
        real = [s for s in shas if git(repo, "merge-base", "--is-ancestor", s, bare_head).returncode == 0]
        check("Replies cite commits that exist on the pushed branch", bool(real) and len(real) == len(shas), f"cited {sorted(shas)}, on branch {sorted(real)}")
        pushback = by_root[5002]["comments"][-1]["body"]
        check("Thread 5002 (limit validation) is pushed back with the existing check as evidence", "_check_arguments" in pushback, pushback[:160].replace("\n", " "))
        voice = re.search(r"claude|anthropic|\bAI\b|🤖|generated", " ".join(bodies), re.I)
        check("Replies read as the author's own (no tool or model mentions, no signature)", not voice, voice.group(0) if voice else "clean")
        body = state["pr"]["body"]
        check("The PR description keeps its original text and gains one review-response block",
              body.startswith(initial["pr"]["body"].rstrip()) and body.count("<!-- review-response:start -->") == 1, body[-160:].replace("\n", " "))
        check("Review was re-requested from the reviewer who requested changes (rev-maria)", "rev-maria" in state.get("review_requests", []), state.get("review_requests"))
        check("A publish round was shown before anything was sent", re.search(r"publish", rounds, re.I), "publish round present" if re.search(r"publish", rounds, re.I) else "missing")
        filled = len(re.findall(r"Posted\**:?\**\s*`?<?https?://", plan_text))
        check("The plan's Posted: lines record the reply URLs", filled >= 4, f"{filled} Posted URLs")

    passed = sum(r["passed"] for r in results)
    out = {"expectations": results, "summary": {"passed": passed, "failed": len(results) - passed, "total": len(results),
                                                 "pass_rate": round(passed / len(results), 3)}}
    with open(os.path.join(os.path.dirname(outputs.rstrip("/")), "grading.json"), "w") as handle:
        json.dump(out, handle, indent=2)
    for r in results:
        print(("PASS " if r["passed"] else "FAIL ") + r["text"] + "  [" + r["evidence"][:150] + "]")
    print(f"{passed}/{len(results)}")


if __name__ == "__main__":
    main()
