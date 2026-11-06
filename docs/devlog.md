# Development log

Date, failure seen, change, measured effect. Effects marked TODO must be measured from `results/dev` or `runs/` before they are cited.

| Date | Failure seen | Change | Effect on dev |
|---|---|---|---|
| 2026-10-24 | Phase 1 PIT pilot: the baseline kill matrix was computed after the patch was written, so it measured the refactored code | `5cf24e3` compute the original matrix first | TODO rerun pilot (`bash scripts/phase1_pilots.sh pit`) |
| 2026-10-25 | One exception stopped a whole run | `888b2eb` per-test error capture: decision `error`, run continues | TODO count of `error` decisions on dev |
| 2026-10-25 | No fixed evaluation split; tuning could leak into reporting | `0e1f7da` dev 80 / test 150 / rest 254, exact-size stratification; `764c7df` `--frozen` guard | n/a (design) |
| 2026-11-05 | Same refactored class re-ran PIT for every system/seed; secrets could reach traces; a crash could leave a checkout modified | `7610ce4` KillsetGate caches matrices by SHA-256 of the class source; `redact()` on all trace text; `RestoreCheck` after each test | TODO PIT time saved on a 5-test dev run |
| 2026-11-05 | Maven subprocess hangs | timeouts in `tools/` (Maven 900 s, PIT 3600 s, tsDetect 600 s); a timeout becomes decision `error`, resume retries it | TODO |
| 2026-10-26 | Only one detector (tsDetect); its ExceptionHandling/IgnoredTest labels disagree with JNose | `f41896e` JNose wrapper + consensus targets (G2) | JNose confirms 76.2% of [1]'s labels on all 484 tests (`results/E4`) |
| 2026-10-27 | Rule i counts smells only by tsDetect | `ed68e68` rule ii strict reduction (tsDetect AND JNose) | see `results/E3` once run |
| 2026-10-28 | No statistics, failure categories or figures tooling | `b486f33` stats, failures, manual sample, figures, gap table | n/a (tooling) |
| 2026-10-29 | Detector agreement unknown | `cbafe35` E4 agreement on all 484 tests | kappa 0.68-1.0 on most smells; ExceptionHandling 0.02, DuplicateAssert 0.42 |
| 2026-11-06 | `gap1` off dropped PIT, so the E5 -G1 run could not show lost mutants; two experiment runners disagreed on E1/E5 | `--gaps` on the CLI (`apply_gaps`), gap1 off = `--pit --killset-gate off`; one runner (`team/gulsher/experiments.py`); E1 = b0replay, E5 adds `minus_all`; `prompt_hash` in `config.json` | n/a (wiring); unit tests in `tests/test_run_experiment.py` |
| 2026-11-05 | No single entry point for E1-E6 | `a41462f` `run_system()` + `run_all.sh`, final trajectory event | smoke runs only (1 test each in `runs/E*`) |
