# Refactor plan: feat/ORD-31-quote

Working document. Never staged or committed.

**Ids used here.** `R1`-`R5` are this plan's items; the spec's requirements are always written "spec R1"-"spec R6". `D1`-`D10` are settled decisions and are always written "decision D3"; a CLEAN_CODE design rule is written "rule D5". Findings are `FND-n`, correctness items `COR-n`, observations `OBS-n`, plan-review findings `P-n`. Any other bare id (`F6`, `N5`, `C5`, `SM5`, `T1`, `U6`, `G2`) is a CLEAN_CODE rule.

## 1. Header

- **Branch:** `feat/ORD-31-quote`
- **PR:** none open at the start of the run; this run opened https://github.example.invalid/acme/orders/pull/7 against `main` (see section 9)
- **Base:** `main` (the remote's default branch); **merge-base:** `a45dfb8239f40dd2932fc5891716294b52a920a2`
- **Start (`<start>`):** `a6869ab54e1cc4af752da1c97e88a7a700b64910`
- **Workspace:** `/tmp/rf-eval/named-branch-no-pr/repo-worktrees/feat-ORD-31-quote` (worktree added for this run; the branch was not checked out anywhere)
- **Scope:** 4 source and test files, 65 lines added, 1 removed: `orders/__main__.py`, `orders/adapters/cli.py`, `orders/domain/pricing.py` (new), `tests/test_quote.py` (new). `specs/ord-31-quote/requirements.md` (new, 10 lines) was read for intent and is not judged.
- **Baseline gates at `<start>`:**

  | Gate | Command | Result |
  |---|---|---|
  | format | - | not configured (`CLAUDE.md:4`) |
  | lint | `make lint` | pass |
  | architecture | `make arch` | **fail**: `orders/domain/pricing.py: orders/domain must not import orders.adapters.rates_file` (1 from this branch, 0 pre-existing: the gate passes at the merge-base) |
  | build | - | not configured (`CLAUDE.md:4`) |
  | test | `make test` | pass, 4 tests (`test_quote.T.test_1`, `test_quote.T.test_2`, `test_total.TotalOrderTest.test_total_adds_tax_for_the_customers_country`, `test_total.TotalOrderTest.test_total_sums_every_line`) |

- **Date:** 2026-11-20

## 2. Settled decisions

- **D1** - Depth is structural.
- **D2** - The discount boundary (code: above 100; spec R2: "100.00 or more") is fixed on this branch in its own `fix(quote)` commit after the refactor, with a regression test. (Narrowed by decision D9: it covers a float subtotal of exactly 100.)
- **D3** - The quote keeps its exact arithmetic (line-by-line subtotal, `t + t * rate`, `t - t * 0.05`). Unifying with `orders/domain/totals.py` is deferred and recorded as an open correctness item, with a warning comment at the quote's subtotal.
- **D4** - The quote gets a `QuoteOrder` use case in `orders/app/quote.py` that receives the `TaxRates` port through its constructor; `calc` dissolves into pure pricing rules; `quote_command(use_case, text, flags)` only translates; `__main__.py` wires it.
- **D5** - The minimum-order rule moves to the domain; rejection crosses back as a `BelowMinimumOrder` exception that the CLI adapter renders as the same JSON, exit status 0.
- **D6** - The shipping table is a `ShippingRates` value object built in the composition root and injected; the discount threshold, discount rate, and minimum order are named constants in the domain. No new port.
- **D7** - The switches reach the use case as keyword-only booleans, `run(order, *, include_tax, include_shipping)`; the domain rules take no flags.
- **D8** - Tests: R1 pins the CLI contract end to end; R5 rewrites `tests/test_quote.py` as one-behavior tests with a fake `TaxRates`. (Its sharing clause was replaced by decision D10.)
- **D9** (reopened in the plan review, P-10) - The float-money mismatches with spec R2, R5, and R6 are deferred as an open correctness item (COR-3). The decision D2 fix stays and is described as covering a float subtotal of exactly 100. R1's three arithmetic tests are labelled as pinning float artefacts.
- **D10** (reopened in the plan review, P-9; replaces the sharing clause of D8) - `tests/test_total.py` and `CLAUDE.md` stay untouched; `tests/test_quote.py` gets its own `FakeTaxRates` and `order_for`, written after the example `CLAUDE.md:6` points to.

Fact, not a decision: Python names are internal and may change; the CLI output for a given input is the contract (`CLAUDE.md:5`).

## 3. Architecture

```
STYLE: ports-and-adapters (hexagonal), three layers and a composition root - declared at docs/architecture.md:3
GATE: make arch (python3 tools/check_layers.py) -> fail (1 from this branch, 0 pre-existing)
NEW EDGES:
  orders/domain/pricing.py -> orders.adapters.rates_file | orders/domain/pricing.py:1 | forbidden (docs/architecture.md:5)
  orders/adapters/cli.py -> orders.domain.pricing | orders/adapters/cli.py:4 | allowed (no rule restricts what adapters import, and the direction is inward; what the adapter does with the import is the placement problem in FND-2 and FND-3)
  orders/__main__.py -> orders.adapters.cli (new symbol quote_command on an existing edge) | orders/__main__.py:3 | allowed (docs/architecture.md:9)
  tests/test_quote.py -> orders.adapters.cli, orders.domain.pricing | tests/test_quote.py:3-4 | allowed (tests are not a layer)
LOOSENED GATES: none (tools/check_layers.py and the Makefile are unchanged; no suppressions added)
CONFORMANCE:
  orders/domain/pricing.py | domain | violation | docs/architecture.md:5 (pure: no I/O, no configuration, imports only orders.domain), read with :9 (file paths and tables are configuration) | pricing.py:1 imports an adapter; pricing.py:13-14 builds FileTaxRates from a hard-coded path and reads the file; pricing.py:16-21 holds the shipping table | Extract a use case that receives the TaxRates port as docs/architecture.md:7 prescribes; pass the rate in as a value; move the table to the root
  orders/adapters/cli.py | adapters | violation | docs/architecture.md:8 (adapters contain no business rules); :6 (use cases orchestrate) | cli.py:19-24 decides the minimum-order rule; cli.py:17-25 orchestrates parse, validate, price | Move the rule to the domain; move the orchestration to the use case
  orders/__main__.py | composition root | drift | docs/architecture.md:9 (builds adapters, injects them into use cases, dispatches; configuration defined here and passed down); :8 (adapters translate CLI text) | __main__.py:16-19 builds and injects nothing for quote; __main__.py:17-18 translates the flag text itself; the rates path it defines at :7 is spelled again at pricing.py:13 | Build QuoteOrder(FileTaxRates(TAX_RATES_PATH), SHIPPING_RATES) at the root; hand the raw flags to the adapter
  tests/test_quote.py | tests (not a layer) | n/a for architecture; see FND-13 (CLAUDE.md:6)
VERDICT: violates
OBSERVATIONS: see Non-goals (OBS-1 to OBS-6)
```

Gate blind spots (`docs/architecture.md:10`, `tools/check_layers.py:7-10,18-19,26`): the gate reads only absolute `orders.<x>` imports under `orders/domain` and `orders/app`. It cannot see I/O through the standard library (`open` in the domain would pass), business rules inside adapters (rule 4), what the composition root wires (rule 5), or placement in general. It also misses some imports: `from orders import adapters` (the module is `orders`, which fails `startswith("orders.")`), relative imports, and `importlib`. So a green gate after R2 confirms only that no absolute `orders.adapters` import remains in the domain; the rest of the "after" verdict is by reading the files. After R3 the adapter keeps one edge to `orders.domain.pricing`, for the `BelowMinimumOrder` type it translates: allowed.

## 4. Items

Findings are listed with their verdicts in section 4.0; the items follow in execution order. Each item is one commit.

### 4.0 Findings and verdicts

| # | Site | Rule | What is wrong (evidence) and what it costs | Remedy | Behavior-preserving | Pinned by | Payoff / cost | Verdict |
|---|---|---|---|---|---|---|---|---|
| FND-1 | `orders/domain/pricing.py:calc` | `docs/architecture.md:5`; rule D5 | Imports `orders.adapters.rates_file` (`:1`), builds `FileTaxRates("data/tax_rates.json")` and reads the file (`:13-14`). `make arch` fails; the domain cannot run without a file relative to the working directory; the path duplicates `orders/__main__.py:7` | Extract Class (use case `QuoteOrder`) receiving the `TaxRates` port (`docs/architecture.md:7`); Parameterize the rate | yes: same adapter, same path, rate looked up only when tax is requested | `T.test_1` (DE and FR rates through the real file); default-rate country and CLI path unpinned | H / M | plan (R2) |
| FND-2 | `orders/adapters/cli.py:quote_command`, `orders/__main__.py:main` | `docs/architecture.md:6`, `:9` | The quote has no use case: the adapter sequences parse, validate, price (`cli.py:17-25`) and the root injects nothing (`__main__.py:16-19`), unlike the total branch (`:12-15`). A second adapter would have to copy the sequence | Extract use case; wire it at the root | yes | CLI dispatch and flag parsing unpinned | H / M | plan (R2), same root cause as FND-1 |
| FND-3 | `orders/adapters/cli.py:quote_command` | `docs/architecture.md:8`, `:5` | The minimum-order rule is decided in the adapter (`cli.py:19-24`). Any other entry point skips it | Move Function to the domain (`require_minimum_order`), translate the rejection in the adapter | yes: same comparison `subtotal < 10`, same text, same exit status | `T.test_2` (below minimum); exactly 10.00 unpinned | H / S | plan (R3) |
| FND-4 | `orders/domain/pricing.py:calc` | F6, F4 | Two positional boolean flags `flag`, `f2` (`:4`); calls read `calc(o, True, True)` (`tests/test_quote.py:12`), and `quote_command(payload, "--no-tax" not in flags, "--shipping" in flags)` (`__main__.py:18`) | Split into flagless rules; keyword-only switches at the use case (decision D7) | yes | `T.test_1` | H / S | plan (R2) |
| FND-5 | `orders/domain/pricing.py:calc` | F2, F1 | One function does five things: subtotal, discount, tax lookup and application, shipping, rounding (`:6-24`). No rule can be read, tested, or changed alone | Extract Function per rule | yes: each expression kept verbatim (decision D3) | `T.test_1`; shipping elsewhere unpinned | H / M | plan (R2) |
| FND-6 | `calc`, `quote_command` | N1, F3 | `calc`, `o`, `flag`, `f2`, `t`, `r`, `l` (`pricing.py:4-14`); `tax`, `ship`, `o`, `s`, `l` (`cli.py:17-22`). The reader has to execute the code to learn what each holds | Rename | yes | - | M / S | plan (R2, R3: the lines are rewritten there) |
| FND-7 | `calc` | N5 | `100`, `0.05` (`pricing.py:10-11`) | Replace Magic Number with Named Constant | yes | 200.00 pinned by `T.test_1`; the boundary unpinned | M / S | plan (R2) |
| FND-8 | `quote_command` | N5; SM5 traced to FND-3 | `10` (`cli.py:23`) and again inside the text `"minimum order is 10.00"` (`cli.py:24`): the threshold is written twice and can drift | Named constant in the domain; the adapter formats the text from it (`f"{10:.2f}"` is `"10.00"`) | yes | `T.test_2` pins the text | M / S | plan (R3) |
| FND-9 | `calc` | `docs/architecture.md:5` read with `:9`; rule D1, N5 | The shipping table `DE 4.9 / FR 6.5 / else 12.0` is an if-chain of literals in the domain (`pricing.py:16-21`) | Replace conditional with a `ShippingRates` value built at the root (decision D6) | yes, provided the lookup compares with `==` as the chain does: a dict lookup would raise `TypeError` for an unhashable `country` such as `["DE"]`, which with `--no-tax --shipping` prints 32.0 today (P-1) | DE and FR pinned by `T.test_1`; elsewhere and the non-string country unpinned | M / S | plan (R4) |
| FND-10 | `calc` | U6 | `if not (t <= 100)` (`pricing.py:10`) | `subtotal > DISCOUNT_THRESHOLD` | yes for every number; for NaN the branch taken differs but both end in a NaN total | boundary and NaN unpinned | M / S | plan (R2) |
| FND-11 | `calc` | rule D6 | `o.customer.address.country.code` three times (`pricing.py:14,16,18`) although `Order.country_code` exists (`orders/domain/model.py:32`) | Use `order.country_code` | yes: the property returns the same attribute | `T.test_1` | M / S | plan (R2) |
| FND-12 | `calc`, `quote_command` | C5, C4, C2, C3 | Commented-out code (`pricing.py:22-23`), closing comment `# end calc` (`:25`), noise comments `# calculate the price`, `# discount`, `# check minimum` (`pricing.py:5,9`; `cli.py:19`) | Delete; the extracted function names carry the meaning (rule C1) | yes | - | L / S | plan (R2, R3: the lines are rewritten there) |
| FND-13 | `tests/test_quote.py:T` | `CLAUDE.md:6`; T1, T2, T5, N1 | `test_1` asserts five behaviors in a row (`:10-15`), so the first failure hides the rest; the names `T`, `test_1`, `test_2`, `o2`, `r` say nothing; `test_1` reads `data/tax_rates.json` through the domain and only passes from the repo root | Split into one-behavior tests of `QuoteOrder` with a fake `TaxRates` (decisions D8, D10) | yes: same inputs and expected values | - | H / M | plan (R5) |
| FND-14 | quote behavior | Step 2 rule 3 (pin before touching) | Unpinned today: `main`'s quote dispatch; `--no-tax` and `--shipping` parsing, in either order; unknown flags being ignored; the success output format; shipping elsewhere; the default tax rate; exactly 10.00; exactly 100.00; the discount being decided on the pre-tax subtotal (228.0 for 200.00 in FR is the same in either order); line-by-line addition and the tax and discount expression forms; NaN prices; a non-string country; that `--no-tax` and a rejected order never open the rates file; that parse and file errors propagate; the exit status | Characterization tests at the CLI contract | n/a (tests only) | - | H / S | plan (R1) |
| FND-15 | `calc` vs spec R2 | `specs/ord-31-quote/requirements.md:6` | The spec discounts "100.00 or more"; the code discounts only when the float subtotal is above 100 (`pricing.py:10`). One line of 100.00 in DE prints 119.0; the spec gives 113.05 | Change `>` to `>=` | **no**: a caller observes a different total | unpinned | H / S | correctness (COR-1, decision D2: fix now) |
| FND-16 | `pricing.py:6-8,14` vs `orders/domain/totals.py` | SM5 | The quote re-implements `subtotal` and `with_tax`. Calling them changes output: `sum()` is compensated on Python 3.12 (140.31 becomes 140.32 for lines 1 x 6.27, 3 x 24.41, 2 x 34.10, no tax), and `amount * (1 + rate)` differs from `t + t * rate` at half-cent boundaries (10.50 in DE: 12.5 against 12.49). Measured with a scratch script: 300000 random orders (seed 1) of 2-4 lines, quantity 1-5, price 0.01-50.00, each at rates 0.19, 0.2, 0.0: 1843 orders (0.61%) changed their rounded total at one rate. Single-line amounts 10.00-2000.00 by cent, discount applied above 100, three rates: 884 of 570003 cases differ between the two tax forms | Reuse `totals.subtotal` / `totals.with_tax` | **no** | unpinned | M / M | correctness (COR-2, decision D3: deferred) |
| FND-17 | `pricing.py:6-8` and `cli.py:20-22` | SM5 traced to FND-2 | The quote's subtotal loop exists twice inside the branch; a change to one silently disagrees with the other | One `quote_subtotal`, computed once in the use case | yes: the same loop | `T.test_1`, `T.test_2` | M / S | plan (R2 extracts it, R3 removes the adapter's copy) |
| FND-18 | `orders/__main__.py:main` | N5 | The literals `"--no-tax"` and `"--shipping"` (`__main__.py:18`) | Named constants | yes | - | L / S | skip (see Non-goals) |
| FND-19 | `orders/__main__.py:main` | `docs/architecture.md:8`, `:9` | The composition root translates CLI text itself: `"--no-tax" not in flags`, `"--shipping" in flags` (`__main__.py:17-18`). Translating CLI text is the adapter's job; the root builds, injects, dispatches | Move the flag translation into `quote_command(use_case, text, flags)` | yes: the same two membership tests on the same list | unpinned | M / S | plan (R2) |
| FND-20 | quote vs spec R2, R5, R6 | `specs/ord-31-quote/requirements.md:6,9,10` | Float money misses the spec at the boundaries (reproduced): 3 x 3.30 + 5 x 0.02 is exactly 10.00 and is rejected (float sum 9.999999999999998); 4 x 7.10 + 2 x 32.01 + 1 x 7.58 is exactly 100.00 and is not discounted, before and after COR-1 (float sum 99.99999999999999); 1 x 6.27 + 3 x 24.41 + 2 x 34.10 with no tax is exactly 140.315 and prints 140.31 | Exact money (integer cents or `Decimal`) in `orders/domain/model.py`, the parser, both commands | **no** | unpinned | H / L | correctness (COR-3, decision D9: deferred); root cause OBS-1 |

