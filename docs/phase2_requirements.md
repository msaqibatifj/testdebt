# Phase 2 requirements (AI4015, Group G2-10)

Deadline: **Sun 8 Nov 2026, 11:55 PM PKT**. Section `.tex` files go to Saqib by **Sun 4 PM**. Tag `phase2-final` by **9 PM**, submit by **11 PM**.
Members: M Saqib Atif (23I-0769, group head), Gulsher Khan (23I-0066), Hasan Altaf (23I-0698).
Status key: [x] done in repo, [~] partly done, [ ] not done.

## Gulsher Khan: pipeline, verification, data, base-paper reproduction

| ID | Requirement | Status |
|---|---|---|
| r5 | Frozen dev/test splits in `data/splits/` (`dev_ids.txt`/`test_ids.txt` or script plus checksums), README table filled. Never tune on test. | [x] `.jsonl` files + `SHA256SUMS` + README |
| s3 | Gap 1 as its own module behind `gaps.enabled("gap1")`, listed in `KNOWN_GAPS`; pipeline runs with `gap1: false` | [x] kill-set gate (`team/gulsher/killset_gate.py`), switch is `--gaps` / `--killset-gate off` (PIT still measures) |
| s5 | Real tool wrappers (test runner, compiler/build, AST parser, coverage); each call logged as `tool_call`/`tool_result` | [~] JaCoCo coverage not implemented; PIT kill-set used instead |
| s6 | Verification, retry (cap, e.g. 3), feed error back, roll back to original and log `final` with `failure_mode` | [x] |
| r4 | Pinned `requirements.txt`, `.env.example`, no secrets in git history | [x] checked 2026-11-06, clean |
| e2 | E2 UTRefactor on identical split and metrics; label each number **reproduced** or **paper-reported** (`source: paper-reported`) | [~] b0replay / b0 run; paper numbers not entered |
| w6 | Paper: Experimental Setup (dataset, split sizes, baselines, model ID, temperature, seeds, hardware, tool versions) | [x] |
| w6 | Paper: Evaluation Methodology (formal metric definitions, 3 seeds, mean ± std, same split, metric differences) | [x] |
| w8 | Paper: Limitations and Validity (internal, external, construct, rate limits, single model family) | [x] |
| w8 | Paper: Conclusion (findings per gap, lessons, future work) | [~] numbers `[TODO]` |

## Hasan Altaf: detection, metrics, experiments, failure analysis

| ID | Requirement | Status |
|---|---|---|
| s4 | Gap 2 as its own module behind `gaps.enabled("gap2")`; pipeline runs with `gap2: false` | [x] `--detector tsdetect` is the off switch |
| r3 | Unit and integration tests for deterministic modules (detectors, metrics, parsers, gap switches); one integration test with mocked LLM; `pytest -q` before each push | [x] 91 pass, 2 skip |
| e1 | E1 Phase 1 baseline, 3 seeds | [ ] not run |
| e4 | One experiment per gap hypothesis (H1: adding X increases Y on subset Z), report the subset number | [~] E4-G2 agreement done; G1/G6 subsets wait for runs |
| e5 | Ablation: `full`, `minus_gap1`, `minus_gap2`, `minus_all`; `full` must match E3; report change from `full` | [ ] not run |
| e8 | Failure modes categorized with counts and percentages on test (`results/tables/failures.md`); category names agreed with Gulsher | [~] tool done, needs runs |
| e9 | 2 success + 2 failure trajectories with step-by-step post-mortems (root cause and fix for failures) | [ ] |
| w7 | Paper: Results by gap (RQ1, RQ2), gap-resolution table, mean ± std, E2 labelled reproduced/paper-reported | [~] skeleton |
| w7 | Paper: Ablation and Comparative Analysis (E5 table, per-component contribution, E6 tokens/latency/tool calls vs baseline) | [~] skeleton |
| w7 | Paper: Failure Analysis (distribution table or chart, 4 trajectory walkthroughs) | [~] skeleton |
| fig | Figures in `paper/figures/` (PDF/PNG), readable fonts, numbered, captioned, referenced in text | [ ] |

## M Saqib Atif: orchestration, integration, paper lead, submission

