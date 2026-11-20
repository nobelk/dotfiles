#!/usr/bin/env python3
"""Check a design document written by the design-doc skill.

Checks, in order:
  sections  the eight required level-2 sections exist, in order, and are the only ones
  figures   every Mermaid diagram has a numbered caption and is cited in the text
  diagrams  every Mermaid diagram renders (mermaid-cli: `mmdc` on PATH, else `npx`)
  glossary  acronyms used are defined, and defined terms are used (warnings only)

The last line printed is `result: PASS`, `result: FAIL`, or `result: UNVERIFIED DIAGRAMS`.
Exit status: 0 = pass (warnings allowed), 1 = a check failed or the file could not be read,
2 = everything else passed but the diagrams could not be rendered here.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

SECTIONS = [
    "Introduction and overview",
    "System architecture",
    "Data design",
    "Interface design",
    "Component design",
    "User interface design",
    "Assumptions and dependencies",
    "Glossary of terms",
]
CAPTION = re.compile(r"^\s*\*{1,2}Figure (\d+)[.:]")
CITATION = re.compile(r"\bfig(?:ure|\.)?s?\.?\s+(\d+(?:\s*(?:,|and|or|to|through|-|–)\s*(?:and\s+)?\d+)*)", re.I)
ACRONYM = re.compile(r"\b[A-Z][A-Z0-9]{1,}s?\b")
FILENAME = re.compile(r"\b[\w.-]+\.(?:md|json|ya?ml|toml|txt|py|go|ts|js)\b")
IGNORED_ACRONYMS = {"OK", "ID", "IDS", "TBD", "TODO", "NA", "GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"}
LAUNCH_FAILURE = ("Failed to launch the browser", "No usable sandbox", "Could not find Chrome")

# Everything the checker starts must be gone when it exits, however it exits.
DEADLINE = time.monotonic() + 540  # under the 600 s cap of the Bash call that runs this script
LIVE: set = set()
STOPPING = threading.Event()
TIMEOUT = shutil.which("timeout")


def stop(processes):
    """SIGTERM each process group so mermaid-cli closes its browser, then SIGKILL what is left."""
    for sig, grace in ((signal.SIGTERM, 5), (signal.SIGKILL, 2)):
        for process in processes:
            try:
                os.killpg(process.pid, sig)
            except (ProcessLookupError, PermissionError):
                pass
        end = time.monotonic() + grace
        for process in processes:
            try:
                process.wait(timeout=max(0.0, end - time.monotonic()))
            except subprocess.TimeoutExpired:
                pass


def interrupted(signum, _frame):
    STOPPING.set()
    stop(list(LIVE))
    sys.exit(128 + signum)


def run(command, limit):
    """Run a command in its own process group, bounded twice: by `timeout`, and by this process."""
    limit = int(min(limit, DEADLINE - time.monotonic()))
    if STOPPING.is_set():
        return 124, "", "interrupted"
    if limit <= 0:
        return 124, "", "the checker ran out of time"
    if TIMEOUT:  # the child keeps its own upper bound even if this process is killed outright
        command = [TIMEOUT, "-k", "5", str(limit)] + command
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    LIVE.add(process)
    try:
        out, err = process.communicate(timeout=limit + 10)
    except subprocess.TimeoutExpired:
        stop([process])
        process.communicate()
        return 124, "", f"timed out after {limit}s"
    finally:
        LIVE.discard(process)
    if TIMEOUT and process.returncode in (124, 137):
        return 124, out, f"timed out after {limit}s"
    return process.returncode, out, err


def normalize(heading: str) -> str:
    return re.sub(r"^\d+[.)]?\s*", "", heading.strip()).strip().lower()


def parse(text: str):
    """Return (h2 headings, mermaid blocks, prose lines) with fenced code removed from prose."""
    headings, blocks, prose = [], [], []
    fence, lang, start, buf = None, "", 0, []
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if fence is None:
            opened = re.match(r"^(`{3,}|~{3,})\s*([\w-]*)", stripped)
            if opened:
                fence, lang, start, buf = opened.group(1), opened.group(2).lower(), number, []
                continue
            if line.startswith("## "):
                headings.append((number, line[3:].strip()))
            prose.append((number, line))
        elif stripped.startswith(fence) and stripped.strip(fence[0]) == "":
            if lang == "mermaid":
                blocks.append({"line": start, "end": number, "source": "\n".join(buf) + "\n"})
            fence = None
        else:
            buf.append(line)
    return headings, blocks, prose


def check_sections(headings):
    problems, found = [], [normalize(title) for _, title in headings]
    wanted = [name.lower() for name in SECTIONS]
    for name in SECTIONS:
        if name.lower() not in found:
            problems.append(f'missing section "## {name}"')
    present = [name for name in found if name in wanted]
    if not problems and present != wanted:
        problems.append("sections are out of order or repeated; expected: " + " > ".join(SECTIONS))
    for _, title in headings:
        if normalize(title) not in wanted:
            problems.append(f'unexpected level-2 heading "{title}": make it a subsection of one of the eight sections')
    return problems


def cited_figures(body):
    cited = set()
    for match in CITATION.finditer(body):
        cited.update(int(n) for n in re.findall(r"\d+", match.group(1)))
        for first, last in re.findall(r"(\d+)\s*(?:to|through|-|–)\s*(\d+)", match.group(1)):
            cited.update(range(int(first), int(last) + 1))
    return cited


def check_figures(blocks, prose):
    if not blocks:
        return ["the document has no Mermaid diagrams"]
    problems = []
    lines = dict(prose)
    ordered = sorted(lines)
    for index, block in enumerate(blocks, 1):
        following = next((lines[n] for n in ordered if n > block["end"] and lines[n].strip()), "")
        match = CAPTION.match(following)
        block["figure"] = int(match.group(1)) if match else None
        if not match:
            problems.append(f'line {block["line"]}: diagram has no caption below it (expected "*Figure {index}. ...*")')
        elif block["figure"] != index:
            problems.append(f'line {block["line"]}: caption says Figure {block["figure"]}, expected Figure {index}')
    cited = cited_figures("\n".join(line for _, line in prose if not CAPTION.match(line)))
    for block in blocks:
        if block["figure"] and block["figure"] not in cited:
            problems.append(f'Figure {block["figure"]} is never cited in the text (cite it as "Figure {block["figure"]}")')
    return problems


def glossary_terms(headings, prose):
    """Terms are the first cell of each table row under the glossary heading."""
    start = next((n for n, title in headings if normalize(title) == SECTIONS[-1].lower()), None)
    if start is None:
        return None, []
    end = min((n for n, _ in headings if n > start), default=10**9)
    terms = []
    for number, line in prose:
        if start < number < end and line.strip().startswith("|"):
            term = re.sub(r"[*`_]", "", line.strip().strip("|").split("|")[0]).strip()
            if term and term.lower() != "term" and not re.fullmatch(r"[\s:-]+", term):
                terms.append(term)
    return (start, end), terms


def check_glossary(headings, blocks, prose):
    span, terms = glossary_terms(headings, prose)
    if span is None:
        return [], []
    if not terms:
        return ["the glossary has no table rows (expected a | Term | Definition | table)"], []
    body = "\n".join(re.sub(r"`[^`]*`", " ", line) for n, line in prose if not span[0] <= n < span[1])
    flowcharts = [b["source"] for b in blocks if b["source"].lstrip().startswith(("flowchart", "graph"))]
    labels = "\n".join(label for source in flowcharts for label in re.findall(r'"([^"]*)"', source))
    scanned = FILENAME.sub(" ", body + "\n" + labels)
    words = set(re.findall(r"[A-Za-z0-9]+", " ".join(terms)))
    used = {m.group(0) for m in ACRONYM.finditer(scanned) if sum(c.isupper() for c in m.group(0)) >= 2}
    missing = sorted(a for a in used if a not in words and a.rstrip("s") not in words and a.upper() not in IGNORED_ACRONYMS)
    everything = (body + "\n" + "\n".join(b["source"] for b in blocks)).lower()
    unused = [t for t in terms if re.sub(r"\s*\(.*?\)", "", t).strip().lower() not in everything]
    notes = []
    if missing:
        notes.append("possible acronyms not in the glossary: " + ", ".join(missing))
    if unused:
        notes.append("glossary terms never used in the text: " + ", ".join(unused))
    return [], notes


def find_renderer(allow_install):
    if shutil.which("mmdc"):
        return ["mmdc"], None
    if allow_install and shutil.which("npx"):
        return ["npx", "-y", "@mermaid-js/mermaid-cli"], None
    return None, "mermaid-cli (mmdc) is not installed" + (", and npx is missing" if allow_install else "; --no-install given")


def first_error(stderr):
    lines = []
    for line in stderr.strip().splitlines():
        if re.match(r"^\s+at |^Parser\.", line):
            break
        if line.strip():
            lines.append(line.rstrip())
    return " / ".join(lines[:5]) or "no error output"


def check_diagrams(blocks, allow_install):
    """Return (problems, unavailable_reason)."""
    renderer, reason = find_renderer(allow_install)
    if renderer is None:
        return [], reason
    code, _, err = run(renderer + ["--version"], 480)  # the first npx run downloads the tool
    if code != 0:
        return [], "mermaid-cli did not start: " + first_error(err)
    with tempfile.TemporaryDirectory(prefix="design-doc-") as tmp:
        config = Path(tmp, "puppeteer.json")
        config.write_text(json.dumps({"args": ["--no-sandbox"]}))

        def render(job, sandbox=True):
            index, block = job
            source, target = Path(tmp, f"fig-{index}.mmd"), Path(tmp, f"fig-{index}.svg")
            source.write_text(block["source"])
            command = renderer + ["-q", "-i", str(source), "-o", str(target)] + ([] if sandbox else ["-p", str(config)])
            code, _, err = run(command, 120)
            ok = code == 0 and target.exists() and target.stat().st_size > 0
            return index, block, ok, err

        jobs = list(enumerate(blocks, 1))
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(render, jobs))
            blocked = [(i, b) for i, b, ok, err in results if not ok and any(m in err for m in LAUNCH_FAILURE)]
            if blocked:  # the browser sandbox is unavailable here; these are local diagrams, so retry without it
                retried = {r[0]: r for r in pool.map(lambda job: render(job, sandbox=False), blocked)}
                results = [retried.get(r[0], r) for r in results]
    if results and all(not ok and any(m in err for m in LAUNCH_FAILURE) for _, _, ok, err in results):
        return [], "the headless browser would not start: " + first_error(results[0][3])
    problems = [
        f'Figure {block.get("figure") or index} (line {block["line"]}): {first_error(err)}'
        for index, block, ok, err in results
        if not ok
    ]
    return problems, None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("document", type=Path)
    parser.add_argument("--no-render", action="store_true", help="skip rendering the diagrams")
    parser.add_argument("--no-install", action="store_true", help="render only with an mmdc already on PATH")
    args = parser.parse_args()
    for signum in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
        signal.signal(signum, interrupted)

    print(f"design-doc check: {args.document}")
    try:
        text = args.document.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as error:
        print(f"  - cannot read the document: {error}")
        print("result: FAIL")
        return 1
    headings, blocks, prose = parse(text)
    failed = False

    def report(name, problems, notes=(), ok=""):
        nonlocal failed
        failed = failed or bool(problems)
        print(f"{name:<9} {'FAIL' if problems else 'WARN' if notes else 'OK'}{'' if problems or notes or not ok else ' (' + ok + ')'}")
        for line in list(problems) + list(notes):
            print(f"  - {line}")

    report("sections", check_sections(headings), ok=f"{len(SECTIONS)} of {len(SECTIONS)}, in order")
    report("figures", check_figures(blocks, prose), ok=f"{len(blocks)} captioned and cited")
    unavailable = None
    if args.no_render:
        unavailable = "--no-render given"
    elif blocks:
        problems, unavailable = check_diagrams(blocks, not args.no_install)
        if unavailable is None:
            report("diagrams", problems, ok=f"{len(blocks)} of {len(blocks)} render")
    if unavailable:
        print(f"diagrams  UNVERIFIED ({unavailable})")
    report("glossary", *check_glossary(headings, blocks, prose))
    print("result:", "FAIL" if failed else "UNVERIFIED DIAGRAMS" if unavailable else "PASS")
    return 1 if failed else 2 if unavailable else 0


if __name__ == "__main__":
    sys.exit(main())