In-scope files: all four read in full; each has findings above. None is recorded as clean.

### R1 - Pin the quote command's CLI contract

- **Resolves:** FND-14 (safety net for R2-R4 and COR-1).
- **Touches:** new `tests/test_quote_cli.py`. No production code.
- **Steps:** add end-to-end tests that call `orders.__main__.main(["orders", "quote", <json>, *flags])` with stdout captured, one behavior per test, each asserting the exact output line unless stated:
  1. tax is added for the customer's country (DE, 2 x 10.0: `{"total": 23.8, "currency": "EUR"}`)
  2. `--no-tax` leaves tax out (20.0)
  3. `--shipping` adds the DE rate after tax (28.7)
  4. `--shipping` adds the FR rate (1 x 200.0, `--no-tax --shipping`: 196.5)
  5. `--shipping` adds 12.00 elsewhere (US, 2 x 10.0: 32.0)
  6. flags are accepted in either order (`--shipping --no-tax`, DE, 2 x 10.0: 24.9)
  7. an unknown flag is ignored (`--bogus`, DE, 2 x 10.0: 23.8)
  8. a country without a rate is taxed at the default rate (US, 2 x 10 as integers: `20.0`, where `--no-tax` prints `20`, so the tax step demonstrably ran)
  9. a subtotal above 100 is discounted (FR, 1 x 200.0: 228.0)
  10. the discount is decided on the subtotal before tax (DE, 1 x 99.99: 118.99; deciding after tax would print 113.04)
  11. a subtotal of exactly 100 is not discounted (DE, 1 x 100.0: 119.0). This pins today's behavior, which contradicts spec R2; COR-1 flips it.
  12. a subtotal below the minimum is rejected (DE, 1 x 2.0: `{"error": "minimum order is 10.00"}`)
  13. a subtotal of exactly the minimum is accepted (DE, 1 x 10.0: 11.9)
  14. an order without lines is rejected (`"items": []`)
  15. lines are added one by one (US, 1 x 6.27, 3 x 24.41, 2 x 34.1: 140.31; `sum()` would print 140.32)
  16. tax is added to the amount, not multiplied in (DE, 1 x 10.5: 12.5; `amount * (1 + rate)` would print 12.49)
  17. the discount is subtracted, not multiplied in (US, 1 x 100.7, `--no-tax`: 95.67; `amount * 0.95` would print 95.66)
  18. integer prices stay integers (DE, 2 x 10, `--no-tax`: `{"total": 20, "currency": "EUR"}`)
  19. a NaN price yields a NaN total, not a rejection (`{"total": NaN, "currency": "EUR"}`)
  20. a country that is not a string ships at the elsewhere rate (`"country": ["DE"]`, `--no-tax --shipping`: 32.0)
  21. `--no-tax` never opens the rates file (`builtins.open` patched to fail)
  22. a rejected order never opens the rates file (same patch)
  23. a malformed payload raises `json.JSONDecodeError` out of `main`
  24. an unreadable rates file raises `FileNotFoundError` out of `main` (`builtins.open` patched)
  25. a quote exits with status 0; 26. a rejected quote exits with status 0
