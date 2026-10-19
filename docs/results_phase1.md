# Phase 1 results

All numbers below were produced by the code in this repo. Re-create them with the command shown.

## 1. Reproducing UTRefactor's inputs (data side of D1)

The paper does not name the project commits it used, and today's HEADs differ (for example, Commons-cli later
removed `public` from its JUnit 5 tests, and tsDetect ignores non-public test methods, so it finds no smells there).
`testdebt.eval.utr_dataset pin` scans each project's history for the commit whose test files contain the most
of UTRefactor's published input methods verbatim.

| Project | Pinned commit | Date | Inputs found verbatim | Tests in eval set |
|---|---|---|---|---|
| Commons-cli | fb6293f | 2024-08-30 | 98.7% of 78 | 77 |
| Gson | 58eaac3 | 2024-09-22 | 97.9% of 243 | 238 |
| Jsoup | 5136929 | 2020-03-01 | 98.8% of 171 | 169 |
| Total | | | | 484 tests, 1,086 smells |

Note: the replication package's result reports cover 492 tests. The proposal's figure of 593 tests (Table 2 of [1])
includes tests whose reports are not in the package. Use 484 as the evaluation set and state this in the report.

Command: `bash scripts/setup_projects.sh --repin`

## 2. Our method-level tsDetect reproduces the paper's smell labels

tsDetect is run with the jar from the UTRefactor package, once per test method (the class with every other test removed).

- Every smell label in [1] for the 484 tests is also reported by our run (1,086 of 1,086).
- On 445 tests (92%), the smell set is identical.
- On the other 39 tests (1 Commons-cli, 38 Jsoup), we report additional smells. These are mostly types that have no DSL rule in [1].

## 3. B0-replay: UTRefactor's own published refactorings, measured by our verifier (no LLM calls)

Run: `python3 -m testdebt.eval.run_baseline --system b0replay --eval data/eval_set.jsonl --skip-verify`

| Project | Tests | Usable code | Smell reduction (tsDetect, rule i) | Paper (Table 5) | Within 5 points? |
|---|---|---|---|---|---|
| Commons-cli | 77 | 97.4% | 84.0% | 86% | yes |
| Gson | 238 | 97.9% | 57.4% | 89% | no (-31.6) |
| Jsoup | 168 | 97.6% | 53.0% | 91% | no (-38.0) |
| All | 483 | 97.7% | 58.9% | | |

Per smell, all projects:

| Smell | Targeted | Removed | % |
|---|---|---|---|
| EagerTest | 337 | 105 | 31.2 |
| AssertionRoulette | 305 | 196 | 64.3 |
| ExceptionHandling | 222 | 202 | 91.0 |
| SensitiveEquality | 79 | 64 | 81.0 |
| MagicNumberTest | 53 | 28 | 52.8 |
| DuplicateAssert | 39 | 30 | 76.9 |
| ConditionalTestLogic | 10 | 8 | 80.0 |

How to read this: on Commons-cli, our measurement agrees with the paper, which checks our pipeline. On Gson and Jsoup
it does not. The gap comes mostly from:

- Eager Test after a split. Each new test still calls more than one production method, for example a setter and a getter.
- Assertion Roulette when `assertThrows` has no message. The DSL in [1] exempts `assertThrows`, but tsDetect does not.

This is early evidence for gap G2: the reported reduction depends on how "removed" is measured. It must be
confirmed before it is written up as a finding. Steps:

1. Check the counting in UTRefactor's own Java detector (`src/main/.../detection`).
2. Add JNose as the second detector.
3. Label the 100-test manual sample.

The numbers above come from tsDetect alone (`--skip-verify`, no compile or run).

First full run with compile and test execution (Maven in WSL, JDK 17), 2026-10-19:

| Run | Tests | Compile % | Pass % (= accepted) | Smell reduction (tsDetect) | Accepted losing ≥1 mutant (G1a) |
|---|---|---|---|---|---|
| b0replay, commons-cli | 77 | 87.0 | 84.4 | 86.4 (125 targeted, 108 removed) | Phase 2 (PIT) |
| Paper, Commons-cli (`result/cli/outline.txt` in [1]'s package) | 78 | 93 (CPR) | 89 (EPR) | 86 | not measured |

Smell reduction matches the paper (86.4 vs 86, so D1 holds for Commons-cli). Compile and pass rates are 6 and 5 points
lower. The 12 rejected tests are:

- 9 that do not compile. For example, `testLongOptionQuoteHandlingWithoutStrip` has a statement after `return` and
  uses `cl` inside its own initializer.
- 2 that compile but fail. In `testShortOptionQuoteHandlingWithoutStrip`, the new setup helper re-creates `options`
  and wipes the test's fixture. The other is `testObjectPattern`.
- 1 that drops its only assertion (`testnstantiableEquals`).

All of these were published in [1] as refactorings. Before quoting the 6-point compile gap, check whether [1]
fixed its imports by hand: our verifier adds missing JUnit imports automatically for every system.

## 4. LLM baseline pilot

| System | Tests | Accepted % | Compile % | Pass % | Reduction % | Tokens/test |
|---|---|---|---|---|---|---|
| b0 (gpt-oss-120b), pilot: first 10 Commons-cli tests | 10 | 90 | 100 | 90 | 100 (19/19) | 2,462 |
| b1 (gpt-oss-120b) | Phase 2 | | | | | |

On the same 10 tests, UTRefactor's published outputs (b0replay) also get 9/10 accepted. The rejected test differs:
the published `testLongOptionQuoteHandlingWithoutStrip` does not compile. Our b0 `testDeprecated` compiles but fails an
assertion ("Deprecated handler should be invoked…"), which means the refactoring changed what the test checks. A
compile-only check misses that kind of failure; the test-run gate catches it.

Cost and time: 2,462 tokens per test (about 1.2M tokens for the 484-test set, one pass, no retries) and about
13 s per test, including the 5-requests-per-minute pacing.

## 5. Gson: published UTRefactor outputs do not compile against Gson's own test setup

On the first 125 Gson tests, b0replay accepts 8 (6.4%). Error types:

| Error | Count |
|---|---|
| cannot find symbol | 54 |
| no suitable method found | 23 |
| Truth `isEqualTo` called with a message argument | 17 |
| void cannot be dereferenced | 6 |
| other | 17 |

A static scan of all 238 published Gson refactorings finds:

- 131 call `assertDoesNotThrow`, which is JUnit 5 only. Gson's tests at the matched commit are JUnit 4.
- About 61 pass a message argument to a Truth assertion. Truth has no such method.
- 30 use Hamcrest matchers.

[1] reports a 94% compile rate for Gson, so it must have compiled in a different setup (extra libraries or manual
fixes). We report Gson strictly, "against the project's own test dependencies at the matched commit", and note the
difference. We do not claim [1] is wrong.
