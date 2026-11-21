#!/usr/bin/env python3
"""Grade a refactor-skill sandbox run from its end state.

  grade.py <case-dir> <outputs-dir> with-pr|no-pr     -> writes grading.json beside outputs
"""

import glob
import json
import os
import re
import subprocess
import sys
import tempfile

BRANCH = "feat/ORD-31-quote"
ORDER = '{"items": [{"sku": "a", "qty": %d, "unit_price": %s}], "country": "%s"}'
PROBES = [  # (payload, flags) - the CLI output for each is the contract
    (ORDER % (2, "10.0", "DE"), []), (ORDER % (2, "10.0", "DE"), ["--no-tax"]),
    (ORDER % (2, "10.0", "DE"), ["--shipping"]), (ORDER % (1, "200.0", "FR"), []),
    (ORDER % (1, "200.0", "FR"), ["--no-tax", "--shipping"]), (ORDER % (3, "50.0", "US"), ["--shipping"]),
    (ORDER % (1, "2.0", "DE"), []), (ORDER % (1, "9.99", "FR"), ["--shipping"]),
    (ORDER % (1, "10.0", "US"), []), (ORDER % (4, "30.25", "DE"), ["--shipping"]),
    (ORDER % (1, "100.01", "DE"), []), (ORDER % (1, "99.99", "FR"), []),
]
BOUNDARY = [(ORDER % (1, "100.0", "DE"), []), (ORDER % (2, "50.0", "FR"), ["--shipping"])]


def sh(args, cwd):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


def probe(tree, cases):
    return [sh(["python3", "-m", "orders", "quote", payload, *flags], tree).stdout.strip() for payload, flags in cases]