- **Labels:** tests 15-17 pin float artefacts so that the refactor provably keeps them (decision D3); they are not intended behavior (COR-2, COR-3) and are grouped and commented as such. Test 20 pins what unvalidated input does today (OBS-6), for the same reason. Test 11 pins the bug COR-1 fixes.
- **Why it preserves behavior:** it adds tests only, and they must pass against the unchanged code before anything else moves.
- **Note:** apart from 21, 22, and 24 these tests read `data/tax_rates.json` relative to the repo root, as the CLI does. `CLAUDE.md:6` forbids file I/O in domain and app tests; these are neither.
- **Commit subject:** `test(quote): pin the quote command's CLI contract (ORD-31)`
- **Status:** done
- **Commit:** `4c77e2e`

### R2 - Price quotes through a QuoteOrder use case

- **Resolves:** FND-1, FND-2, FND-4, FND-5, FND-7, FND-10, FND-11, FND-19, FND-17 (the pricing copy); FND-6 and FND-12 for `pricing.py`. Rules: `docs/architecture.md:5,6,7,8,9`; rule D5, rule D6, F2, F6, F1, N1, N5, U6, C2-C5.
- **Touches (in scope):** `orders/domain/pricing.py` (`calc` removed; `quote_subtotal`, `after_discount`, `add_tax`, `shipping_cost`, `DISCOUNT_THRESHOLD`, `DISCOUNT_RATE` added), `orders/adapters/cli.py` (the `calc` import at `:4`, and `quote_command`'s signature and last line only), `orders/__main__.py` (the quote branch), `tests/test_quote.py` (forced edits only). **New:** `orders/app/quote.py` (`QuoteOrder`).
- **Steps:**
  1. Extract Function in `pricing.py`, each body verbatim: `quote_subtotal(order)` (the loop, starting from `0`, with a warning comment that `sum()` would change totals, decision D3), `after_discount(subtotal)` (`subtotal > DISCOUNT_THRESHOLD`, `subtotal - subtotal * DISCOUNT_RATE`), `add_tax(amount, rate)` (`amount + amount * rate`, with a warning comment that it is deliberately not `totals.with_tax`), `shipping_cost(country_code)` (the if-chain, literals unchanged until R4). `calc` calls them and uses `order.country_code`. Run the tests.
  2. Add `orders/app/quote.py`: `QuoteOrder(tax_rates)` with `run(order, *, include_tax, include_shipping)` composing the rules in the same order as `calc` and rounding to 2. The rate is looked up only inside `if include_tax`. Run the tests.
  3. Change `quote_command(text, tax, ship)` to `quote_command(use_case, text, flags)`: its minimum check stays untouched (R3 owns it); its last line becomes `format_total(use_case.run(o, include_tax="--no-tax" not in flags, include_shipping="--shipping" in flags))`; the import of `calc` at `cli.py:4` is removed. `__main__.py` builds `QuoteOrder(FileTaxRates(TAX_RATES_PATH))` and passes `argv[3:]`. `T.test_2` is re-pointed to the new signature. Run the tests.
  4. Re-point `T.test_1` from `calc(...)` to `QuoteOrder(FileTaxRates("data/tax_rates.json")).run(...)` with the same inputs and expected values, then delete `calc`, the adapter import at `pricing.py:1`, the commented-out code, and the closing comment. Run the tests and `make arch` (it must now pass), and read `pricing.py`'s imports (the gate's blind spots).
