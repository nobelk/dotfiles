#!/usr/bin/env python3
"""Check a product requirements document written by the prd skill.

Checks, in order:
  sections      the eleven required level-2 sections exist, in order, and are the only ones
  header        the header table fills in status, date, target release, participants, system name, sources
  placeholders  no <angle-bracket> template guidance is left
  ids           every goal, story, requirement, assumption, and question has a well-formed, unique ID
  ears          every functional and non-functional requirement is one well-formed EARS sentence
  fields        priorities and verification methods use the allowed values; stories use the story form
  trace         every trace points at an ID that exists; goals and stories nothing traces to (warnings)
  wording       vague words, non-EARS modal verbs, unmeasured targets, no unwanted behaviour (warnings only)
  glossary      acronyms and the system name are defined, defined terms are used, rows sorted (warnings only)

The last line printed is `result: PASS` or `result: FAIL`.
Exit status: 0 = pass (warnings allowed), 1 = a check failed or the file could not be read.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

SECTIONS = [
    "Background and strategic fit",
    "Goals and success metrics",
    "Users",
    "Scope",
    "User stories",
    "Functional requirements",
    "Non-functional requirements",
    "User interaction and design",
    "Assumptions, constraints, and dependencies",
    "Open questions",
    "Glossary",
]
# Section number -> (ID prefix, columns its ID table must have).
ID_TABLES = {
    2: ("G", ["id", "goal", "metric", "baseline", "target"]),
    5: ("US", ["id", "user story", "priority", "goals"]),
    6: ("FR", ["id", "requirement", "priority", "traces to", "verification"]),
    7: ("NFR", ["id", "requirement", "priority", "traces to", "verification"]),
    9: ("A", ["id", "assumption", "if it is wrong"]),
    10: ("Q", ["id", "question", "blocks", "owner", "needed by"]),
}
REQUIRED_TABLES = {2, 5, 6, 7}
HEADER_KEYS = ["status", "date", "target release", "participants", "system name", "sources"]
PRIORITIES = {"must", "should", "could"}
VERIFICATIONS = {"test", "demonstration", "inspection", "analysis"}

ANY_ID = re.compile(r"\b(?:NFR|FR|US|G|A|Q)\d+\b")
KEYWORDS = ["WHERE", "WHILE", "WHEN", "IF", "THEN"]
KEYWORD = re.compile(r"\b(WHERE|WHILE|WHEN|IF|THEN)\b")
LOWER_KEYWORD = re.compile(r"(?:^|,)\s*(where|while|when|if|then)\b", re.I)
QUOTED = re.compile(r'"[^"]*"|“[^”]*”|‘[^’]*’|(?<!\w)\'[^\']+\'(?!\w)')
PLACEHOLDER = re.compile(r"<[A-Za-z][^<>\n]*>")
HTML_TAG = re.compile(r"</?(?:br|sup|sub|a|b|i|em|strong|details|summary|kbd|img|span|div|p)\b", re.I)
VAGUE = re.compile(
    r"\b(?:fast|faster|quick|quickly|slow|easy|easily|simple|simply|user[- ]friendly|intuitive|robust|"
    r"seamless(?:ly)?|efficient(?:ly)?|flexible|scalable|appropriate(?:ly)?|adequate(?:ly)?|"
    r"sufficient(?:ly)?|reasonabl[ey]|as needed|as required|as appropriate|if possible|where possible|"
    r"when possible|etc|and/or|minimi[sz]e|maximi[sz]e|optimi[sz]e|normally|usually|typically|"
    r"generally|(?:near[- ])?real[- ]time|state[- ]of[- ]the[- ]art)\b",
    re.I,
)
VAGUE_VERB = re.compile(r"\bSHALL\s+(?:NOT\s+)?(support|handle|manage|be able to)\b")
MODAL = re.compile(r"\b(should|may|might|will|must|could)\b")
ACRONYM = re.compile(r"\b[A-Z][A-Z0-9]{1,}s?\b")
FILENAME = re.compile(r"\b[\w.-]+\.(?:md|json|ya?ml|toml|txt|py|go|ts|js)\b")
URL = re.compile(r"https?://\S+")
IGNORED_ACRONYMS = {"OK", "ID", "IDS", "TBD", "TODO", "NA", "README", "AND", "OR", "NOT", "SHALL", *KEYWORDS}
PATTERNS = {"WHEN": "event-driven", "WHILE": "state-driven", "WHERE": "optional feature", "IF": "unwanted behaviour"}
PATTERN_ORDER = ["ubiquitous", "event-driven", "state-driven", "unwanted behaviour", "optional feature", "complex"]


def normalize(heading: str) -> str:
    return re.sub(r"^\d+[.)]?\s*", "", heading.strip()).strip().lower()


def plain(cell: str) -> str:
    """Drop Markdown emphasis and code ticks, keeping the text."""
    return re.sub(r"[*`]", "", cell).strip()


def mask(text: str) -> str:
    """Hide quoted text (messages, labels) so words inside it are not read as keywords or vague words."""
    return QUOTED.sub("«q»", text)


def split_row(line: str) -> list[str]:
    s = line.strip()
    s = s[1:] if s.startswith("|") else s
    s = s[:-1] if s.endswith("|") and not s.endswith("\\|") else s
    return [part.strip().replace("\\|", "|") for part in re.split(r"(?<!\\)\|", s)]


def parse(text: str):
    """Return (h2 headings, prose lines, tables). Fenced code is skipped.

    A prose line is (number, text, section) where section is the 1-based index into SECTIONS of the
    level-2 heading it sits under (0 before the first one, None under an unknown heading).
    A table is {"line", "section", "header": [lowercased names], "rows": [(number, cells)]}.
    """
    headings, prose, tables = [], [], []
    section, fence, table = 0, None, None
    wanted = [name.lower() for name in SECTIONS]
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if fence is not None:
            if stripped.startswith(fence) and stripped.strip(fence[0]) == "":
                fence = None
            continue
        opened = re.match(r"^(`{3,}|~{3,})", stripped)
        if opened:
            fence, table = opened.group(1), None
            continue
        if line.startswith("## "):
            title = line[3:].strip()
            headings.append((number, title))
            section = wanted.index(normalize(title)) + 1 if normalize(title) in wanted else None
        prose.append((number, line, section))
        if stripped.startswith("|"):
            cells = split_row(stripped)
            if table is None:
                table = {"line": number, "section": section, "header": [plain(c).lower() for c in cells], "rows": []}
                tables.append(table)
            elif not all(re.fullmatch(r":?-{1,}:?", c) for c in cells if c):
                table["rows"].append((number, cells))
        else:
            table = None
    return headings, prose, tables


def cell(table, row, column):
    try:
        return row[1][table["header"].index(column)]
    except (ValueError, IndexError):
        return ""


def check_sections(headings):
    problems, found = [], [normalize(title) for _, title in headings]
    wanted = [name.lower() for name in SECTIONS]
    for name in SECTIONS:
        if name.lower() not in found:
            problems.append(f'missing section "## {name}"')
    present = [name for name in found if name in wanted]
    if not problems and present != wanted:
        problems.append("sections are out of order or repeated; expected: " + " > ".join(SECTIONS))
    for number, title in headings:
        if normalize(title) not in wanted:
            problems.append(f'line {number}: unexpected level-2 heading "{title}": make it a subsection of one of the eleven')
    return problems


def header_fields(tables):
    table = next((t for t in tables if t["section"] == 0), None)
    if table is None:
        return None
    fields = {}
    for row in [(table["line"], [plain(c) for c in table["header"]])] + table["rows"]:
        if len(row[1]) >= 2:
            fields[plain(row[1][0]).lower().rstrip(":")] = plain(row[1][1])
    return fields


def system_names(fields):
    value = (fields or {}).get("system name", "")
    if not value or PLACEHOLDER.search(value):
        return []
    names = [re.sub(r"^the\s+", "", part.strip(), flags=re.I) for part in re.split(r"[;,]", value)]
    return [name for name in names if name]


def check_header(fields):
    if fields is None:
        return ["no header table before section 1 (expected | **Status** | ... | rows)"], []
    problems, notes = [], []
    for key in HEADER_KEYS:
        if not fields.get(key):
            problems.append(f'header has no "{key.capitalize()}" value')
    date = fields.get("date", "")
    if date and not PLACEHOLDER.search(date) and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        notes.append(f'Date "{date}" is not YYYY-MM-DD')
    return problems, notes


def check_placeholders(prose):
    hits = []
    for number, line, _ in prose:
        for match in PLACEHOLDER.finditer(re.sub(r"`[^`]*`", " ", line)):
            text = match.group(0)
            if not HTML_TAG.match(text) and "://" not in text and "@" not in text:
                hits.append(f"line {number}: {text}")
    if len(hits) > 12:
        hits = hits[:12] + [f"... and {len(hits) - 12} more"]
    return ["template guidance left in the document: " + hit for hit in hits]


def id_tables(tables):
    """Yield (section, prefix, columns, table) for each table that holds IDs."""
    for table in tables:
        if table["section"] not in ID_TABLES or "id" not in table["header"]:
            continue
        prefix, columns = ID_TABLES[table["section"]]
        if prefix in ("FR", "NFR") and "requirement" not in table["header"]:
            continue  # a decision or state table that a requirement cites
        yield table["section"], prefix, columns, table


def check_ids(tables):
    problems, items = [], {}
    seen_sections = set()
    for section, prefix, columns, table in id_tables(tables):
        seen_sections.add(section)
        for column in columns:
            if column not in table["header"]:
                problems.append(f'line {table["line"]}: table in section {section} has no "{column}" column')
        for row in table["rows"]:
            number = row[0]
            ident = plain(cell(table, row, "id"))
            if not re.fullmatch(rf"{prefix}\d+", ident):
                problems.append(f'line {number}: ID "{ident}" in section {section} should look like {prefix}1')
                continue
            if ident in items:
                problems.append(f"line {number}: {ident} is already used on line {items[ident]['line']}")
                continue
            items[ident] = {"line": number, "section": section, "table": table, "row": row}
            for column in columns[1:]:
                if column in table["header"] and not plain(cell(table, row, column)):
                    problems.append(f'line {number} {ident}: "{column}" is empty')
    for section in sorted(REQUIRED_TABLES - seen_sections):
        prefix, columns = ID_TABLES[section]
        problems.append(f"section {section} has no table of {prefix} items (| " + " | ".join(c.capitalize() for c in columns) + " |)")
    return problems, items


def ears(text: str, names: list[str]):
    """Return (pattern or None, problems) for one requirement sentence."""
    s = mask(plain(text))
    shalls = len(re.findall(r"\bSHALL\b", s))
    if not shalls:
        return None, ["write SHALL in capitals" if re.search(r"\bshall\b", s, re.I) else
                      "no SHALL: every requirement reads '... the <system name> SHALL <response>.'"]
    problems = []
    if shalls > 1:
        problems.append(f"{shalls} SHALLs: one response per requirement, so split it into separate rows")
    left, right = re.split(r"\bSHALL\b", s, maxsplit=1)
    response = re.sub(r"^\s*NOT\b", "", right).strip(" .")
    if not response:
        problems.append("nothing after SHALL: state the response")
    late = KEYWORD.findall(right)
    if late:
        problems.append(f"{', '.join(late)} after SHALL: conditions go before the system name")
    lowercase = [m.group(1) for m in LOWER_KEYWORD.finditer(left) if m.group(1) != m.group(1).upper()]
    for word in lowercase:
        problems.append(f'"{word}" is an EARS keyword here: write it in capitals')
    if lowercase:
        return None, problems  # the clause structure can't be read until the keywords are fixed
    found = [(m.group(1), m.start(), m.end()) for m in KEYWORD.finditer(left)]
    words = [w for w, _, _ in found]
    for word, count in Counter(words).items():
        if count > 1:
            problems.append(f"{word} appears {count} times: join its conditions with 'and' in one clause, or cite a decision table")
    if [KEYWORDS.index(w) for w in words] != sorted(KEYWORDS.index(w) for w in words):
        problems.append("clauses out of order: WHERE, then WHILE, then WHEN, then IF ... THEN, then the system name")
    if "IF" in words and "THEN" not in words:
        problems.append("IF without THEN: write 'IF <condition>, THEN the <system name> SHALL ...'")
    if "THEN" in words and "IF" not in words:
        problems.append("THEN without IF: THEN belongs only to IF ... THEN")

    subject = None
    if not found:
        subject = left.strip()
    else:
        if left[: found[0][1]].strip():
            problems.append("text before the first keyword: start the sentence with the keyword")
        for index, (word, _, end) in enumerate(found):
            last = index == len(found) - 1
            body = left[end : found[index + 1][1]] if not last else left[end:]
            if not last:
                if not body.strip(" ,"):
                    problems.append(f"the {word} clause is empty")
                elif not body.rstrip().endswith(","):
                    problems.append(f"end the {word} clause with a comma")
            elif word == "THEN":
                subject = body.strip()
            elif "," not in body:
                problems.append(f"no comma between the {word} clause and the system name")
            else:
                condition, subject = body.rsplit(",", 1)
                subject = subject.strip()
                if not condition.strip():
                    problems.append(f"the {word} clause is empty")
    if subject is not None and names:
        if not re.fullmatch(r"(?:[Tt]he\s+)?(?:" + "|".join(re.escape(n) for n in names) + r")", subject):
            shown = f'"{subject}"' if subject else "nothing"
            problems.append(f"the subject is {shown}, not the declared system name ({' / '.join(names)})")

    kinds = {w for w in words if w != "THEN"}
    pattern = "ubiquitous" if not kinds else "complex" if len(kinds) > 1 else PATTERNS[next(iter(kinds))]
    return (None if problems else pattern), problems


def requirements(items):
    for ident, item in items.items():
        if item["section"] in (6, 7):
            yield ident, item, cell(item["table"], item["row"], "requirement")


def check_ears(items, names):
    problems, counts = [], Counter()
    if not names:
        problems.append("cannot check subjects: the header names no System name")
    for ident, item, text in requirements(items):
        if not plain(text):
            continue  # reported by ids
        pattern, found = ears(text, names)
        problems.extend(f"line {item['line']} {ident}: {problem}" for problem in found)
        if pattern:
            counts[pattern] += 1
    summary = ", ".join(f"{counts[p]} {p}" for p in PATTERN_ORDER if counts[p])
    return problems, counts, summary


def check_fields(items):
    problems, notes = [], []
    for ident, item in items.items():
        table, row = item["table"], item["row"]
        if item["section"] in (5, 6, 7):
            priority = plain(cell(table, row, "priority"))
            if priority and priority.lower() not in PRIORITIES:
                hint = "; Won't items belong in 4.2 What we're not doing" if "won" in priority.lower() else ""
                problems.append(f'line {item["line"]} {ident}: priority "{priority}" is not Must, Should, or Could{hint}')
        if item["section"] in (6, 7):
            methods = plain(cell(table, row, "verification"))
            for method in filter(None, (m.strip() for m in re.split(r",|/|\band\b", methods))):
                if method.lower() not in VERIFICATIONS:
                    problems.append(f'line {item["line"]} {ident}: verification "{method}" is not Test, Demonstration, Inspection, or Analysis')
        if item["section"] == 5:
            story = plain(cell(table, row, "user story"))
            if story and not re.match(r"As an? .+?, I want .+?, so that .+", story, re.I):
                notes.append(f'line {item["line"]} {ident}: not in the form "As a <user>, I want <capability>, so that <benefit>."')
    return problems, notes


def check_trace(items):
    problems, notes = [], []
    traced = Counter()
    rules = {5: ("goals", {"G"}), 6: ("traces to", {"G", "US"}), 7: ("traces to", {"G", "US"})}
    for ident, item in items.items():
        if item["section"] not in rules and item["section"] != 10:
            continue
        column, kinds = rules.get(item["section"], ("blocks", None))
        value = plain(cell(item["table"], item["row"], column))
        targets = ANY_ID.findall(value)
        if item["section"] in rules and value and not targets:
            problems.append(f'line {item["line"]} {ident}: "{column}" names no ID ({" or ".join(sorted(kinds))}...)')
        for target in targets:
            kind = re.match(r"[A-Z]+", target).group(0)
            if target not in items:
                problems.append(f"line {item['line']} {ident}: traces to {target}, which does not exist")
            elif kinds and kind not in kinds:
                own = re.match(r"[A-Z]+", ident).group(0)
                problems.append(f"line {item['line']} {ident}: traces to {target}; {own} items trace to {' or '.join(sorted(kinds))} IDs")
            elif item["section"] != 10:
                traced[target] += 1
    for ident, item in items.items():
        if item["section"] == 2 and not traced[ident]:
            notes.append(f"{ident}: no story or requirement traces to this goal, so nothing delivers it")
        if item["section"] == 5 and not any(
            target == ident for other, o in items.items() if o["section"] == 6
            for target in ANY_ID.findall(plain(cell(o["table"], o["row"], "traces to")))
        ):
            notes.append(f"{ident}: no functional requirement traces to this story")
    return problems, notes


def check_wording(items, counts):
    notes = []
    for ident, item, text in requirements(items):
        s = mask(plain(text))
        vague = sorted({m.group(0).lower() for m in VAGUE.finditer(s)} | {m.group(1) for m in VAGUE_VERB.finditer(s)})
        if vague:
            notes.append(f"line {item['line']} {ident}: vague: {', '.join(vague)} - say the number or the behaviour")
        modals = sorted(set(MODAL.findall(s)))
        if modals:
            notes.append(f"line {item['line']} {ident}: {', '.join(modals)}: SHALL is the only modal verb; priority goes in its column")
        if item["section"] == 7 and not re.search(r"\d", s) and not re.search(r"\bSHALL\s+NOT\b", s):
            notes.append(f"line {item['line']} {ident}: no number: is this target measurable?")
    for ident, item in items.items():
        if item["section"] == 2:
            target = plain(cell(item["table"], item["row"], "target"))
            if target and not re.search(r"\d", target):
                notes.append(f"line {item['line']} {ident}: target has no number")
    if counts["event-driven"] and not counts["unwanted behaviour"] and not counts["complex"]:
        notes.append("no IF ... THEN requirement: the failure cases (invalid input, errors, dependencies down) are probably missing")
    return notes


def check_glossary(prose, tables, names):
    rows = [row for t in tables if t["section"] == 11 for row in t["rows"]]
    if not rows:
        return ["the glossary has no table rows (expected a | Term | Definition | table)"], []
    terms = [plain(cells[0]) for _, cells in rows if cells and plain(cells[0])]
    body = "\n".join(
        FILENAME.sub(" ", URL.sub(" ", mask(re.sub(r"`[^`]*`", " ", line))))
        for _, line, section in prose if section != 11
    )
    words = set(re.findall(r"[A-Za-z0-9]+", " ".join(terms)))
    used = {m.group(0) for m in ACRONYM.finditer(body) if sum(c.isupper() for c in m.group(0)) >= 2}
    missing = sorted(
        a for a in used
        if a not in words and a.rstrip("s") not in words and a.upper() not in IGNORED_ACRONYMS and not ANY_ID.fullmatch(a)
    )
    lowered = body.lower()
    unused = [t for t in terms if re.sub(r"\s*\(.*?\)", "", t).strip().lower() not in lowered]
    defined = {t.lower() for t in terms}
    notes = []
    for name in names:
        if name.lower() not in defined and f"the {name.lower()}" not in defined:
            notes.append(f'the system name "{name}" has no glossary row')
    if missing:
        notes.append("possible acronyms not in the glossary: " + ", ".join(missing))
    if unused:
        notes.append("glossary terms never used in the text: " + ", ".join(unused))
    if [t.lower() for t in terms] != sorted(t.lower() for t in terms):
        notes.append("glossary rows are not in alphabetical order")
    return [], notes


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("document", type=Path)
    args = parser.parse_args()
    print(f"prd check: {args.document}")
    try:
        text = args.document.read_text(encoding="utf-8")
    except OSError as error:
        print(f"  - cannot read the document: {error}")
        print("result: FAIL")
        return 1

    failed = False

    def report(name, problems, notes=(), ok=""):
        nonlocal failed
        failed |= bool(problems)
        status = "FAIL" if problems else "WARN" if notes else "OK"
        print(f"{name:<12} {status}{'' if problems or notes or not ok else ' (' + ok + ')'}")
        for line in list(problems) + list(notes):
            print(f"  - {line}")

    headings, prose, tables = parse(text)
    fields = header_fields(tables)
    names = system_names(fields)
    report("sections", check_sections(headings))
    report("header", *check_header(fields), ok=f"system name: {' / '.join(names)}" if names else "")
    report("placeholders", check_placeholders(prose))
    id_problems, items = check_ids(tables)
    kinds = Counter(re.match(r"[A-Z]+", i).group(0) for i in items)
    report("ids", id_problems, ok=", ".join(f"{kinds[k]} {k}" for k in ("G", "US", "FR", "NFR", "A", "Q") if kinds[k]))
    ears_problems, counts, summary = check_ears(items, names)
    report("ears", ears_problems, ok=summary)
    report("fields", *check_fields(items))
    report("trace", *check_trace(items))
    report("wording", [], check_wording(items, counts))
    report("glossary", *check_glossary(prose, tables, names))
    print("result:", "FAIL" if failed else "PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
