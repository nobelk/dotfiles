# Coverage measurement (clean-code Steps 6 and 7, subagent procedure)

Measure test coverage of the branch's changed units, not the whole repo. Inputs come from the dispatching prompt: the repo root, the changed-file list with statuses, the scratch directory `$tmp`, and - for the Step 7 re-run - the exact settings the Step 6 run recorded. You write only under `$tmp`.

**Done when** you return:

```
UNIT MAPPING: <changed file -> unit, one line per unit; test-only changes listed separately>
SETTINGS: <the exact commands, flags, and instrumentation scope - the Step 7 re-run reuses them verbatim>
TIERS: <tier> | measured | unavailable (<missing prerequisite>), one line per test tier
METRIC: <statement | line | branch> - total weighted by <how>
PER UNIT: <unit> | <covered>/<total> | <percent> | <self-coverage or consumer-coverage>
TOTAL: <covered>/<total> | <percent>
LEAST COVERED: <function or file:line ranges with 0% or the lowest coverage in changed code>
FAILURES: <a unit that would not compile or whose tests are red, with the error> | none
```

or `NOTHING TO MEASURE: no production source changed`, when that is so. If a unit fails to compile or its tests are already red, report it under `FAILURES` and stop measuring that unit - the main loop asks the user.

## Map changed files to units

State the mapping in the result.

- **Go** - the directory of each changed non-test `.go` file, deduped. Drop a directory only when it contains **no non-test `.go` files at all** in the current tree: a deleted file does not delete its package, and dropping the unit because one file went away hides the surviving code's coverage.
- **JS/TS, Python, Rust** - the module, package, or crate that owns each changed source file, per the repo's own layout. Keep the *unit* mapping and the *instrumentation* scope consistent: if the unit is a module, instrument the whole module, not only the changed files inside it, or the denominators will not match between runs.
- List `_test`-only changes separately: they affect coverage but add no production lines to cover.
- If **no production source changed at all**, return `NOTHING TO MEASURE`. Never fabricate a number.

## Measure

Prefer the project's own coverage entrypoint (`task cover`, `make coverage`, a package script) so local and CI agree, provided it can be scoped to the mapped units; otherwise use the language-native form. Use **identical settings for the before and after runs** - a lift measured with different flags is not a lift - and write every artifact into `$tmp`.

**Test tiers.** Find every configuration the repo's tests run under (Go build tags such as `integration` and `smoke`, pytest markers, separate test projects) from its test and coverage entrypoints and docs; a default-tier number alone can understate a unit whose tests sit behind a tag. Always measure the default tier. Measure a tagged tier as well when its prerequisites (a database, a container runtime, an address variable) are available, with the same settings before and after, and merge the profiles per statement block where the repo's own tooling does; otherwise list the tier as `unavailable` with the missing prerequisite. Report numbers per tier, and mark each gap measured on the default tier alone as `default-tier only`, after reading the unavailable tier's tests for the same behavior: a tier you could not run may already pin it.

- **Go** - `go test -race -count=1 -coverprofile="$tmp/cover.before.out" "${pkgs[@]}"`, then `go tool cover -func="$tmp/cover.before.out"`. Package patterns go **before** any `--`; `go test` treats `--` and everything after it as arguments for the test binary. Name the changed packages explicitly rather than `./...`: a changed package with no test file still reports `0.0%`, exactly the gap worth catching, and `-coverpkg` would drop it. For per-package totals, **aggregate the covered and total statement counts from the profile** (each non-header line ends in `<numStmt> <count>`; sum `numStmt` where `count > 0` over the sum of `numStmt`, per package) - averaging the rounded percentages `cover -func` prints does not give a statement-weighted total. This measures **in-package self-coverage**: a package covered deliberately by a consumer package's tests reads low here. Record that rather than chasing it, and only for such a package re-measure by naming the **consumer packages** as the test targets with `-coverpkg` pointed at the package under measurement (`go test -coverprofile="$tmp/consumer.out" -coverpkg=<pkg> "${consumer_pkgs[@]}"`). Label which semantic each number is.
- **JavaScript/TypeScript** - the repo's runner with coverage on (`vitest run --coverage`, `jest --coverage`), writing to `$tmp` (`--coverage.reportsDirectory` / `--coverageDirectory`). Restricting the *test* selection does not restrict *instrumentation*: set the coverage `include` / `collectCoverageFrom` to the mapped units, and make sure untested files are still reported - otherwise a source file no test imports vanishes instead of showing 0%. **Check the installed runner's version for how**: Jest uses `collectCoverageFrom`; Vitest used `coverage.all` in older versions and drops it in v4, where an explicit `coverage.include` glob supplies the same inclusion. Read the runner's own config docs rather than assuming a flag exists. `skipFull` is a reporter display option that hides fully-covered files; it changes nothing about what is instrumented.
- **Python** - one `--cov=<module>` per module (the flag is repeatable, not comma-joined): `pytest "--cov=$m1" "--cov=$m2" --cov-report=term-missing "--cov-report=xml:$tmp/coverage.xml"`.
- **Rust** - `cargo llvm-cov` (or `cargo tarpaulin`) restricted to the changed crates, with its output directed into `$tmp`.

For the Step 7 re-run, write to a distinct profile (`cover.after.out`) with the recorded settings unchanged.