- **Why it preserves behavior:** every arithmetic expression is moved verbatim, in the same order (subtotal, discount, tax, shipping, round); the same adapter reads the same path; the lookup stays conditional on the tax switch and after the adapter's minimum check; `order.country_code` returns the attribute the chain read; `subtotal > 100` and `not (subtotal <= 100)` agree for every number, and for NaN both produce a NaN total; the flag tests are the same two membership checks on the same list.
- **Pinned by:** all of R1's tests (in particular 6, 7 for the flags; 10, 15-19 for the arithmetic; 21 for the conditional lookup); `T.test_1`, `T.test_2`.
- **Test edits:** `tests/test_quote.py` only where it called `calc` or the old `quote_command` signature; no expected value changes. Between R2 and R5 `T.test_1` is an app-level test that reads the rates file, as it effectively was before; R5 removes that.
- **Commit subject:** `refactor(quote): price quotes through a QuoteOrder use case (ORD-31)`
- **Status:** done
- **Commit:** `44ecc25`

### R3 - Move the minimum-order rule into the domain

- **Resolves:** FND-3, FND-8, FND-17 (the adapter copy); FND-6 and FND-12 for `cli.py`. Rules: `docs/architecture.md:8,5`; N5, N1, C3, SM5 at its root.
- **Touches (in scope):** `orders/domain/pricing.py` (`MINIMUM_ORDER`, `BelowMinimumOrder`, `require_minimum_order` added), `orders/app/quote.py` (`run` calls the rule first), `orders/adapters/cli.py` (`quote_command`).
- **Steps:**
  1. Add `MINIMUM_ORDER = 10`, `class BelowMinimumOrder(Exception)` carrying `minimum`, and `require_minimum_order(subtotal)` raising it when `subtotal < MINIMUM_ORDER` (that exact comparison: a NaN subtotal is not rejected). Run the tests.
  2. `QuoteOrder.run` computes `quote_subtotal(order)` once, calls `require_minimum_order` on it before anything else, then discounts that same value. The adapter still checks first, so nothing changes yet. Run the tests.
  3. `quote_command` drops its loop, comparison, and comment; it calls the use case inside `try` and renders `BelowMinimumOrder`, and only that exception, as `json.dumps({"error": f"minimum order is {error.minimum:.2f}"})`. Run the tests.
