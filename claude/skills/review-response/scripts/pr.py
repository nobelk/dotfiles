#!/usr/bin/env python3
"""GitHub plumbing for the review-response skill. Standard library plus the `gh` CLI.

  pr.py fetch [PR-URL | PR-number] [--out FILE]
      Print one JSON snapshot of the PR: metadata, review threads with their
      resolution state, review summaries, conversation comments, and Jira-key
      candidates. With no argument, uses the current branch's PR.

  pr.py reply <PR-URL | PR-number> <replies.json> [--dry-run]
      Post replies. replies.json is a list of
        {"reply_to": <thread root_comment_id>, "seen_comments": <comment_count at fetch>, "body": "..."}
        {"conversation": true, "body": "..."}        # one top-level PR comment
      A thread that was resolved, or gained a comment since the snapshot, is held
      rather than answered; a reply that is already there is skipped. The result
      lists each target under posted / skipped / held / failed (--dry-run: would_post).

  pr.py body <PR-URL | PR-number> <section.md> [--dry-run]
      Replace (or append) the <!-- review-response --> block of the PR description
      with the contents of section.md, leaving the rest of the description as written.

Exit status: 0 on success, 1 when a write failed, 2 when the PR cannot be resolved.
"""

import argparse
import json
import re
import subprocess
import sys

PR_URL = re.compile(r"^https?://([^/]+)/([^/]+)/([^/]+)/pull/(\d+)")
TICKET = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b")
PLACEHOLDER = re.compile(r"<sha[:>]")  # <sha> or <sha:name>, left unfilled
BLOCK_START = "<!-- review-response:start -->"
BLOCK_END = "<!-- review-response:end -->"

QUERY = """
query($owner:String!,$repo:String!,$n:Int!,$cursor:String){
  viewer{login}
  repository(owner:$owner,name:$repo){
    pullRequest(number:$n){
      number url title body state isDraft isCrossRepository
      author{login}
      headRefName headRefOid baseRefName
      headRepository{nameWithOwner}
      commits(last:100){nodes{commit{oid message}}}
      reviewThreads(first:50,after:$cursor){
        pageInfo{hasNextPage endCursor}
        nodes{
          id isResolved isOutdated path line originalLine startLine
          resolvedBy{login}
          comments(first:100){
            totalCount
            nodes{databaseId author{login __typename} body createdAt url diffHunk}
          }
        }
      }
    }
  }
}
"""


class GhError(Exception):
    pass


def gh(args, stdin=None):
    proc = subprocess.run(["gh", *args], input=stdin, capture_output=True, text=True)
    if proc.returncode != 0:
        raise GhError(proc.stderr.strip() or proc.stdout.strip() or f"gh {args[0]} failed")
    return proc.stdout


def resolve(pr_arg):
    """Return (host, owner, repo, number) for a PR URL, a PR number, or the current branch."""
    match = PR_URL.match(pr_arg or "")
    if not match:
        view = ["pr", "view", "--json", "url", "--jq", ".url"]
        if pr_arg:
            view.insert(2, pr_arg)
        try:
            match = PR_URL.match(gh(view).strip())
        except GhError as err:
            print(f"cannot resolve the pull request: {err}", file=sys.stderr)
            sys.exit(2)
        if not match:
            print("cannot resolve the pull request: gh returned no PR url", file=sys.stderr)
            sys.exit(2)
    host, owner, repo, number = match.groups()
    return host, owner, repo, int(number)


def rest_list(host, path):
    """Every item of a paginated REST list endpoint."""
    out = gh(["api", "--hostname", host, "--paginate", path, "--jq", ".[] | tojson"])
    return [json.loads(line) for line in out.splitlines() if line.strip()]


def is_bot(login, kind):
    return kind == "Bot" or (login or "").endswith("[bot]")


def ticket_candidates(pr, commits):
    """Jira-style keys in priority order: branch, title, body, commit messages."""
    seen, found = set(), []
    sources = [
        ("branch", pr["headRefName"].upper()),  # branch names are often lowercased
        ("title", pr["title"]),
        ("body", pr["body"] or ""),
        ("commits", "\n".join(commits)),
    ]
    for source, text in sources:
        for key in TICKET.findall(text):
            if key not in seen:
                seen.add(key)
                found.append({"key": key, "source": source})
    return found


