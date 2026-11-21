#!/usr/bin/env python3
"""Sandbox stand-in for the `gh` CLI, used to test the review-response skill offline.

Serves one fake pull request from ../gh-state/state.json, records every call in
../gh-state/calls.jsonl, and applies writes (replies, comments, body edits,
reviewer requests) to the state file. The PR head is read live from the sandbox's
bare remote, so a real `git push` is what moves it.
"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "gh-state", "state.json")
CALLS = os.path.join(ROOT, "gh-state", "calls.jsonl")
REMOTE = os.path.join(ROOT, "remote.git")


def load():
    with open(STATE, encoding="utf-8") as handle:
        return json.load(handle)


def save(state):
    with open(STATE, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)


def log(argv, stdin_text, note=""):
    with open(CALLS, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"argv": argv, "stdin": stdin_text, "cwd": os.getcwd(), "note": note}) + "\n")


def fail(message, argv, stdin_text=None):
    log(argv, stdin_text, note=f"ERROR: {message}")
    print(message, file=sys.stderr)
    sys.exit(1)


def head_oid(state):
    out = subprocess.run(["git", "--git-dir", REMOTE, "rev-parse", f"refs/heads/{state['pr']['headRefName']}"],
                         capture_output=True, text=True)
    return out.stdout.strip()


def emit(value, jq_expr):
    text = json.dumps(value)
    if jq_expr:
        proc = subprocess.run(["jq", "-r", jq_expr], input=text, capture_output=True, text=True)
        if proc.returncode != 0:
            print(proc.stderr, file=sys.stderr)
            sys.exit(1)
        sys.stdout.write(proc.stdout)
    else:
        print(text)


def current_branch():
    out = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True)
    return out.stdout.strip() if out.returncode == 0 else None


def pr_url(state):
    pr = state["pr"]
    return f"https://{state['host']}/{state['owner']}/{state['repo']}/pull/{pr['number']}"


def is_this_pr(state, target):
    return target in (str(state["pr"]["number"]), pr_url(state), state["pr"]["headRefName"])


def pr_view_object(state):
    pr = state["pr"]
    return {
        "number": pr["number"], "title": pr["title"], "body": pr["body"], "url": pr_url(state),
        "state": pr["state"], "isDraft": False, "author": {"login": pr["author"]},
        "headRefName": pr["headRefName"], "baseRefName": pr["baseRefName"], "headRefOid": head_oid(state),
        "isCrossRepository": False, "reviewDecision": "CHANGES_REQUESTED",
        "headRepository": {"name": state["repo"]}, "headRepositoryOwner": {"login": state["owner"]},
        "commits": [{"oid": c["oid"], "messageHeadline": c["message"].splitlines()[0], "messageBody": ""} for c in pr["commits"]],
        "files": [{"path": p} for p in pr["files"]],
        "reviewRequests": [{"login": r} for r in state.get("review_requests", [])],
    }


def take(args, flag):
    """Pop `flag VALUE` from args; return VALUE or None."""
    if flag in args:
        i = args.index(flag)
        value = args[i + 1]
        del args[i:i + 2]
        return value
    return None


def cmd_pr(state, argv, args):
    sub = args.pop(0)
    take(args, "--repo") or take(args, "-R")
    if sub == "view":
        fields = take(args, "--json")
        jq_expr = take(args, "--jq") or take(args, "-q")
        target = args[0] if args else None
        if target is None and current_branch() != state["pr"]["headRefName"]:
            fail(f'no pull requests found for branch "{current_branch()}"', argv)
        if target is not None and not is_this_pr(state, target):
            fail(f"GraphQL: Could not resolve to a PullRequest ({target})", argv)
        obj = pr_view_object(state)
        if fields:
            obj = {k: obj[k] for k in fields.split(",") if k in obj}
        log(argv, None)
        emit(obj, jq_expr)
    elif sub == "checkout":
        log(argv, None)
        sys.exit(subprocess.run(["git", "checkout", state["pr"]["headRefName"]]).returncode)
    elif sub == "diff":
        log(argv, None)
        sys.exit(subprocess.run(["git", "diff", f"origin/{state['pr']['baseRefName']}...origin/{state['pr']['headRefName']}"]).returncode)
    elif sub == "edit":
        reviewers = take(args, "--add-reviewer")
        body = take(args, "--body") or take(args, "-b")
        body_file = take(args, "--body-file") or take(args, "-F")
        if body_file:
            body = sys.stdin.read() if body_file == "-" else open(body_file, encoding="utf-8").read()
        if reviewers:
            state.setdefault("review_requests", []).extend(reviewers.split(","))
        if body is not None:
            state["pr"]["body"] = body
        save(state)
        log(argv, body, note="WRITE pr edit")
        print(pr_url(state))
    elif sub == "comment":
        body = take(args, "--body") or take(args, "-b")
        body_file = take(args, "--body-file") or take(args, "-F")
        if body_file:
            body = open(body_file, encoding="utf-8").read()
        add_conversation(state, body)
        log(argv, body, note="WRITE pr comment")
    else:
        fail(f"sandbox gh: unsupported command: gh pr {sub}", argv)


def add_conversation(state, body):
    state["next_id"] += 1
    comment = {"id": state["next_id"], "user": {"login": state["viewer"], "type": "User"}, "body": body,
               "created_at": "2026-11-20T12:00:00Z",
               "html_url": f"{pr_url(state)}#issuecomment-{state['next_id']}"}
    state["conversation"].append(comment)
    save(state)
    return comment


def graphql(state):
    pr = state["pr"]
    threads = []
    for t in state["threads"]:
        threads.append({
            "id": f"PRRT_{t['comments'][0]['id']}", "isResolved": t["resolved"], "isOutdated": t.get("outdated", False),
            "path": t["path"], "line": t["line"], "originalLine": t["line"], "startLine": None,
            "resolvedBy": {"login": t["resolved_by"]} if t.get("resolved_by") else None,
            "comments": {"totalCount": len(t["comments"]), "nodes": [{
                "databaseId": c["id"], "author": {"login": c["author"], "__typename": "User"}, "body": c["body"],
                "createdAt": c.get("created_at", "2026-11-19T10:00:00Z"),
                "url": f"{pr_url(state)}#discussion_r{c['id']}", "diffHunk": t["diff_hunk"]} for c in t["comments"]]},
        })
    return {"data": {"viewer": {"login": state["viewer"]}, "repository": {"pullRequest": {
        "number": pr["number"], "url": pr_url(state), "title": pr["title"], "body": pr["body"], "state": pr["state"],
        "isDraft": False, "isCrossRepository": False, "author": {"login": pr["author"]},
        "headRefName": pr["headRefName"], "headRefOid": head_oid(state), "baseRefName": pr["baseRefName"],
        "headRepository": {"nameWithOwner": f"{state['owner']}/{state['repo']}"},
        "commits": {"nodes": [{"commit": c} for c in pr["commits"]]},
        "reviewThreads": {"pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": threads},
    }}}}


def cmd_api(state, argv, args):
    take(args, "--hostname")
    method = (take(args, "--method") or take(args, "-X") or "GET").upper()
    jq_expr = take(args, "--jq") or take(args, "-q")
    input_file = take(args, "--input")
    fields = {}
    for flag in ("-f", "-F", "--field", "--raw-field"):
        while flag in args:
            key, _, value = take(args, flag).partition("=")
            if flag in ("-F", "--field") and value.startswith("@"):
                value = open(value[1:], encoding="utf-8").read()
            fields[key] = value
    args = [a for a in args if a not in ("--paginate", "--silent", "-i")]
    stdin_text = sys.stdin.read() if input_file == "-" else (open(input_file, encoding="utf-8").read() if input_file else None)
    payload = json.loads(stdin_text) if stdin_text else fields
    if (payload or fields) and method == "GET" and args and args[0] != "graphql":
        method = "POST"
    path = args[0].lstrip("/") if args else ""
    base = f"repos/{state['owner']}/{state['repo']}"
    n = state["pr"]["number"]

    if path == "graphql":
        if "reviewThreads" not in fields.get("query", "") and "pullRequest" not in fields.get("query", ""):
            fail("sandbox gh: only pullRequest GraphQL queries are supported", argv)
        log(argv, None)
        return emit(graphql(state), jq_expr)
    if path == "user":
        log(argv, None)
        return emit({"login": state["viewer"]}, jq_expr)
    if path == f"{base}/pulls/{n}" and method == "GET":
        log(argv, None)
        return emit({"number": n, "body": state["pr"]["body"], "html_url": pr_url(state), "state": "open", "draft": False,
                     "title": state["pr"]["title"], "user": {"login": state["pr"]["author"]},
                     "head": {"sha": head_oid(state), "ref": state["pr"]["headRefName"]},
                     "base": {"ref": state["pr"]["baseRefName"]}}, jq_expr)
    if path == f"{base}/pulls/{n}" and method == "PATCH":
        state["pr"]["body"] = payload["body"]
        save(state)
        log(argv, stdin_text, note="WRITE pr body")
        return emit({"html_url": pr_url(state), "body": payload["body"]}, jq_expr)
    if path == f"{base}/pulls/{n}/reviews" and method == "GET":
        log(argv, None)
        return emit(state["reviews"], jq_expr)
    if path == f"{base}/pulls/{n}/comments" and method == "GET":
        flat = []
        for t in state["threads"]:
            root = t["comments"][0]["id"]
            for i, c in enumerate(t["comments"]):
                flat.append({"id": c["id"], "user": {"login": c["author"]}, "body": c["body"], "path": t["path"],
                             "line": t["line"], "original_line": t["line"], "diff_hunk": t["diff_hunk"],
                             "in_reply_to_id": None if i == 0 else root,
                             "html_url": f"{pr_url(state)}#discussion_r{c['id']}"})
        log(argv, None)
        return emit(flat, jq_expr)
    if path == f"{base}/issues/{n}/comments" and method == "GET":
        log(argv, None)
        return emit(state["conversation"], jq_expr)
    if path == f"{base}/issues/{n}/comments" and method == "POST":
        comment = add_conversation(state, payload["body"])
        log(argv, stdin_text, note="WRITE conversation comment")
        return emit(comment, jq_expr)
    prefix, suffix = f"{base}/pulls/{n}/comments/", "/replies"
    if path.startswith(prefix) and path.endswith(suffix) and method == "POST":
        root = int(path[len(prefix):-len(suffix)])
        thread = next((t for t in state["threads"] if t["comments"][0]["id"] == root), None)
        if thread is None:
            fail("gh: Not Found (HTTP 404): replies must target a thread's root comment", argv, stdin_text)
        state["next_id"] += 1
        thread["comments"].append({"id": state["next_id"], "author": state["viewer"], "body": payload["body"],
                                   "created_at": "2026-11-20T12:00:00Z"})
        save(state)
        log(argv, stdin_text, note=f"WRITE thread reply {root}")
        return emit({"id": state["next_id"], "html_url": f"{pr_url(state)}#discussion_r{state['next_id']}"}, jq_expr)
    fail(f"sandbox gh: unsupported API call: {method} {path}", argv, stdin_text)


def main():
    argv = sys.argv[1:]
    args = list(argv)
    state = load()
    if not args:
        fail("sandbox gh: no command", argv)
    top = args.pop(0)
    if top == "auth":
        log(argv, None)
        print(f"{state['host']}\n  ✓ Logged in to {state['host']} account {state['viewer']} (sandbox)")
    elif top == "pr":
        cmd_pr(state, argv, args)
    elif top == "api":
        cmd_api(state, argv, args)
    elif top == "repo" and args and args[0] == "view":
        log(argv, None)
        take(args, "--json")
        emit({"nameWithOwner": f"{state['owner']}/{state['repo']}", "url": f"https://{state['host']}/{state['owner']}/{state['repo']}",
              "isFork": False, "defaultBranchRef": {"name": state["pr"]["baseRefName"]}}, take(args, "--jq"))
    else:
        fail(f"sandbox gh: unsupported command: gh {' '.join(argv[:2])}", argv)


if __name__ == "__main__":
    main()