- **Why it preserves behavior:** the comparison is the same expression on the same value (the two loops were identical); the rule still runs before any rate lookup; `f"{10:.2f}"` is `"10.00"`; the adapter still returns the text and `main` still exits 0. Every other exception still propagates uncaught.
- **Pinned by:** R1 tests 12, 13, 14, 19 (NaN), 22 (no lookup before the rejection), 23, 24 (other errors propagate), 26; `T.test_2`.
- **Test edits:** none.
- **Commit subject:** `refactor(quote): move the minimum-order rule into the domain (ORD-31)`
- **Status:** done
- **Commit:** `e24a77c`

### R4 - Define shipping rates in the composition root

- **Resolves:** FND-9. Rules: `docs/architecture.md:5,9`; rule D1, N5.
- **Touches (in scope):** `orders/domain/pricing.py` (`shipping_cost` replaced by a frozen dataclass `ShippingRates(by_country, elsewhere)` with `cost_for(country_code)`), `orders/app/quote.py` (constructor takes `shipping_rates`), `orders/__main__.py` (`SHIPPING_RATES = ShippingRates((("DE", 4.9), ("FR", 6.5)), elsewhere=12.0)`, injected), `tests/test_quote.py` (forced edit: the constructor call).
- **Design note (P-1):** `by_country` is a tuple of `(country code, cost)` pairs and `cost_for` returns the first cost whose code `==` the country, else `elsewhere`. This is the if-chain's own semantics, so an unhashable country still falls through to `elsewhere`; it also makes the frozen value truly immutable, in line with `Order.lines: tuple` (`orders/domain/model.py:28`). A dict would be shorter and would change output for malformed input.
- **Steps:** add `ShippingRates`; inject it into `QuoteOrder` and use `self._shipping_rates.cost_for(order.country_code)`; define the table beside `TAX_RATES_PATH`; delete `shipping_cost`. Run the tests after each.
- **Why it preserves behavior:** the same three floats, compared with `==` in the same order with the same fallback, added at the same point.
- **Pinned by:** R1 tests 3, 4, 5, 6, 20; `T.test_1`.
- **Test edits:** `tests/test_quote.py` passes the table to the constructor; no expected value changes.
- **Commit subject:** `refactor(quote): define shipping rates in the composition root (ORD-31)`
- **Status:** done
- **Commit:** `8c0e14a`