def fetch(host, owner, repo, number):
    threads, cursor, pr, viewer = [], None, None, None
    while True:
        args = ["api", "graphql", "--hostname", host, "-f", f"query={QUERY}",
                "-F", f"owner={owner}", "-F", f"repo={repo}", "-F", f"n={number}"]
        if cursor:
            args += ["-f", f"cursor={cursor}"]
        data = json.loads(gh(args))["data"]
        viewer = data["viewer"]["login"]
        pr = data["repository"]["pullRequest"]
        if pr is None:
            raise GhError(f"no pull request #{number} in {owner}/{repo}")
        page = pr["reviewThreads"]
        for node in page["nodes"]:
            comments = [{
                "id": c["databaseId"],
                "author": (c["author"] or {}).get("login"),
                "is_bot": is_bot((c["author"] or {}).get("login"), (c["author"] or {}).get("__typename")),
                "body": c["body"],
                "created_at": c["createdAt"],
                "url": c["url"],
            } for c in node["comments"]["nodes"]]
            if not comments:
                continue
            threads.append({
                "root_comment_id": comments[0]["id"],
                "path": node["path"],
                "line": node["line"] or node["originalLine"],
                "start_line": node["startLine"],
                "is_resolved": node["isResolved"],
                "is_outdated": node["isOutdated"],
                "resolved_by": (node["resolvedBy"] or {}).get("login"),
                "comment_count": node["comments"]["totalCount"],
                "diff_hunk": node["comments"]["nodes"][0]["diffHunk"],
                "url": comments[0]["url"],
                "comments": comments,
            })
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]

    base = f"repos/{owner}/{repo}"
    reviews = [{
        "id": r["id"],
        "author": (r.get("user") or {}).get("login"),
        "is_bot": is_bot((r.get("user") or {}).get("login"), (r.get("user") or {}).get("type")),
        "state": r["state"],
        "body": r.get("body") or "",
        "submitted_at": r.get("submitted_at"),
        "commit_id": r.get("commit_id"),
        "url": r.get("html_url"),
    } for r in rest_list(host, f"{base}/pulls/{number}/reviews") if r["state"] != "PENDING"]
    conversation = [{
        "id": c["id"],
        "author": (c.get("user") or {}).get("login"),
        "is_bot": is_bot((c.get("user") or {}).get("login"), (c.get("user") or {}).get("type")),
        "body": c.get("body") or "",
        "created_at": c.get("created_at"),
        "url": c.get("html_url"),
    } for c in rest_list(host, f"{base}/issues/{number}/comments")]

    commits = [n["commit"]["message"] for n in pr["commits"]["nodes"]]
    unresolved = [t for t in threads if not t["is_resolved"]]
    return {
        "pr": {
            "host": host, "owner": owner, "repo": repo, "number": number,
            "url": pr["url"], "title": pr["title"], "body": pr["body"],
            "state": pr["state"], "is_draft": pr["isDraft"],
            "author": (pr["author"] or {}).get("login"),
            "head_ref": pr["headRefName"], "head_oid": pr["headRefOid"],
            "head_repo": (pr["headRepository"] or {}).get("nameWithOwner"),
            "base_ref": pr["baseRefName"], "is_fork": pr["isCrossRepository"],
        },
        "viewer": viewer,
        "ticket_candidates": ticket_candidates(pr, commits),
        "counts": {
            "threads": len(threads),
            "unresolved": len(unresolved),
            "unresolved_outdated": sum(1 for t in unresolved if t["is_outdated"]),
            "resolved": len(threads) - len(unresolved),
            "reviews_requesting_changes": sum(1 for r in reviews if r["state"] == "CHANGES_REQUESTED"),
            # Review summaries and top-level comments worth reading: not empty, not a bot's, not the author's own.
            "comments_outside_threads": sum(
                1 for c in reviews + conversation
                if c["body"].strip() and not c["is_bot"] and c["author"] != (pr["author"] or {}).get("login")),
        },
        "threads": threads,
        "reviews": reviews,
        "conversation": conversation,
    }


def post(host, path, body):
    out = gh(["api", "--hostname", host, "--method", "POST", path, "--input", "-"],
             stdin=json.dumps({"body": body}))
    return json.loads(out).get("html_url")


