# Refactor plan: PR #7 (`feat/ORD-31-quote`)

- **Branch:** `feat/ORD-31-quote`
- **PR:** [#7 ORD-31: quote command](https://github.example.invalid/acme/orders/pull/7)
- **Base:** `main`, merge-base `a45dfb8239f40dd2932fc5891716294b52a920a2`
- **Start:** `a6869ab54e1cc4af752da1c97e88a7a700b64910`
- **Scope:** 4 code and test files plus the spec, +75 / -1 lines: `orders/__main__.py` (M), `orders/adapters/cli.py` (M), `orders/domain/pricing.py` (A), `tests/test_quote.py` (A), `specs/ord-31-quote/requirements.md` (A, read for intent, not edited)
- **Baseline gates at start:** format - not configured; `make lint` - pass; `make arch` - **fail** (1 failure, from this branch; passes at the merge-base); build - not configured; `make test` - pass (4 tests: `test_quote.T.test_1`, `test_quote.T.test_2`, `test_total.TotalOrderTest` x2)
- **Date:** 2026-11-20

The contract every item is held to is the CLI output (`CLAUDE.md:5`): `python3 -m orders quote '<json>' [--no-tax] [--shipping]` prints the same bytes and exits with the same status before and after each refactor item. Python names are internal and change freely. The one exception is D11.

## Settled decisions

- D1. Depth is structural.
- D2. `quote` gets a use case, `QuoteOrder` in `orders/app/quote.py`, receiving the `TaxRates` port through its constructor and wired in `orders/__main__.py`; `orders/domain/pricing.py` becomes pure (no adapter import, no file, no path).
- D3. The minimum-order rule moves from the CLI adapter into the domain.
- D4. The per-country shipping table is defined in `orders/__main__.py` and passed down; the scalar thresholds (minimum 10.00, discount 100.00 and 5%) are named constants in the domain.
- D5. The discount boundary (exactly 100.00, spec R2) is fixed in this PR, in its own `fix` commit with a regression test, after the refactor items. *Amended after the codex review:* the fix is the comparison only. Baskets whose float subtotal lands a hair under a threshold (3 x 21.40 + 35.80 at 100.00; 9.94 + 0.03 + 0.03 at 10.00) stay as they are and are recorded under C2.
- D6. The `quote` / `total` cent disagreement is deferred: `quote` keeps its arithmetic exactly (`amount + amount * rate`, `amount - amount * 0.05`, and, *added after the codex review*, its left-to-right subtotal, which is not `sum()`), pinned by tests and marked with warning comments; recorded as an open item.
- D7. `FakeTaxRates` and `order_for` move to `tests/fakes.py`, shared by `tests/test_total.py` and `tests/test_quote.py`; the CLI characterization tests stay as permanent contract tests.
- D8. The shipping table travels as a domain value object `ShippingRates`, not a new port.
- D9. The rejection is a domain exception, `MinimumOrderNotMet`, translated to `{"error": ...}` by the CLI adapter; exit status stays 0.
- D10. Domain steps take no flags; `QuoteOrder.run` takes `include_tax` and `include_shipping` as keyword-only arguments without defaults.
- D11. *Added after the codex review.* R5's dictionary lookup changes one malformed input: a `country` that is a JSON list or object, with `--no-tax --shipping`, printed `{"total": 32.0, ...}` and will raise `TypeError`, as the same input already does without `--no-tax`. Accepted as a behavior change, called out in R5's commit body and in the PR; it is not preserved.

## Architecture

- **Style:** ports-and-adapters (hexagonal), three layers and a composition root - declared at `docs/architecture.md:3`.
- **Components and allowed edges:** `orders/domain/` imports only `orders.domain`, pure, no I/O, no configuration (`:5`); `orders/app/` imports only `orders.domain` and `orders.app`, use cases receive ports through the constructor (`:6-7`); `orders/adapters/` implements ports and translates, no business rules (`:8`); `orders/__main__.py` is the composition root and owns configuration values (`:9`).
- **Gate:** `make arch` (`python3 tools/check_layers.py`) -> **fail (1 from this branch, 0 pre-existing)**: `orders/domain/pricing.py: orders/domain must not import orders.adapters.rates_file`. The gate checks imports for rules 1 and 2 only (`:10`); it has no entry for `orders/adapters`, so placement (rule 4) is invisible to it. The branch did not touch the gate or add suppressions.
- **New edges:**
  - `orders/domain/pricing.py` -> `orders.adapters.rates_file` | `orders/domain/pricing.py:1` | **forbidden** (`docs/architecture.md:5`)
  - `orders/adapters/cli.py` -> `orders.domain.pricing` | `orders/adapters/cli.py:4` | allowed (adapters translate to domain objects, `:8`), but it is how the adapter bypasses the app layer (A3)
  - `orders/__main__.py` -> `orders.adapters.cli.quote_command` | `orders/__main__.py:3` | allowed (composition root)

| File | Component | Result | Rule | Evidence | Remedy |
|---|---|---|---|---|---|
| `orders/domain/pricing.py` | domain | violation (A1) | `docs/architecture.md:5` | `:1` imports `orders.adapters.rates_file`; `:13` builds `FileTaxRates("data/tax_rates.json")`: file I/O and a config path in the domain, duplicating `orders/__main__.py:7` | Extract use case; inject the `TaxRates` port (R3) |
| `orders/domain/pricing.py` | domain | drift (A4) | `docs/architecture.md:5,9` | `:16-21` hard-codes the per-country shipping table; "tables" are composition-root configuration (D4) | Move the table to the composition root, pass it down as a value object (R5) |
| `orders/adapters/cli.py` | adapters | violation (A2) | `docs/architecture.md:8` | `:19-24` decides the minimum-order rule (spec R5) | Move the rule to the domain (R4) |
| `orders/adapters/cli.py`, `orders/__main__.py` | adapters, composition root | violation (A3) | `docs/architecture.md:6-7,9` | `cli.py:17-25` orchestrates parse, validate, price, format and calls the domain directly; `__main__.py:16-19` wires `quote` with no use case and no injected adapter | Extract class `QuoteOrder` into `orders/app/quote.py`; wire it in `__main__.py` (R3) |
| `tests/test_quote.py` | tests | conforms to the layering; breaks `CLAUDE.md:6` | `CLAUDE.md:6` | `:8-15` five behaviors in one test, through the real rates file | R3 (fake), R6 (split) |

**Verdict: violates.**

## Findings

Shape: site | rule | what is wrong and what it costs | remedy | behavior-preserving | pinned by | payoff, cost | verdict.

- **A1** `orders/domain/pricing.py:calc` | `docs/architecture.md:5`, D5, D1 | the domain imports an adapter (`:1`), opens a file, and hard-codes its path (`:13`); `make arch` fails, and the pricing rules cannot run without `data/tax_rates.json` in the working directory | Extract use case, inject port | yes: the same rate reaches the same expression | `test_1` (through the real file); the CLI dispatch is unpinned | H, M | plan (R3)
- **A2** `orders/adapters/cli.py:quote_command` | `docs/architecture.md:8` | spec R5 decided in the adapter (`:19-24`); a second entry point would skip it | Move function to the domain | yes for the CLI: same check, same place in the sequence, same message | `test_2`; boundary at 10.00 unpinned | H, S | plan (R4)
- **A3** `cli.py:quote_command`, `__main__.py:main` | `docs/architecture.md:6-7,9` | no use case; the adapter orchestrates and nothing is injected | Extract class `QuoteOrder` | yes | flags and dispatch unpinned | H, M | plan (R3)
- **A4** `pricing.py:calc` | `docs/architecture.md:5,9`, D1, N5 | shipping table as literals in an if/elif chain (`:16-21`) | Move table to the composition root as a value object | yes for every hashable country; no for a list or object (D11) | DE and FR rows by `test_1`; "elsewhere" unpinned | M, S | plan (R5), by D4
- **K1** `pricing.py:calc`, `cli.py:quote_command` | F6, D4 | positional flags `flag`, `f2` with defaults; `calc(o, True, True)` (`tests/test_quote.py:12`) and `quote_command(text, True, False)` (`:18`) cannot be read at the call site | Remove flag argument: flag-free steps, keyword-only choices at the use case (D10) | yes | `test_1` | H, S | plan (R3)
- **K2** `pricing.py:calc` | F2, F1 | one function does subtotal, discount, tax lookup, tax, shipping, rounding (`:4-24`) | Extract function per step | yes when each expression is kept verbatim (see R3) | `test_1`; discount boundary unpinned | H, M | plan (R3)
- **K3** names | N1, N3, N4 | `calc`, `o`, `flag`, `f2`, `t`, `r`, `l` (`pricing.py:4-14`); `o`, `s`, `l`, `tax`, `ship` (`cli.py:17-22`); `T`, `test_1`, `test_2`, `o2`, `r` (`tests/test_quote.py`) | Rename | yes | all tests | M, S | plan (R3, R4, R6)
- **K4** magic numbers | N5 | 100 and 0.05 (`pricing.py:10-11`), 4.9 / 6.5 / 12.0 (`:17-21`), 10 (`cli.py:23`) repeated as "10.00" in the message (`:24`) | Replace magic number with named constant | yes: same values; the message is formatted from the constant and yields the same string | `test_2` for the message | M, S | plan (R3, R4, R5)
- **K5** `pricing.py:10` | U6 | `if not (t <= 100)` | Reverse conditional to `>` | yes (identical for every number; for NaN both leave the result NaN) | boundary unpinned | M, S | plan (R3)
- **K6** `pricing.py:14,16,18` | D6 | `o.customer.address.country.code` three times, although `Order.country_code` exists (`orders/domain/model.py:31-33`) | Use the existing property | yes | `test_1` | M, S | plan (R3)
- **K7** subtotal | SM5, traced to A2 and K2 | the quote's subtotal loop is written twice, `pricing.py:6-8` and `cli.py:20-22` (and `orders/domain/totals.py:1-2` computes a subtotal with `sum()`) | Extract the loop once as `quote_subtotal`; **do not** reuse `totals.subtotal`: Python 3.12's `sum()` is compensated and gives a different float (95.01 + 0.01 + 4.98: loop 100.00000000000001, `sum()` 100.0), which moves orders across both thresholds | yes, with the loop kept | multi-line baskets unpinned | M, S | plan (R3, R4); the remaining two-subtotals duplication is C2
- **K8** comments | C3, C5, C4 | noise comments (`pricing.py:5,9`, `cli.py:19`), commented-out code (`pricing.py:22-23`), closing comment (`pricing.py:25`) | Remove | yes | n/a | L, S | plan (they go with the code R3 and R4 rewrite)
- **K9** `tests/test_quote.py` | `CLAUDE.md:6`, T1, T2, T4, T5 | `test_1` asserts five behaviors, reads `data/tax_rates.json` through the real adapter, and so depends on the working directory; names say nothing | Split test, substitute fake | yes: same expected values | n/a | H, S | plan (R2, R3, R6)
- **K10** safety net | pin before touching | nothing tests `main`'s `quote` dispatch, `--no-tax` / `--shipping` parsing, the "elsewhere" rate, the 100.00 or 10.00 boundaries, integer totals, multi-line float accumulation, the order of discount and tax, or that rejection and `--no-tax` never open the rates file | Characterization tests through `main` | adds tests only | n/a | H, S | plan (R1)
- **B1** `pricing.py:10` | spec R2 | exactly 100.00 is not discounted; the spec says "100.00 or more" | change `>` to `>=` | **no** | pinned as-is by R1, then flipped | H, S | correctness (C1)
- **B2** `pricing.py:6-8,14` vs `orders/domain/totals.py:1-6` | SM5 | `quote` and `total` use different float arithmetic for the subtotal and for tax; DE 10.50 gives 12.5 and 12.49; float subtotals also misjudge baskets at the thresholds | decimal money | **no** | pinned as-is by R1 | M, M | correctness (C2, deferred by D6 and D5)
- **O1-O6** | see Non-goals | | | | | | observation / skip

## Items

### R1 - Pin the `quote` CLI contract

- **Resolves:** K10 (the safety net every later item relies on).
- **Touches:** new `tests/test_quote_cli.py`. No production code.
- **Steps:** add a helper that calls `orders.__main__.main(["orders", "quote", payload, *flags])` under `contextlib.redirect_stdout` and returns `(exit status, printed line)`. One behavior per test, expected values recorded from the unchanged code:
  - DE 2 x 10.0 -> `{"total": 23.8, "currency": "EUR"}`
  - same, `--no-tax` -> 20.0
  - same, `--shipping` -> 28.7 (DE rate)
  - FR 2 x 10.0, `--shipping` -> 30.5 (FR rate)
  - US 2 x 10.0, `--shipping` -> 32.0 (elsewhere rate, default tax 0.0)
  - FR 1 x 200.0 -> 228.0 (discounted)
  - DE 1 x 130.0 -> 146.97 (discount before tax; tax first would print 146.96)
  - FR 1 x 200.0, `--no-tax --shipping` -> 196.5
  - DE 1 x 100.0 -> 119.0 (exactly 100.00 is **not** discounted today; C1 flips this test)
  - DE 1 x 10.0 -> 11.9 (exactly 10.00 is accepted)
  - DE 1 x 9.99 -> `{"error": "minimum order is 10.00"}`
  - a rejected quote exits 0; an accepted quote exits 0
  - DE 2 x 10 (integer price), `--no-tax` -> `{"total": 20, "currency": "EUR"}` (an integer, not 20.0)
  - DE 1 x 10.5 -> 12.5 (the `amount + amount * rate` form; `amount * (1 + rate)` would print 12.49)
  - DE 1 x 100.7, `--no-tax` -> 95.67 (the `x - x * 0.05` form; `x * 0.95` would print 95.66)
  - DE 95.01 + 0.01 + 4.98, `--no-tax` -> 95.0 (left-to-right subtotal 100.00000000000001 is discounted; `sum()` gives 100.0)
  - DE 9.94 + 0.03 + 0.03 -> rejected (left-to-right subtotal 9.999999999999998; `sum()` gives 10.0)
  - from an empty working directory (no `data/tax_rates.json`): a sub-minimum order with tax still prints the error, and an accepted `--no-tax` order still prints its total (the rates file is opened only when tax is added, and never before the minimum check)
- **Behavior:** tests only. They read `data/tax_rates.json` through the real adapter, which `CLAUDE.md:6` allows outside domain and app tests; like `make test` itself they run from the repo root. The two float-accumulation pins record what the code does, not what the spec wants (C2).
- **Pinned by:** itself; each test must pass against `a6869ab` before it is committed.
- **Commit subject:** `test(quote): pin the quote CLI contract (ORD-31)`
- **Status:** done
- **Commit:** `0eec806`

### R2 - Share the port fake between test modules

- **Resolves:** the prerequisite of K9: the app tests R3 touches need the `TaxRates` fake (`CLAUDE.md:6`, D7; codex finding 6).
- **Touches:** new `tests/fakes.py`, `tests/test_total.py` (outside the scope: its two helper definitions become one import).
- **Steps:** move `FakeTaxRates` and `order_for` from `tests/test_total.py` to `tests/fakes.py` unchanged; `test_total.py` imports them. Its two tests are otherwise untouched.
- **Why it preserves behavior:** tests only; the helpers move verbatim.
- **Pinned by:** `test_total.TotalOrderTest` (both tests still pass).
- **Commit subject:** `test: share the tax-rates fake between test modules (ORD-31)`
- **Status:** done
- **Commit:** `fb94335`

### R3 - Extract the `QuoteOrder` use case and inject the tax rates

- **Resolves:** A1, A3, K1, K2, K5, K6, and the `pricing.py` parts of K3, K4, K7, K8; the file-I/O part of K9. Rules: `docs/architecture.md:5-7,9`; D5, D1, F6, D4, F2, N1, N5, U6, D6, SM5, C3-C5; `CLAUDE.md:6`.
- **Touches:** `orders/domain/pricing.py`, new `orders/app/quote.py`, `orders/adapters/cli.py` (`quote_command` signature and last line, the import), `orders/__main__.py` (the `quote` branch and imports), `tests/test_quote.py` (call sites only).
- **Steps** (CLI pins run after each):
  1. In `pricing.py`, extract the pure steps out of `calc`, each expression kept verbatim: `quote_subtotal(order)` (the left-to-right loop, with a C8 warning comment that it is deliberately not `totals.subtotal`), `discounted(amount)` (`amount - amount * DISCOUNT_RATE` when `amount > DISCOUNT_THRESHOLD`, constants `DISCOUNT_THRESHOLD = 100.0`, `DISCOUNT_RATE = 0.05`), `taxed(amount, rate)` (`amount + amount * rate`, with a C8 warning comment that it is deliberately not `totals.with_tax`), and `shipping_cost(country_code)` (the if/elif chain as it is; R5 owns it).
  2. Add `orders/app/quote.py`: `QuoteOrder(tax_rates)` with `run(order, *, include_tax, include_shipping)`: `discounted(quote_subtotal(order))`, then tax only when `include_tax` (rate from `self._tax_rates.rate_for(order.country_code)`), then shipping only when `include_shipping`, then `round(amount, 2)`. Same sequence as `calc`, and the same shape as `TotalOrder` (`orders/app/total.py`).
  3. `quote_command(use_case, text, flags)` in `cli.py` turns the flag strings into the two keyword arguments and calls `use_case.run`; its minimum check is left alone for R4. `__main__.py` builds `QuoteOrder(FileTaxRates(TAX_RATES_PATH))` and passes `argv[3:]`.
  4. Delete `calc` with its comments and its adapter import. Update `tests/test_quote.py` at its call sites only: `test_1` runs the same five cases through `QuoteOrder(FakeTaxRates({"DE": 0.19, "FR": 0.2}))` (the rates the file holds) with the same five expected values; `test_2` calls the new `quote_command` signature with the same expected string.
- **Why it preserves behavior:** every arithmetic expression is moved, not rewritten: the subtotal loop, `t + t * rate`, and `t - t * 0.05` stay in that form (D6). An integer subtotal stays an integer. Tax and shipping stay conditional steps rather than adding a zero, so `--no-tax` on integer prices still prints `20`, not `20.0`. `not (t <= 100)` and `t > 100` agree on every number. The rates are still looked up only when tax is included, and only after the adapter's minimum check passed.
- **Pinned by:** R1 (all of it), `test_1`, `test_2`. `make arch` goes from fail to pass.
- **Commit subject:** `refactor(quote): extract QuoteOrder use case and inject tax rates (ORD-31)`
- **Status:** done
- **Commit:** `4da0c28`

### R4 - Move the minimum-order rule into the domain

- **Resolves:** A2, and the `cli.py` parts of K3, K4, K7, K8. Rules: `docs/architecture.md:8`; N5, SM5, N1, C3.
- **Touches:** `orders/domain/pricing.py`, `orders/app/quote.py`, `orders/adapters/cli.py`, `tests/test_quote.py` (one added test).
- **Steps:**
  1. In `pricing.py` add `MINIMUM_SUBTOTAL = 10.0`, `class MinimumOrderNotMet(Exception)` whose message is `f"minimum order is {MINIMUM_SUBTOTAL:.2f}"`, and `ensure_minimum_met(amount)` which raises it when `amount < MINIMUM_SUBTOTAL`.
  2. `QuoteOrder.run` computes `quote_subtotal(order)` once, calls `ensure_minimum_met` first, then continues as before.
  3. `quote_command` drops its hand-written subtotal loop, its literal `10`, and its comment; it catches `MinimumOrderNotMet` around `use_case.run` and returns `json.dumps({"error": str(rejection)})`. Local `o` becomes `order`.
  4. Add a use-case test: a sub-minimum order with `include_tax=True` and `FakeTaxRates({})` raises `MinimumOrderNotMet` (a lookup before the check would raise `KeyError` instead, and a check left only in the adapter would raise nothing).
- **Why it preserves behavior:** the check is the same comparison (`< 10`) on the same left-to-right subtotal, still before any pricing or rates lookup; the message formats to the identical string `minimum order is 10.00`; `quote_command` still returns it and `main` still exits 0. The one internal difference: `QuoteOrder.run` called directly now rejects a sub-minimum order, where `calc` called directly priced it. No CLI path reaches that, and Python names are internal (`CLAUDE.md:5`).
- **Pinned by:** R1 (rejection at 9.99 and at 9.94 + 0.03 + 0.03, acceptance at 10.00, exit status, rejection with no rates file), `test_2`.
- **Commit subject:** `refactor(quote): move minimum-order rule into the domain (ORD-31)`
- **Status:** done
- **Commit:** `01e9c24`

### R5 - Pass the shipping rates down from the composition root

- **Resolves:** A4 and the shipping part of K4. Rules: `docs/architecture.md:5,9`; D1, N5. Decisions D4, D8, D11.
- **Touches:** `orders/domain/pricing.py`, `orders/app/quote.py`, `orders/__main__.py`, `tests/test_quote.py` (constructor call sites).
- **Steps:**
  1. In `pricing.py` replace `shipping_cost` with a frozen dataclass `ShippingRates(by_country, elsewhere)` and `cost_for(country_code)` returning `by_country.get(country_code, elsewhere)`.
  2. `orders/__main__.py` defines `SHIPPING_RATES = ShippingRates({"DE": 4.9, "FR": 6.5}, elsewhere=12.0)` beside `TAX_RATES_PATH` and builds `QuoteOrder(FileTaxRates(TAX_RATES_PATH), SHIPPING_RATES)`.
  3. `QuoteOrder` takes `shipping_rates` in its constructor and adds `self._shipping_rates.cost_for(order.country_code)`.
  4. `tests/test_quote.py` passes the same table at its constructor call sites.
- **Why it preserves behavior:** for every hashable country value the same three floats are added by the same `amount + cost` expression, with the same fallback. **Behavior change (D11):** a `country` that is a JSON list or object, with `--no-tax --shipping`, printed 32.0 through the if/elif chain and now raises `TypeError`, as it already does without `--no-tax` (`orders/adapters/rates_file.py:11`). The commit body says so.
- **Pinned by:** R1 (DE, FR, and elsewhere rows; shipping after tax; shipping without tax), `test_1`.
- **Commit subject:** `refactor(quote): pass shipping rates down from the composition root (ORD-31)`
- **Status:** done
- **Commit:** `347415c`

### R6 - One behavior per test

- **Resolves:** K9 and the test part of K3. Rules: `CLAUDE.md:6`; T1, T2, N1.
- **Touches:** `tests/test_quote.py`.
- **Steps:**
  1. Rewrite `tests/test_quote.py` as `QuoteOrderTest`, building orders with `order_for`. `test_1` splits into five tests with the same expected values:
     - `test_quote_adds_tax_for_the_customers_country` (23.8)
     - `test_quote_without_tax_is_the_subtotal` (20.0)
     - `test_quote_with_shipping_adds_the_countrys_rate` (28.7)
     - `test_subtotal_above_the_threshold_is_discounted` (228.0)
     - `test_shipping_is_added_to_the_discounted_amount_when_tax_is_left_out` (196.5)
  2. Add `test_discount_is_applied_before_tax` (DE 130.0 at 0.19 -> 146.97; codex finding 5) and `test_tax_rate_comes_from_the_injected_port` (a rate the rates file does not hold; codex finding 6).
  3. `test_2` becomes `QuoteCommandTest.test_order_below_the_minimum_is_reported_as_an_error`, same input and expected string. The R4 test keeps its place in `QuoteOrderTest`.
- **Why it preserves behavior:** tests only; every expected value is carried over unchanged.
- **Pinned by:** n/a (production code untouched); every former assertion has a named successor.
- **Commit subject:** `test(quote): one behavior per test (ORD-31)`
- **Status:** done
- **Commit:** `4113fce`

### R7 - Name the quote flags in the CLI adapter (added in Step 6)

- **Resolves:** a finding this work introduced, caught by the closing read of `git diff a6869ab..HEAD` against `CLEAN_CODE.md` (G3): the `use_case.run(...)` call in `quote_command` ran to 112 characters (S7), and the payload helper in `tests/test_quote_cli.py` to 124.
- **Touches:** `orders/adapters/cli.py:quote_command`, `tests/test_quote_cli.py:order_json`.
- **Steps:** introduce explanatory variables `include_tax` and `include_shipping` (U2); simplify the helper's comprehension.
- **Why it preserves behavior:** the same two expressions, evaluated before the call instead of inside it; the 20,505-case output sweep is byte-identical before and after.
- **Pinned by:** R1.
- **Commit subject:** `refactor(quote): name the quote flags in the CLI adapter (ORD-31)`
- **Status:** done
- **Commit:** `13e1ea3`

## Correctness items

### C1 - Discount a subtotal of exactly 100.00 (B1) - **fix now** (D5)

- **Behavior change:** spec R2 says "100.00 or more"; today exactly 100.00 is not discounted. After the fix, `quote` for DE 1 x 100.0 prints `{"total": 113.05, ...}` instead of `{"total": 119.0, ...}`. Only orders whose float subtotal is exactly 100.0 change.
- **Known gap (D5 as amended):** a basket that is 100.00 on paper but a hair under it as a float (3 x 21.40 + 35.80 = 99.99999999999999) is still not discounted. That is C2.
- **Touches:** `orders/domain/pricing.py:discounted` (`>` becomes `>=`), `tests/test_quote_cli.py` (the exactly-100 pin from R1 is renamed and its expected value becomes 113.05), `tests/test_quote.py` (regression tests at the use case: a subtotal of exactly the threshold is discounted; 99.99 is not).
- **Order:** after R6, in its own commit.
- **Commit subject:** `fix(quote): discount a subtotal of exactly 100.00 (ORD-31)`
- **Status:** done
- **Commit:** `8565efa`

### C2 - Float money: `quote` and `total` disagree, and thresholds misjudge some baskets (B2) - **deferred** (D6, D5)

- `quote` keeps its left-to-right subtotal, `amount + amount * rate`, and `amount - amount * 0.05`; `total` keeps `sum()` and `amount * (1 + rate)`. DE 10.50: 12.5 against 12.49.
- Baskets on a threshold on paper can miss it as floats: 3 x 21.40 + 35.80 (100.00) is not discounted; 9.94 + 0.03 + 0.03 (10.00) is rejected; 95.01 + 0.01 + 4.98 (100.00) is discounted today only through float error in the other direction.
- Pinned as-is by R1 so the refactor cannot change any of it silently, and marked in the code with warning comments. The root cause is money as `float` (`orders/domain/model.py:8`), which predates the branch; the fix is its own change across both commands.

## Non-goals

- **O1 (observation, pre-existing).** Money is a `float` (`orders/domain/model.py:8`, U4). A money value object would touch every layer and both commands. See C2.
- **O2 (skip).** Unknown flags are ignored (`orders/__main__.py:17-18`): `--notax` silently quotes with tax. The spec is silent; rejecting them changes the CLI contract.
- **O3 (skip).** A rejected quote prints its error on stdout and exits 0 (`orders/__main__.py:18-19`). The spec fixes only the text (R5); pinned as-is by R1.
- **O4 (observation, pre-existing).** `main` indexes `argv[1]`, `argv[2]` unchecked (`orders/__main__.py:11`); `FileTaxRates` re-reads the file on every call (`orders/adapters/rates_file.py:9-10`); `parse_order` does not validate `country` (`orders/adapters/cli.py:10`).
- **O5 (skip).** `main`'s two command branches could become per-command functions or a dispatch table (D2). Two short branches are simpler than a table (G2); `total`'s branch is outside the scope.
- **O6 (observation; codex finding 7, rejected).** Rounding to two decimals happens in the use case, for `total` (`orders/app/total.py:10`, on `main`) and now for `quote`. `docs/architecture.md` gives rounding no home. If it belongs in the domain, move both in one change.
- **Not planned:** unit tests for each domain step in isolation. R1 pins every branch and boundary through the public contract; more would restate it.

## Applied (Step 6)

- **Order applied:** R1, R2, R3, R4, R5, R6, C1, R7. One commit each, none amended.
- **Departures from the plan as written:**
  - R4: the error JSON is built by a small `format_error` beside `format_total` in `orders/adapters/cli.py`, instead of inline.
  - C1: the R1 pin `test_lines_are_added_left_to_right_at_the_discount_threshold` changed basket, from 95.01 + 0.01 + 4.98 to 90.02 + 0.07 + 9.91. Once 100.0 itself is discounted the first basket prints 95.0 under either way of adding, so it no longer tells the loop from `sum()`; the second one does (100.0 with the loop, 95.0 with `sum()`), and it prints 100.0 both before and after C1. It is also the known-gap basket of D5: 100.00 on paper, not discounted.
  - C1: the 99.99 control test sits in `tests/test_quote_cli.py`, not `tests/test_quote.py`.
- **Gates after:** format - not configured; `make lint` - pass; `make arch` - **pass** (was fail); build - not configured; `make test` - pass, 33 tests (was 4).
- **Baseline tests accounted for:** `test_total.TotalOrderTest` x2 unchanged; `test_quote.T.test_1` split into `QuoteOrderTest.test_quote_adds_tax_for_the_customers_country`, `test_quote_without_tax_is_the_subtotal`, `test_quote_with_shipping_adds_the_countrys_rate`, `test_subtotal_above_the_threshold_is_discounted`, `test_shipping_is_added_to_the_discounted_amount_when_tax_is_left_out` (same five expected values); `test_quote.T.test_2` renamed `QuoteCommandTest.test_order_below_the_minimum_is_reported_as_an_error` (same expected string).
- **Output sweep:** 20,505 `quote` invocations (4,101 payloads x 5 flag sets) run at `a6869ab`, at `4113fce` (all refactor items, before the fix), and at `HEAD`. Start against refactor-only: 1 line differs, the D11 input (`country: []`, `--no-tax --shipping`). Refactor-only against `HEAD`: 60 lines differ, every one with a subtotal of exactly 100 (C1). R7 changed none.
- **Architecture verdict after:** conforms. `orders/domain/pricing.py` imports only the standard library; the minimum rule is in the domain; `QuoteOrder` in `orders/app/` receives the port and the shipping table through its constructor; `orders/__main__.py` holds both configuration values and the wiring.

## Plan review

Reviewer: codex (`adversarial-review` through the plugin's companion script), one run, about 4m 40s, verdict `needs-attention`, 7 findings. Codex reviewed the plan when its items were numbered R1-R5; accepting finding 6 inserted the fakes item, so its R2-R5 are R3-R6 here. Ids below are the final ones. Every numeric claim was re-run against `a6869ab` before its disposition.

| # | Finding | Disposition | Evidence |
|---|---|---|---|
| 1 | [high] Replacing the subtotal loop with `sum()` changes quote totals (R3, R4) | accept | Python 3.12.3: loop 100.00000000000001 vs `sum()` 100.0 for 95.01 + 0.01 + 4.98; loop 9.999999999999998 vs 10.0 for 9.94 + 0.03 + 0.03. K7 rewritten: `quote_subtotal` keeps the loop; both baskets pinned in R1; D6 extended. |
| 2 | [high] C1 still misses some baskets totaling 100.00 | defer | 3 x 21.40 + 35.80 is 99.99999999999999. Reopened D5 with the user: C1 stays the comparison fix; float-edge baskets recorded under C2. The 99.99 control test is accepted into C1. |
| 3 | [medium] The shipping lookup raises for a non-hashable `country` (R5) | accept | `country: []` with `--no-tax --shipping` prints 32.0 today, and raises without `--no-tax`. Put to the user: accepted as a called-out behavior change (D11); R5's preservation claim corrected. |
| 4 | [medium] Early rejection and the tax-file access order are unpinned (R1, R4) | accept | Both paths work today with no rates file. R1 pins both from an empty working directory; R4 adds the use-case test with `FakeTaxRates({})`. |
| 5 | [medium] The discount-before-tax example passes with the order reversed (R1, R6) | accept | FR 200.00 is 228.0 either way; DE 130.00 is 146.97 against 146.96. Added to R1 and to R6. |
| 6 | [medium] The use-case item makes the app test depend on the file adapter (R3) | accept | `CLAUDE.md:6`. Fakes extracted first (new R2); R3's test call sites use `FakeTaxRates`; R6 adds a test at a non-production rate. |
| 7 | [medium] Rounding moves out of the domain into `QuoteOrder.run` (R3) | reject | `orders/app/total.py:10` on `main` rounds in the use case; `docs/architecture.md` assigns rounding no home; moving only quote's would split the idiom (U1). Recorded as O6. |
