#!/usr/bin/env python3
"""Pull-request plumbing for the refactor skill. Standard library plus the `gh` CLI.

  pr.py find [BRANCH]
      Print the open pull request whose head is BRANCH (default: the current
      branch) as JSON: {"found": true, "number", "url", "base_ref", "head_ref",
      "head_oid", "is_draft", "title"}, or {"found": false, "reason": "..."}.

  pr.py body <PR-URL | PR-number> <section.md> [--dry-run]
      Replace (or append) the <!-- refactor --> block of the PR description with
      the contents of section.md, leaving the rest of the description as written.

  pr.py create <BRANCH> <BASE> <TITLE> <summary.md> <section.md>
      Open a pull request from BRANCH into BASE. The description is summary.md
      followed by section.md inside the <!-- refactor --> block. Prints the same
      JSON as `find`.

Run it from inside the repository. Exit status: 0 on success, 1 when gh failed.
"""

import argparse
import json
import subprocess
import sys
import tempfile

BLOCK_START = "<!-- refactor:start -->"
BLOCK_END = "<!-- refactor:end -->"
FIELDS = "number,url,state,baseRefName,headRefName,headRefOid,isDraft,title"


def gh(args):
    return subprocess.run(["gh", *args], capture_output=True, text=True)


def find(branch):
    if not branch:
        current = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True)
        branch = current.stdout.strip()
        if not branch:
            return {"found": False, "reason": "detached HEAD: no branch to look up"}
    proc = gh(["pr", "view", branch, "--json", FIELDS])
    if proc.returncode != 0:
        error = proc.stderr.strip()
        if "no pull requests found" in error.lower() or "could not resolve" in error.lower():
            return {"found": False, "reason": f"no pull request for branch {branch}"}
        print(f"gh failed: {error}", file=sys.stderr)
        sys.exit(1)
    pr = json.loads(proc.stdout)
    if pr["state"] != "OPEN":
        return {"found": False, "reason": f"the pull request for {branch} is {pr['state'].lower()}: {pr['url']}"}
    return {"found": True, "number": pr["number"], "url": pr["url"], "base_ref": pr["baseRefName"],
            "head_ref": pr["headRefName"], "head_oid": pr["headRefOid"], "is_draft": pr["isDraft"],
            "title": pr["title"]}


def splice(body, section):
    """The PR description with its refactor block replaced, or appended."""
    block = f"{BLOCK_START}\n{section.strip()}\n{BLOCK_END}"
    start, end = body.find(BLOCK_START), body.find(BLOCK_END)
    if start != -1 and end > start:
        return body[:start] + block + body[end + len(BLOCK_END):]
    return (body.rstrip() + "\n\n" if body.strip() else "") + block + "\n"


def update_body(pr, section_path, dry_run):
    proc = gh(["pr", "view", pr, "--json", "body,url"])
    if proc.returncode != 0:
        print(f"gh failed: {proc.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    current = json.loads(proc.stdout)
    with open(section_path, encoding="utf-8") as handle:
        new = splice(current["body"] or "", handle.read())
    changed = new != (current["body"] or "")
    if dry_run or not changed:
        return {"changed": changed, "dry_run": dry_run, "body": new}
    with tempfile.NamedTemporaryFile("w", suffix=".md", encoding="utf-8") as tmp:
        tmp.write(new)
        tmp.flush()
        proc = gh(["pr", "edit", pr, "--body-file", tmp.name])
    if proc.returncode != 0:
        print(f"gh failed: {proc.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return {"changed": True, "url": current["url"]}


def create(branch, base, title, summary_path, section_path):
    with open(summary_path, encoding="utf-8") as handle:
        summary = handle.read()
    with open(section_path, encoding="utf-8") as handle:
        body = splice(summary, handle.read())
    with tempfile.NamedTemporaryFile("w", suffix=".md", encoding="utf-8") as tmp:
        tmp.write(body)
        tmp.flush()
        proc = gh(["pr", "create", "--base", base, "--head", branch, "--title", title, "--body-file", tmp.name])
    if proc.returncode != 0:
        print(f"gh failed: {proc.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return find(branch)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p_find = sub.add_parser("find")
    p_find.add_argument("branch", nargs="?")
    p_body = sub.add_parser("body")
    p_body.add_argument("pr")
    p_body.add_argument("section")
    p_body.add_argument("--dry-run", action="store_true")
    p_create = sub.add_parser("create")
    for name in ("branch", "base", "title", "summary", "section"):
        p_create.add_argument(name)
    args = parser.parse_args()
    if args.command == "find":
        print(json.dumps(find(args.branch), indent=2))
    elif args.command == "create":
        print(json.dumps(create(args.branch, args.base, args.title, args.summary, args.section), indent=2))
    else:
        print(json.dumps(update_body(args.pr, args.section, args.dry_run), indent=2))


if __name__ == "__main__":
    main()