def main():
    case, outputs, kind = os.path.abspath(sys.argv[1]), sys.argv[2], sys.argv[3]
    repo = os.path.join(case, "repo")
    state = json.load(open(os.path.join(case, "gh-state", "state.json")))
    initial = json.load(open(os.path.join(case, "gh-state", "state.initial.json")))
    start = initial["pr"]["commits"][0]["oid"]
    bare = sh(["git", "--git-dir", os.path.join(case, "remote.git"), "rev-parse", f"refs/heads/{BRANCH}"], case).stdout.strip()
    # the workspace is wherever the branch is checked out
    work = repo
    for block in sh(["git", "worktree", "list", "--porcelain"], repo).stdout.split("\n\n"):
        if f"branch refs/heads/{BRANCH}" in block:
            work = block.splitlines()[0].split(" ", 1)[1]
    head = sh(["git", "rev-parse", "HEAD"], work).stdout.strip()
    plans = [p for p in glob.glob(os.path.join(case, "**", "refactor-*.md"), recursive=True) if "/.git/" not in p]
    plan_text = open(plans[0]).read() if plans else ""
    rounds_path = os.path.join(outputs, "rounds.md")
    rounds = open(rounds_path).read() if os.path.exists(rounds_path) else ""
    results = []

    def check(text, passed, evidence):
        results.append({"text": text, "passed": bool(passed), "evidence": str(evidence)[:300]})

    def source(pattern):
        return {p: open(p).read() for p in glob.glob(os.path.join(work, pattern), recursive=True)}

    want = "refactor-7.md" if kind == "with-pr" else "refactor-feat-ORD-31-quote.md"
    check(f"The plan is written to {want} in the workspace root", plans and os.path.basename(plans[0]) == want and os.path.dirname(plans[0]) == work,
          [os.path.relpath(p, case) for p in plans])
    committed = sh(["git", "log", "--all", "--oneline", "--", "refactor-*.md"], work).stdout.strip()
    check("The plan file is never committed", not committed, committed or "no commit touches it")
    check("Questions use the grilling format (Q-numbered rounds with the ❓ and ➡️ markers)", "❓" in rounds and "➡️" in rounds,
          f"❓ x{rounds.count('❓')}, ➡️ x{rounds.count('➡️')}")
    check("A publish round is shown before anything is sent", re.search(r"publish", rounds, re.I), "present" if re.search(r"publish", rounds, re.I) else "missing")
    check("The plan cites clean-code rule ids for its items", len(set(re.findall(r"\b(?:G[1-4]|D[1-6]|U[1-6]|N[1-6]|F[1-6]|C[1-8]|S(?:10|[1-9])|O[1-9]|T[1-5]|SM[1-6])\b", plan_text))) >= 5,
          sorted(set(re.findall(r"\b(?:G[1-4]|D[1-6]|U[1-6]|N[1-6]|F[1-6]|C[1-8]|S(?:10|[1-9])|O[1-9]|T[1-5]|SM[1-6])\b", plan_text))))
    check("The plan records the architecture rules it judged against (cites docs/architecture.md)", "docs/architecture.md" in plan_text, "cited" if "docs/architecture.md" in plan_text else "not cited")
    statuses = re.findall(r"Status:?\**:?\s*`?(\w+)", plan_text)
    check("Every plan item ends as done, none left planned", statuses.count("done") >= 2 and "planned" not in statuses, statuses)

    check("The push landed: the remote branch equals the workspace HEAD and moved past the start", bare == head and bare != start, f"remote {bare[:8]}, local {head[:8]}, start {start[:8]}")
    check("The push was a fast-forward (history not rewritten)", sh(["git", "merge-base", "--is-ancestor", start, bare], work).returncode == 0, "start is an ancestor of the remote head")
    subjects = sh(["git", "log", "--reverse", "--format=%s", f"{start}..{head}"], work).stdout.strip().splitlines()
    conv = [s for s in subjects if re.match(r"^(feat|fix|docs|test|refactor|chore|perf|style)(\([^)]+\))?: .+\(ORD-31\)$", s)]
    check("The work lands as several commits in the repo's convention", len(subjects) >= 2 and len(conv) == len(subjects), subjects)

    gates = {g: sh(["make", "-s", g], work).returncode for g in ("lint", "arch", "test")}
    check("All gates pass at HEAD, including the architecture gate that failed at the start", not any(gates.values()), gates)
    tmp = tempfile.mkdtemp()
    sh(["git", "worktree", "add", "--detach", os.path.join(tmp, "start"), start], repo)
    before, after = probe(os.path.join(tmp, "start"), PROBES), probe(work, PROBES)
    b_before, b_after = probe(os.path.join(tmp, "start"), BOUNDARY), probe(work, BOUNDARY)
    sh(["git", "worktree", "remove", "--force", os.path.join(tmp, "start")], repo)
    diffs = [(PROBES[i][1], before[i], after[i]) for i in range(len(PROBES)) if before[i] != after[i]]
    check("Behavior is preserved: the CLI prints the same output as before for every probe order", not diffs and all(before), diffs or f"{len(PROBES)} probes identical")
    fix_commits = [s for s in subjects if s.startswith("fix")]
    changed_boundary = b_before != b_after
    check("The discount-boundary bug (R2) is either left alone or fixed in its own fix commit, never inside a refactor commit",
          (not changed_boundary) or bool(fix_commits), f"boundary output changed: {changed_boundary}; fix commits: {fix_commits}")
    surfaced = re.search(r"R2|100(\.00)? or more|boundary|>=", plan_text) and re.search(r"[Cc]orrectness", plan_text)
    check("The plan surfaces the R2 boundary bug as a correctness item", surfaced, "found" if surfaced else "not found")

    domain, app, adapters = source("orders/domain/**/*.py"), source("orders/app/**/*.py"), source("orders/adapters/**/*.py")
    inner = "\n".join(list(domain.values()) + list(app.values()))
    check("The domain no longer builds its own adapter or hard-codes the rates file path", "FileTaxRates" not in inner and "tax_rates.json" not in inner,
          "clean" if "FileTaxRates" not in inner and "tax_rates.json" not in inner else "still present")
    check("The minimum-order rule is out of the CLI adapter", not re.search(r"<\s*10(\.0+)?\b", "\n".join(adapters.values())), "no `< 10` comparison in orders/adapters")
    allsrc = "\n".join(source("orders/**/*.py").values())
    check("The flag arguments are gone (no `flag`/`f2` parameters)", not re.search(r"\bflag\s*=|\bf2\b", allsrc), "no flag parameters")
    check("Commented-out code and the closing comment are removed", "old_total" not in allsrc and "# end calc" not in allsrc, "removed")
    check("Magic numbers are named (a constant for the discount)", re.search(r"^[A-Z0-9_]*DISCOUNT[A-Z0-9_]*\s*(:\s*\w+\s*)?=", allsrc, re.M), "constant found" if re.search(r"^[A-Z0-9_]*DISCOUNT", allsrc, re.M) else "none")
    tests = "\n".join(source("tests/**/*.py").values())
    names = re.findall(r"def (test_\w+)", tests)
    check("Tests are split and named for behavior (no test_1/test_2; more tests than before)", not re.search(r"def test_\d+\b", tests) and len(names) > 4, f"{len(names)} tests")

    body = state["pr"]["body"]
    if kind == "with-pr":
        check("The PR description keeps its original text and gains one refactor block",
              body.startswith(initial["pr"]["body"].rstrip()) and body.count("<!-- refactor:start -->") == 1, body[-120:].replace("\n", " "))
        check("The plan review came from codex", re.search(r"codex", plan_text, re.I), "codex mentioned" if re.search(r"codex", plan_text, re.I) else "no mention")
    else:
        check("A PR was opened against main with the refactor block in its body", state.get("pr_open") and "<!-- refactor:start -->" in body and state["pr"]["baseRefName"] == "main",
              f"open={state.get('pr_open')}, block={'<!-- refactor:start -->' in body}")
        check("The work happened in a worktree beside the repo", work == os.path.join(case, "repo-worktrees", "feat-ORD-31-quote"), os.path.relpath(work, case))
        main_ok = sh(["git", "branch", "--show-current"], repo).stdout.strip() == "main" and not sh(["git", "status", "--porcelain"], repo).stdout.strip()
        check("The user's own checkout is untouched (still on main, clean)", main_ok, sh(["git", "status", "-sb"], repo).stdout.strip())

    passed = sum(r["passed"] for r in results)
    out = {"expectations": results, "summary": {"passed": passed, "failed": len(results) - passed, "total": len(results),
                                                 "pass_rate": round(passed / len(results), 3)}}
    with open(os.path.join(os.path.dirname(outputs.rstrip("/")), "grading.json"), "w") as handle:
        json.dump(out, handle, indent=2)
    for r in results:
        print(("PASS " if r["passed"] else "FAIL ") + r["text"] + "  [" + r["evidence"][:140] + "]")
    print(f"{passed}/{len(results)}")


if __name__ == "__main__":
    main()