| ID | Requirement | Status |
|---|---|---|
| p2 | README "Phase 1 feedback addressed" and "Changes since Phase 1" | [~] needs members' feedback lines |
| p3 | Confirm base paper (UTRefactor) and gaps unchanged; any change needs **written** approval from Meemon Khan | [ ] confirm |
| s1 | End-to-end pipeline as one agentic workflow on the full evaluation suite, gaps via `GapSwitch` | [x] `run_system()` |
| s2 | Trajectory logging in every agent: `reason`, `tool_call`/`tool_result` (with token counts), `state`, `retry`, `error`, one `final` with `failure_mode` | [x] |
| r1 | README: overview, setup, run steps, gap-resolution table | [~] table empty until runs |
| r2 | CLI entry point, e.g. `python -m veriref --input FooTest.java --gaps gap1,gap2` | [~] `veriref` and `testdebt` both take `--gaps`; dataset-based, no `--input` file mode |
| r6 | `bash experiments/run_all.sh` reproduces E1-E6 into `results/` | [x] one runner (`team/gulsher/experiments.py`), reduced seed grid; [ ] not run on test |
| r8 | Tag `phase2-final` and push before deadline; only code in the tag is graded | [ ] |
| e3 | E3 full system on test, 3 seeds, mean ± std | [ ] |
| e6 | E6 efficiency and reliability: latency, tokens, tool calls, retries, recovery rate; cost $0 on free tier | [ ] |
| e7 | Log model ID, temperature, system-prompt hash, seed, git commit on every run | [x] all in `config.json`, incl. `prompt_hash` |
| w1 | IEEEtran two-column, 8-10 pages including references | [ ] check page count |
| w2 | Front matter: title, G2-10, names, IDs, institutional emails | [~] verify |
| w3 | Abstract, 150-250 words (write last) | [ ] |
| w4 | Introduction (ends with RQs per gap and contributions), Related Work, Problem Formulation (input suite, smell set, tool set, state space, output, constraints) | [~] |
| w5 | Proposed System plus architecture diagram, same figure in `docs/architecture.md` | [x] diagram exists |
| u1 | PDF named `Phase2_G2-10_23I-0769_Paper.pdf` | [ ] |
| u2 | LaTeX source ZIP via `bash paper/make_zip.sh` | [ ] |
| u3 | Links to repo (public or shared with supervisor) and the `phase2-final` tag | [ ] |
| u4 | Upload to Google Classroom (group head only) | [ ] |

## Shared by everyone

| ID | Requirement | Status |
|---|---|---|
| p1 | Every Phase 1 supervisor comment addressed; one line per comment sent to Saqib | [ ] comments not in repo |
| s7 | Devlog entries: date, failure seen, change, measured effect on dev (`docs/devlog.md`) | [~] "effect" cells are `TODO` |
| r7 | Commits under your own name (balanced history) | [~] 24 / 4 / 3 commits for Saqib / Hasan / Gulsher |
| e10 | Gap-resolution table filled, identical in README and paper; check against `results/` | [ ] needs `results/gap_verdicts.json` |
| w9 | About 10 references with DOIs each (25-30 total, peer-reviewed preferred) | [~] 26 entries; DOIs unverified, run `check_refs.py` |
| w10 | Every number in the paper traces to `results/` or `logs/` | [ ] |

## Handoffs

| From → To | What | By |
|---|---|---|
| Gulsher → everyone | Frozen splits in `data/splits/` | Fri morning |
| Gulsher → Saqib, Hasan | Gap 1 module behind `gaps.enabled("gap1")` | Fri night |
| Gulsher → Hasan | `failure_mode` values used in `final` steps | Fri night |
| Hasan → Saqib | Gap 2 module behind `gaps.enabled("gap2")` | Fri night |
| Saqib → Gulsher, Hasan | Working `run_system()` and trace logging | Fri night |
| Gulsher, Hasan → Saqib | `.tex` sections, figures, E2 numbers | Sun 4 PM |

## General rules

- Run each stochastic experiment with 3 seeds and report mean ± std; use the same split for every system.
- Label every E2 number as **reproduced** or **paper-reported**.
- Never tune prompts or thresholds on the test split.
- Check the git history for leaked keys; rotate on Cerebras if one is found.
- Do not delete `backups/`.
