# Development log

Date, failure seen, change, measured effect. Every effect below was measured on dev or pilot runs (`runs/`, copied to `logs/` when reported).

| Date | Failure seen | Change | Effect on dev |
|---|---|---|---|
| 2026-10-24 | Phase 1 PIT pilot: the baseline kill matrix was computed after the patch was written, so it measured the refactored code | `5cf24e3` compute the original matrix first | Pilot rerun after the fix (`runs/pit_pilot_b0replay_cli`, commit `1152007`): 5 Commons-cli tests, kill-set checked on 4, none of UTRefactor's published refactorings lost a mutant |
| 2026-10-25 | One exception stopped a whole run | `888b2eb` per-test error capture: decision `error`, run continues | 14 of 258 test records across all dev/pilot runs ended in `error` and the runs continued: 12 PIT/Gson (fixed 2026-11-06 below), 2 deliberate bad-key test (`gw_err`) |
| 2026-10-25 | No fixed evaluation split; tuning could leak into reporting | `0e1f7da` dev 80 / test 150 / rest 254, exact-size stratification; `764c7df` `--frozen` guard | n/a (design) |
| 2026-11-05 | Same refactored class re-ran PIT for every system/seed; secrets could reach traces; a crash could leave a checkout modified | `7610ce4` KillsetGate caches matrices by SHA-256 of the class source; `redact()` on all trace text; `RestoreCheck` after each test | PIT on a refactored class took 12-111 s (median about 80 s) over 25 measured attempts; the one cache hit took 0.0 s (`runs/*/state.jsonl` timings) |
| 2026-11-05 | Maven subprocess hangs | timeouts in `tools/` (Maven 900 s, PIT 3600 s, tsDetect 600 s); a timeout becomes decision `error`, resume retries it | 0 timeouts in 258 dev/pilot test records; no run hung since |
| 2026-10-26 | Only one detector (tsDetect); its ExceptionHandling/IgnoredTest labels disagree with JNose | `f41896e` JNose wrapper + consensus targets (G2) | JNose confirms 76.2% of [1]'s labels on all 484 tests (`results/E4`) |
| 2026-10-27 | Rule i counts smells only by tsDetect | `ed68e68` rule ii strict reduction (tsDetect AND JNose) | see `results/E3` once run |
| 2026-10-28 | No statistics, failure categories or figures tooling | `b486f33` stats, failures, manual sample, figures, gap table | n/a (tooling) |
| 2026-10-29 | Detector agreement unknown | `cbafe35` E4 agreement on all 484 tests | kappa 0.68-1.0 on most smells; ExceptionHandling 0.02, DuplicateAssert 0.42 |
| 2026-11-06 | PIT never produced a kill matrix for Gson or Jsoup: all 12 Gson tests in `dev_E3_s3_s1` ended in `error` ("Cannot create Launcher without at least one TestEngine"); every cached matrix was Commons-cli | `tools/pit.py` adds `pitest-junit5-plugin` only to JUnit 5 projects; Gson and Jsoup (JUnit 4) use PIT's built-in support | Gson `LongSerializationPolicyTest`: matrix in 37 s (was: error); Jsoup `NodeTest`: 25 test methods with kill sets in 141 s. Before: 12/25 dev s3 tests were `error`, all Gson |
| 2026-11-06 | `gap1` off dropped PIT, so the E5 -G1 run could not show lost mutants; two experiment runners disagreed on E1/E5 | `--gaps` on the CLI (`apply_gaps`), gap1 off = `--pit --killset-gate off`; one runner (`team/gulsher/experiments.py`); E1 = b0replay, E5 adds `minus_all`; `prompt_hash` in `config.json` | n/a (wiring); unit tests in `tests/test_run_experiment.py` |
| 2026-11-05 | No single entry point for E1-E6 | `a41462f` `run_system()` + `run_all.sh`, final trajectory event | smoke runs only (1 test each in `runs/E*`) |
