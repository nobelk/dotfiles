#!/usr/bin/env python3
"""Build an offline sandbox for testing the refactor skill.

  build_sandbox.py <case-dir> [--on-main] [--no-pr]

Creates <case-dir>/{repo,remote.git,bin/gh,gh-state/state.json}: a small layered
Python project whose feature branch works but breaks the declared architecture and
several clean-code rules, a bare remote to push to, and a fake `gh` serving the PR.
--on-main leaves the clone on main (the branch is not checked out anywhere);
--no-pr starts with no pull request for the branch.
"""

import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BRANCH = "feat/ORD-31-quote"

MAIN_FILES = {
    ".gitignore": "__pycache__/\n",
    "Makefile": (
        ".PHONY: lint arch test\n\n"
        "lint:\n\tpython3 -m compileall -q orders tests tools\n\n"
        "arch:\n\tpython3 tools/check_layers.py\n\n"
        "test:\n\tpython3 -m unittest discover -s tests\n"
    ),
    "CLAUDE.md": (
        "# orders\n\n"
        "- Architecture: `docs/architecture.md`. `make arch` enforces its import rules.\n"
        "- Gates: `make lint`, `make arch`, `make test`, run from the repo root. There is no formatter and no build step.\n"
        "- The CLI (`python3 -m orders <command> '<json>' [flags]`) is the public interface: its output for a given input is the contract. Python names are internal and may change.\n"
        "- Tests use `unittest`: one behavior per test, a fake for each port (see `tests/test_total.py`), and no file or network I/O in domain or app tests.\n"
        "- Commits follow Conventional Commits with the ticket key in parentheses at the end, e.g. `feat(total): add order total (ORD-12)`.\n"
        "- Behavior is specified in `specs/<ticket>-<name>/requirements.md`.\n"
    ),
    "docs/architecture.md": (
        "# Architecture\n\n"
        "`orders` is a ports-and-adapters (hexagonal) application with three layers and a composition root.\n\n"
        "1. `orders/domain/` holds the business rules: pricing, validation, invariants. It is pure: no I/O, no configuration, and it imports only `orders.domain`.\n"
        "2. `orders/app/` holds the use cases. A use case orchestrates domain functions and talks to the outside world through ports. It imports only `orders.domain` and `orders.app`.\n"
        "3. Ports are `Protocol` classes in `orders/app/ports.py`, defined by what the use cases need. Use cases receive their ports through the constructor.\n"
        "4. `orders/adapters/` implements ports and translates between the outside world (CLI text, files) and domain objects. Adapters contain no business rules.\n"
        "5. `orders/__main__.py` is the composition root: it builds adapters, injects them into use cases, and dispatches commands. Configuration values (file paths, tables) are defined here and passed down.\n"
        "6. `make arch` (`tools/check_layers.py`) checks rules 1 and 2 by reading imports. It cannot see where a rule lives, so placement is a review matter.\n"
    ),
    "tools/check_layers.py": '''"""Fail when a layer imports from a layer it may not depend on (docs/architecture.md, rules 1 and 2)."""

import ast
import pathlib
import sys

ALLOWED = {
    "orders/domain": ("orders.domain",),
    "orders/app": ("orders.domain", "orders.app"),
}


def imported_modules(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module


def violations():
    for layer, allowed in ALLOWED.items():
        for path in sorted(pathlib.Path(layer).rglob("*.py")):
            for module in imported_modules(path):
                if module.startswith("orders.") and not module.startswith(allowed):
                    yield f"{path}: {layer} must not import {module}"


def main():
    found = list(violations())
    for line in found:
        print(line)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
''',
    "data/tax_rates.json": '{"DE": 0.19, "FR": 0.2, "default": 0.0}\n',
    "orders/__init__.py": "",
    "orders/domain/__init__.py": "",
    "orders/app/__init__.py": "",
    "orders/adapters/__init__.py": "",
    "orders/domain/model.py": '''from dataclasses import dataclass


@dataclass(frozen=True)
class Line:
    sku: str
    qty: int
    unit_price: float


@dataclass(frozen=True)
class Country:
    code: str


@dataclass(frozen=True)
class Address:
    country: Country


@dataclass(frozen=True)
class Customer:
    address: Address


@dataclass(frozen=True)
class Order:
    lines: tuple
    customer: Customer

    @property
    def country_code(self):
        return self.customer.address.country.code
''',
    "orders/domain/totals.py": '''def subtotal(order):
    return sum(line.qty * line.unit_price for line in order.lines)


def with_tax(amount, rate):
    return amount * (1 + rate)
''',
    "orders/app/ports.py": '''from typing import Protocol


class TaxRates(Protocol):
    def rate_for(self, country_code: str) -> float: ...
''',
    "orders/app/total.py": '''from orders.domain.totals import subtotal, with_tax


class TotalOrder:
    def __init__(self, tax_rates):
        self._tax_rates = tax_rates

    def run(self, order):
        rate = self._tax_rates.rate_for(order.country_code)
        return round(with_tax(subtotal(order), rate), 2)
''',
    "orders/adapters/rates_file.py": '''import json


class FileTaxRates:
    def __init__(self, path):
        self._path = path

    def rate_for(self, country_code):
        with open(self._path, encoding="utf-8") as handle:
            rates = json.load(handle)
        return rates.get(country_code, rates["default"])
''',
    "orders/adapters/cli.py": '''import json

from orders.domain.model import Address, Country, Customer, Line, Order


def parse_order(text):
    data = json.loads(text)
    lines = tuple(Line(item["sku"], item["qty"], item["unit_price"]) for item in data["items"])
    return Order(lines, Customer(Address(Country(data["country"]))))


def format_total(total):
    return json.dumps({"total": total, "currency": "EUR"})
''',
    "orders/__main__.py": '''import sys

from orders.adapters.cli import format_total, parse_order
from orders.adapters.rates_file import FileTaxRates
from orders.app.total import TotalOrder

TAX_RATES_PATH = "data/tax_rates.json"


def main(argv):
    command, payload = argv[1], argv[2]
    if command == "total":
        use_case = TotalOrder(FileTaxRates(TAX_RATES_PATH))
        print(format_total(use_case.run(parse_order(payload))))
        return 0
    print(f"unknown command: {command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
''',
    "tests/__init__.py": "",
    "tests/test_total.py": '''import unittest

from orders.app.total import TotalOrder
from orders.domain.model import Address, Country, Customer, Line, Order


class FakeTaxRates:
    def __init__(self, rates):
        self._rates = rates

    def rate_for(self, country_code):
        return self._rates[country_code]


def order_for(country_code, *lines):
    return Order(tuple(lines), Customer(Address(Country(country_code))))


class TotalOrderTest(unittest.TestCase):
    def test_total_adds_tax_for_the_customers_country(self):
        use_case = TotalOrder(FakeTaxRates({"DE": 0.19}))

        total = use_case.run(order_for("DE", Line("pen", 2, 10.0)))

        self.assertEqual(total, 23.8)

    def test_total_sums_every_line(self):
        use_case = TotalOrder(FakeTaxRates({"XX": 0.0}))

        total = use_case.run(order_for("XX", Line("pen", 2, 10.0), Line("ink", 1, 5.5)))

        self.assertEqual(total, 25.5)


if __name__ == "__main__":
    unittest.main()
''',
}