### R5 - Test one quote behavior per test, with a fake TaxRates

- **Resolves:** FND-13. Rules: `CLAUDE.md:6`; T1, T2, T5, N1.
- **Touches (in scope):** `tests/test_quote.py` (rewritten). Nothing outside the scope (decision D10).
- **Steps:** rewrite `tests/test_quote.py` as `QuoteOrderTest`, with its own `FakeTaxRates` and `order_for` after the example in `tests/test_total.py:7-16`, one behavior per test: adds tax for the customer's country (23.8); without tax returns the subtotal (20.0); without tax never asks for a rate (a fake with no rates); adds shipping after tax (28.7); shipping uses the customer's country (FR, 196.5); shipping elsewhere (32.0); a subtotal above 100 is discounted (228.0); the discount is decided on the subtotal before tax (118.99); a subtotal below the minimum is rejected (`BelowMinimumOrder`); a rejected order never asks for a rate.
- **Why it preserves behavior:** tests only; every expected value of `T.test_1` reappears with the same input.
- **Accounting for the baseline tests:** `test_quote.T.test_1`'s five assertions become, in order, `QuoteOrderTest`'s tax (23.8), without-tax (20.0), shipping-after-tax (28.7), discount (228.0), and shipping-by-country (196.5) tests; `test_quote.T.test_2` becomes `QuoteOrderTest.test_subtotal_below_the_minimum_is_rejected` at the use case, and its JSON text stays pinned by R1 test 12. The two `test_total` tests are untouched.
- **Commit subject:** `test(quote): test one quote behavior per test with a fake TaxRates (ORD-31)`
- **Status:** done
- **Commit:** `dc0e873`

## 5. Correctness items

### COR-1 - Discount boundary (FND-15) - decision D2: fix now, in its own commit, after R5

- Change `subtotal > DISCOUNT_THRESHOLD` to `subtotal >= DISCOUNT_THRESHOLD` in `after_discount`.
- Regression tests: R1 test 11 flips from 119.0 to 113.05 and is renamed to say the order is discounted; `QuoteOrderTest` gains a test for exactly 100. Both are watched failing before the fix. R1 test 10 (99.99 is not discounted) stays as it is and guards the other side.
- **Behavior change:** an order whose float subtotal is exactly 100 is now discounted (DE, 1 x 100.0: 119.0 becomes 113.05; with integer prices and `--no-tax`, `100` becomes `95.0`). It does not reach orders that total 100.00 on paper but sum to 99.99999999999999 in floats (COR-3), so spec R2 is met for float-exact subtotals only.
- **Commit subject:** `fix(quote): discount orders of exactly 100.00 (ORD-31)`
- **Status:** done
- **Commit:** `76aab05`

### COR-2 - Quote arithmetic disagrees with `totals.py` (FND-16) - decision D3: deferred

- Not changed. `quote_subtotal` and `add_tax` keep their expressions and carry warning comments; R1 tests 15-17 pin them. In the 10.50 DE example the quote (12.5) is the side that matches exact arithmetic (12.495 rounds to 12.50) and `total` (12.49) is not.

### COR-3 - Float money misses spec R2, R5, R6 at the boundaries (FND-20) - decision D9: deferred

- Not changed. Examples in FND-20. Needs exact money (OBS-1) across `model.py`, the parser, `quote`, and `total`: its own ticket. When it lands, R1 tests 15-17 are expected to change.

