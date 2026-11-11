# Hasan: remaining items (status 2026-11-06)

| Item | Status | What is left |
|---|---|---|
| s4 Gap 2 behind a switch | done in code | `--detector tsdetect` is the off switch; `gap2` maps to it in `experiments/run_experiment.py` |
| r3 tests | mostly there | `tests/` has consensus, stats, smells, end-to-end mock, failures/manual, trace, run_experiment. Missing: a test for each metric in `eval/metrics.py` with a hand-computed example (rule ii strict, accepted_safe, Wilson CI). Run `pytest -q` (88 pass, 3 skip). |
| e1 baseline, 3 seeds | not run | E1 is `b0replay` (no LLM, deterministic), so one seed is enough: say so instead of running 3 |
| e4 gap-wise | E4-G2 agreement done on all 484 | hypotheses H1-H3 are written in the .tex; G1 and G6 subset numbers need the E3/E5 test runs |
| e5 ablation | not run on test | `-G1`, `-G2`, `-G6` and memory-off exist in `experiments/run_all.py`; check the full row equals E3 (same cache keys, so it does) |
| e8 failure counts | tool done | `failures.py` needs real runs; categories are listed in the .tex |
| e9 2+2 trajectories | not chosen | `--case` exports them; pick one accepted-with-retry test, one clean accept, and a failure from each of the two largest categories |
| figures | not made | `paper/figures/` does not exist; run `figures.py`, number/caption/reference each |
| e10 gap rows | empty | `results/gap_verdicts.json` is hand-written and not created yet |
| manual sample (rule iii) | not done | 100 test-split tests, two labellers, `labelling_guide.md`; if there is no second labeller, report rule iii as not done rather than a one-person kappa |
| p1 feedback line | missing | supervisor comments are not in the repo |
| s7 devlog | missing | `docs/devlog.md` does not exist. Hasan's dated facts: 2026-10-26 JNose wrapper and consensus (`f41896e`), rule ii (`ed68e68`), stats/failures/figures/gap table (`b486f33`), E4 agreement (`cbafe35`). Effects: JNose confirms 76.2% of [1]'s labels (`results/E4`). |