def reply(host, owner, repo, number, replies, dry_run):
    snapshot = fetch(host, owner, repo, number)
    viewer = snapshot["viewer"]
    by_root = {t["root_comment_id"]: t for t in snapshot["threads"]}
    base = f"repos/{owner}/{repo}"
    result = {"posted": [], "would_post": [], "skipped": [], "held": [], "failed": []}

    for item in replies:
        body = (item.get("body") or "").strip()
        target = "conversation" if item.get("conversation") else item.get("reply_to")
        entry = {"target": target}
        if not body:
            result["failed"].append({**entry, "error": "empty body"})
            continue
        if PLACEHOLDER.search(body):
            result["failed"].append({**entry, "error": "unfilled commit placeholder"})
            continue

        if item.get("conversation"):
            dup = next((c for c in snapshot["conversation"]
                        if c["author"] == viewer and c["body"].strip() == body), None)
            if dup:
                result["skipped"].append({**entry, "reason": "already posted", "url": dup["url"]})
                continue
            path = f"{base}/issues/{number}/comments"
        else:
            thread = by_root.get(target)
            if thread is None:
                result["failed"].append({**entry, "error": "no thread with this root_comment_id"})
                continue
            last = thread["comments"][-1]
            if last["author"] == viewer and last["body"].strip() == body:
                result["skipped"].append({**entry, "reason": "already posted", "url": last["url"]})
                continue
            if thread["is_resolved"]:
                result["held"].append({**entry, "reason": "thread resolved since the snapshot"})
                continue
            if thread["comment_count"] != item.get("seen_comments"):
                result["held"].append({**entry, "reason": "new comment since the snapshot",
                                       "latest": f'{last["author"]}: {last["body"][:200]}'})
                continue
            path = f"{base}/pulls/{number}/comments/{target}/replies"

        if dry_run:
            result["would_post"].append(entry)
            continue
        try:
            result["posted"].append({**entry, "url": post(host, path, body)})
        except GhError as err:
            result["failed"].append({**entry, "error": str(err)})
    return result


def splice(body, section):
    """The PR description with its review-response block replaced, or appended."""
    block = f"{BLOCK_START}\n{section.strip()}\n{BLOCK_END}"
    start, end = body.find(BLOCK_START), body.find(BLOCK_END)
    if start != -1 and end > start:
        return body[:start] + block + body[end + len(BLOCK_END):]
    return (body.rstrip() + "\n\n" if body.strip() else "") + block + "\n"


def update_body(host, owner, repo, number, section, dry_run):
    path = f"repos/{owner}/{repo}/pulls/{number}"
    current = json.loads(gh(["api", "--hostname", host, path]))["body"] or ""
    new = splice(current, section)
    if dry_run or new == current:
        return {"changed": new != current, "dry_run": dry_run, "body": new}
    out = gh(["api", "--hostname", host, "--method", "PATCH", path, "--input", "-"],
             stdin=json.dumps({"body": new}))
    return {"changed": True, "url": json.loads(out).get("html_url")}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p_fetch = sub.add_parser("fetch")
    p_fetch.add_argument("pr", nargs="?")
    p_fetch.add_argument("--out")
    p_reply = sub.add_parser("reply")
    p_reply.add_argument("pr")
    p_reply.add_argument("replies")
    p_reply.add_argument("--dry-run", action="store_true")
    p_body = sub.add_parser("body")
    p_body.add_argument("pr")
    p_body.add_argument("section")
    p_body.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    target = resolve(args.pr)
    try:
        if args.command == "fetch":
            text = json.dumps(fetch(*target), indent=2)
            if args.out:
                with open(args.out, "w", encoding="utf-8") as handle:
                    handle.write(text + "\n")
                snapshot = json.loads(text)
                print(json.dumps({"out": args.out, "pr": snapshot["pr"]["url"],
                                  "viewer": snapshot["viewer"], "counts": snapshot["counts"],
                                  "ticket_candidates": snapshot["ticket_candidates"]}, indent=2))
            else:
                print(text)
        elif args.command == "reply":
            with open(args.replies, encoding="utf-8") as handle:
                result = reply(*target, json.load(handle), args.dry_run)
            print(json.dumps(result, indent=2))
            sys.exit(1 if result["failed"] else 0)
        else:
            with open(args.section, encoding="utf-8") as handle:
                print(json.dumps(update_body(*target, handle.read(), args.dry_run), indent=2))
    except GhError as err:
        print(f"gh failed: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