## 6. Non-goals

Skipped findings:

- **FND-18** - naming the `"--no-tax"` and `"--shipping"` literals. After R2 each is used once, inside the CLI adapter that owns that vocabulary, and reads as what it is; a constant would add a line and an indirection for no reader (G2).
- Splitting `QuoteOrder.run` to remove the two keyword switches entirely (F6 to the letter) - settled by decision D7.
- Sharing `FakeTaxRates` and `order_for` between the two test modules (SM5) - settled by decision D10: it would require editing `tests/test_total.py`, which this branch did not touch, and the pointer in `CLAUDE.md:6`.
- Domain-level unit tests for each pricing rule in addition to the use-case and CLI tests: they would assert the same values a third time.

Observations (pre-existing, outside the scope; not planned):

- **OBS-1** - Money is `float` (`orders/domain/model.py:8`); U4. Root cause of COR-2 and COR-3.
- **OBS-2** - `main` indexes `argv[1]`, `argv[2]` without a usage check (`orders/__main__.py:11`): a missing argument is a traceback.
- **OBS-3** - `FileTaxRates.rate_for` re-reads the file on every call (`orders/adapters/rates_file.py:9-10`).
- **OBS-4** - `format_total` hard-codes `"EUR"` (`orders/adapters/cli.py:14`).
- **OBS-5** - `make arch` checks only rules 1 and 2, and only absolute `orders.<x>` imports (`tools/check_layers.py:7-10,26`): it would not have caught FND-2, FND-3, FND-9, or FND-19, and would not catch `open()` or a relative import in the domain.
- **OBS-6** - `parse_order` validates nothing (`orders/adapters/cli.py:8-10`): malformed JSON and missing keys are tracebacks, unknown flags are ignored, and any JSON value is accepted as `country` or a price (a list, `NaN`).

## 7. Plan review

Reviewed natively by two adversarial `general-purpose` subagents (one on the diagnosis, one on the remedy), because codex is not available in this environment. 19 findings after merging duplicates: 16 accepted (3 of them in part), 2 accepted through reopened decisions (D9, D10), 1 rejected, 0 deferred.