# The feature branch: works, but puts things in the wrong place and reads badly.
BRANCH_FILES = {
    "specs/ord-31-quote/requirements.md": (
        "# ORD-31 Quote: requirements\n\n"
        "`python3 -m orders quote '<json>' [--no-tax] [--shipping]` prints a quote for an order.\n\n"
        "- R1. The subtotal is the sum of `qty * unit_price` over the order's lines.\n"
        "- R2. An order whose subtotal is 100.00 or more gets a 5% discount on the subtotal.\n"
        "- R3. Tax for the customer's country is added after the discount, unless `--no-tax` is given.\n"
        "- R4. With `--shipping`, shipping is added after tax: 4.90 for DE, 6.50 for FR, 12.00 elsewhere.\n"
        "- R5. An order whose subtotal is below 10.00 is rejected with `{\"error\": \"minimum order is 10.00\"}`.\n"
        "- R6. The total is rounded to two decimals and printed as `{\"total\": <n>, \"currency\": \"EUR\"}`.\n"
    ),
    "orders/domain/pricing.py": '''from orders.adapters.rates_file import FileTaxRates


def calc(o, flag=True, f2=False):
    # calculate the price
    t = 0
    for l in o.lines:
        t = t + l.qty * l.unit_price
    # discount
    if not (t <= 100):
        t = t - t * 0.05
    if flag:
        r = FileTaxRates("data/tax_rates.json")
        t = t + t * r.rate_for(o.customer.address.country.code)
    if f2:
        if o.customer.address.country.code == "DE":
            t = t + 4.9
        elif o.customer.address.country.code == "FR":
            t = t + 6.5
        else:
            t = t + 12.0
    # old_total = t * 1.19
    # return old_total
    return round(t, 2)
# end calc
''',
    "orders/adapters/cli.py": MAIN_FILES["orders/adapters/cli.py"].replace(
        "from orders.domain.model import Address, Country, Customer, Line, Order\n",
        "from orders.domain.model import Address, Country, Customer, Line, Order\nfrom orders.domain.pricing import calc\n",
    ) + '''

def quote_command(text, tax, ship):
    o = parse_order(text)
    # check minimum
    s = 0
    for l in o.lines:
        s = s + l.qty * l.unit_price
    if s < 10:
        return json.dumps({"error": "minimum order is 10.00"})
    return format_total(calc(o, tax, ship))
''',
    "orders/__main__.py": MAIN_FILES["orders/__main__.py"].replace(
        "from orders.adapters.cli import format_total, parse_order\n",
        "from orders.adapters.cli import format_total, parse_order, quote_command\n",
    ).replace(
        '    print(f"unknown command: {command}", file=sys.stderr)\n',
        '    if command == "quote":\n'
        '        flags = argv[3:]\n'
        '        print(quote_command(payload, "--no-tax" not in flags, "--shipping" in flags))\n'
        '        return 0\n'
        '    print(f"unknown command: {command}", file=sys.stderr)\n',
    ),
    "tests/test_quote.py": '''import unittest

from orders.adapters.cli import parse_order, quote_command
from orders.domain.pricing import calc


class T(unittest.TestCase):
    def test_1(self):
        o = parse_order('{"items": [{"sku": "pen", "qty": 2, "unit_price": 10.0}], "country": "DE"}')
        self.assertEqual(calc(o), 23.8)
        self.assertEqual(calc(o, False), 20.0)
        self.assertEqual(calc(o, True, True), 28.7)
        o2 = parse_order('{"items": [{"sku": "desk", "qty": 1, "unit_price": 200.0}], "country": "FR"}')
        self.assertEqual(calc(o2), 228.0)
        self.assertEqual(calc(o2, False, True), 196.5)

    def test_2(self):
        r = quote_command('{"items": [{"sku": "pin", "qty": 1, "unit_price": 2.0}], "country": "DE"}', True, False)
        self.assertEqual(r, '{"error": "minimum order is 10.00"}')


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


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    case = os.path.abspath(sys.argv[1])
    on_main, no_pr = "--on-main" in sys.argv, "--no-pr" in sys.argv
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
    write(repo, MAIN_FILES)
    run(["git", "add", "-A"], repo)
    run(["git", "commit", "-m", "feat(total): add order total (ORD-12)"], repo)
    run(["git", "remote", "add", "origin", remote], repo)
    run(["git", "push", "-u", "origin", "main"], repo)
    run(["git", "checkout", "-b", BRANCH], repo)
    write(repo, BRANCH_FILES)
    run(["git", "add", "-A"], repo)
    run(["git", "commit", "-m", "feat(quote): add quote command (ORD-31)"], repo)
    run(["git", "push", "-u", "origin", BRANCH], repo)
    oid = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
    if on_main:
        run(["git", "checkout", "main"], repo)

    state = {
        "host": "github.example.invalid", "owner": "acme", "repo": "orders", "viewer": "dev-author", "next_id": 9000,
        "pr_open": not no_pr,
        "pr": {
            "number": 7, "title": "ORD-31: quote command", "state": "OPEN", "author": "dev-author",
            "headRefName": BRANCH, "baseRefName": "main",
            "body": "Adds `python3 -m orders quote`, which prices an order with discount, tax, and optional shipping.\n\n"
                    "Implements ORD-31. Spec: `specs/ord-31-quote/requirements.md`.\n",
            "commits": [{"oid": oid, "message": "feat(quote): add quote command (ORD-31)"}],
            "files": sorted(BRANCH_FILES),
        },
        "threads": [], "reviews": [], "conversation": [], "review_requests": [],
    }
    with open(os.path.join(case, "gh-state", "state.json"), "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
    shutil.copy(os.path.join(case, "gh-state", "state.json"), os.path.join(case, "gh-state", "state.initial.json"))
    gh = os.path.join(case, "bin", "gh")
    shutil.copy(os.path.join(HERE, "fake_gh.py"), gh)
    os.chmod(gh, 0o755)
    print(json.dumps({"case": case, "repo": repo, "start": oid, "checked_out": "main" if on_main else BRANCH,
                      "pr": None if no_pr else "https://github.example.invalid/acme/orders/pull/7"}, indent=2))


if __name__ == "__main__":
    main()