| # | From | Concerns | Finding | Disposition | Evidence |
|---|---|---|---|---|---|
| P-1 | both | R4, FND-9 | A dict-backed `ShippingRates` raises `TypeError` for an unhashable `country`; today `"country": ["DE"]` with `--no-tax --shipping` prints 32.0. A frozen dataclass holding a dict is also still mutable | accept | Reproduced: 32.0 today. R4 now stores pairs and compares with `==`; R1 test 20 pins it. Decision D6 is unchanged (the value object stays; only its representation changed) |
| P-2 | remedy | R3 step 3 | Nothing pins that errors other than the rejection still propagate once `quote_command` has a `try` | accept in part | Added R1 tests 23 (`JSONDecodeError`) and 24 (`FileNotFoundError`). The separate `KeyError` test is not added: it is the same path as 23 (`parse_order` raising before the `try`) |
| P-3 | remedy | R2 step 2, R3 step 2, R1 | "No rates lookup for `--no-tax` or a rejected order" was unpinned until R5; the plan's reason (a test would need to change directory) was wrong | accept | Added R1 tests 21 and 22, patching `builtins.open`. The reviewer's alternative (reordering R5) is moot under decision D10 |
| P-4 | both | R1 test 9, R5, COR-1 | 228.0 for 200.00 in FR is the same whether the discount is decided before or after tax; after COR-1 nothing separates the two orders | accept | 240 - 12 = 190 + 38 = 228. Added R1 test 10 and an R5 test (DE, 1 x 99.99: 118.99, verified against today's CLI) |
| P-5 | diagnosis | FND-14 | Unknown flags being silently ignored is unpinned, and R2 moves the flag parsing | accept | `--bogus` prints 23.8 today. Added R1 test 7 |
| P-6 | remedy | R2 step 1, R3 step 1 | NaN is in the contract and unpinned; a careless `not subtotal >= MINIMUM_ORDER` would reject it | accept | `"unit_price": NaN` prints `{"total": NaN, ...}` today. Added R1 test 19; R3 step 1 names the exact comparison |
| P-7 | remedy | R1 test 7 (now 8) | The default-rate test expected the same bytes as an untaxed quote | accept | With integer prices the taxed quote prints `20.0` and the untaxed one `20` (verified). Test 8 uses integers |
| P-8 | remedy | R2 "Touches", step 4 | `cli.py:4` imports `calc` and must go when `calc` does; the plan did not list it | accept | `orders/adapters/cli.py:4`. Named in R2's Touches and step 3 |
| P-9 | remedy | R5 step 1, decision D8 | Moving the fake to `tests/support.py` leaves `CLAUDE.md:6` pointing at a file that no longer defines it | accept, through a reopened decision | Put to the user (Q11): decision D10 keeps `tests/test_total.py` and `CLAUDE.md` untouched; `tests/test_quote.py` gets its own fake |
| P-10 | both | FND-15, FND-16, COR-1, COR-2 | Float money misses spec R2, R5, and R6 at the boundaries; COR-1 overclaimed "as spec R2 requires"; tests 13-15 (now 15-17) pin float artefacts as if they were contract | accept, through a reopened decision | All three examples reproduced. Put to the user (Q10): decision D9 defers it as COR-3 (FND-20); COR-1's behavior line and the test labels are reworded |
| P-11 | diagnosis | section 3, FND-18 | The branch put flag translation in the composition root; no finding recorded it although R2 moves it; FND-18's skip rationale was false at `<start>` | accept | `orders/__main__.py:17-18` against `docs/architecture.md:8,9`. Added FND-19 and the `__main__` row; FND-18's rationale now says "after R2" |
| P-12 | diagnosis | whole plan | The plan's ids (F, D, C, O) collide with CLEAN_CODE ids, so citations are ambiguous | accept in part | Findings, correctness items, and observations renamed FND / COR / OBS, with a key at the top. `D1...` and `R1...` are the names the refactor procedure prescribes, so they stay and are always qualified ("decision D3", "rule D5", "spec R2") |
| P-13 | diagnosis | section 3, FND-1 | The shipping table was called drift although `:5` read with `:9` is explicit; `:7` was cited as a rule the domain breaks | accept | `docs/architecture.md:5,7,9`. The `pricing.py` row is one violation of `:5` read with `:9`; `:7` is cited as the remedy's rule |
| P-14a | diagnosis | section 3, NEW EDGES | The `cli.py -> orders.domain.pricing` edge cited `docs/architecture.md:8` for something that line does not say; R3 leaves such an edge in place | accept | Line 8 is about translation and business rules, not imports. The edge's reason is reworded and the remaining edge is noted under blind spots |
| P-14b | diagnosis | section 3, NEW EDGES | The same edge should be classified as drift | reject | An edge is `allowed`, an `exception`, or `forbidden`, and no cited rule restricts what adapters import. What the adapter does with `calc` is a placement finding and is already FND-2 and FND-3 |
| P-15 | diagnosis | FND-16 | The counts could not be reproduced | accept in part | The counts stand (scratch script, seed 1, re-run: 1843 of 300000 orders; 884 of 570003 cases); the reviewer's reconstruction used a different range and no discount. FND-16 now records the generator |
| P-16 | diagnosis | section 3, OBS-5 | The gate also misses `from orders import adapters`, relative imports, and `importlib`, so "arch passes" proves less than R2 step 4 implied | accept | `tools/check_layers.py:18-19,26`. Added to the blind spots; R2 step 4 also reads the imports |
| P-17 | remedy | COR-1 | With integer prices and `--no-tax`, a subtotal of `100` changes from `100` to `95.0` | accept | `100 - 100 * 0.05` is a float. Stated in COR-1's behavior-change line |
| P-18 | diagnosis | FND-9 | "Behavior-preserving: yes" was unconditional | accept | Same evidence as P-1. FND-9 now states the condition |

## 8. Verification (after the last commit, `76aab05`)

| Gate | At `<start>` (`a6869ab`) | At `76aab05` |
|---|---|---|
| format | not configured | not configured |
| lint (`make lint`) | pass | pass |
| architecture (`make arch`) | fail (1, from this branch) | pass |
| build | not configured | not configured |
| test (`make test`) | pass, 4 tests | pass, 39 tests |

- **Baseline tests accounted for:** `test_total.TotalOrderTest.*` (2) unchanged and passing. `test_quote.T.test_1` split into `QuoteOrderTest.test_quote_adds_tax_for_the_customers_country`, `test_quote_without_tax_is_the_subtotal`, `test_shipping_is_added_after_tax`, `test_subtotal_above_100_is_discounted`, `test_shipping_uses_the_rate_for_the_customers_country`, same inputs and expected values. `test_quote.T.test_2` became `QuoteOrderTest.test_subtotal_below_the_minimum_is_rejected`, with its JSON text pinned by `test_quote_cli.QuoteMinimumOrderTest.test_subtotal_below_the_minimum_is_rejected`.
- **Differential run:** a scratch harness drove `main` in-process over 46098 quote inputs (prices at every boundary, 3000 random multi-line orders, NaN, infinities, wrong types, malformed JSON, ten kinds of country value, eight flag combinations, with and without a readable rates file) at `<start>` and after each step of R2-R4. The recorded status, output, and exception were byte-identical at every step through `dc0e873` (R5). After `76aab05` (COR-1) exactly 160 cases differ, every one an order whose float subtotal is exactly 100.
- **Architecture verdict after:** conforms. The domain imports only `dataclasses`; `orders/app/quote.py` imports only `orders.domain.pricing`; the adapter holds no business rule; the root builds, injects, and dispatches, and defines the rates path and the shipping table. Read by hand as well as by the gate (see its blind spots in section 3).
- **Final read of `git diff a6869ab..HEAD` against CLEAN_CODE.md:** no new finding. The two comments in `pricing.py` are warnings of consequences (C8) for the arithmetic kept under decision D3.

## 9. Published

- Pushed `a6869ab..76aab05` to `feat/ORD-31-quote` on `origin` (fast-forward). Remote head verified: `76aab05e662af1f6d698df1d1d90040326a32f10`.
- Opened PR #7, `feat(quote): add quote command (ORD-31)`, into `main`: https://github.example.invalid/acme/orders/pull/7. Its head is `76aab05`; the refactor section sits between the `<!-- refactor:start -->` and `<!-- refactor:end -->` markers.
- This file keeps the name resolved at the start of the run (`refactor-feat-ORD-31-quote.md`). A later run would look for `refactor-7.md`.

