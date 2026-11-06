# Team parts: who owns what

This folder holds a complete backup implementation of Gulsher's and Hasan's Phase 2 work, one package per owner,
on the local branch `backup/full-system`. When an owner pushes their own version, theirs replaces the file here;
the wiring points listed at the end are the only places the rest of the system touches these packages.

Saqib's parts (G6 and orchestration) live in the core package, not here: `agents/` (planner, supervisor,
memory), `trace.py`, `cli.py`, `data/splits.py`.

## Gulsher: G1 and infrastructure (`team/gulsher/`)

| File | What it does | Plan item |
|---|---|---|
| `killset_gate.py` | G1 kill-set gate: K(original) ⊆ ∪ K(new tests) from PIT; baseline and after-run matrices cached by SHA-256 of the class source; lost mutants named in the retry feedback; `enforce=False` measures only | G1, PIT caches |
| `robustness.py` | `RestoreCheck` (project checkout must be unchanged after every test, else the run stops); `redact` (no API key in any trace file) | robustness, secrets check |
| `experiments.py` | one entry point for E1-E6: `run` (fixed run ids, resumable, `--dev` dry runs) and `summarize` (results/E*/runs.csv, summary.json, table.tex; E4 paired tests; E6 cost/latency/reliability) | experiment runner, E1, E2, E4-G1, E6 |
| `experiments/E1.json` … `E5.json` | which systems, flags, split and seeds each experiment runs | experiment YAMLs (JSON: no YAML library needed) |
| `../../../../experiments/run_all.sh` | E1-E6, failures, figures, gap table (calls this runner) | `experiments/run_all.sh` |
| `../../../../.github/workflows/ci.yml` | pytest on every push (has to live in `.github/`) | CI |

Not built (say so if asked): parallel workers per project. The LLM rate limit (5 requests/min) is the bottleneck;
run one `experiments.py run` per project in separate terminals with `--only` if PIT time dominates.
Subprocess timeouts already exist in `tools/` (Maven 900 s, PIT 3600 s, tsDetect 600 s); a timeout becomes
decision `error`, and resuming the run retries it.

## Hasan: G2 and evaluation (`team/hasan/`)

| File | What it does | Plan item |
|---|---|---|
| `jnose.py`, `jnose/JNoseMain.java`, `get_jnose.sh` | JNose as a second detector, same method isolation as tsDetect; jnose-core 0.9.0 (last release for Java 21) | JNose wrapper, name mapping |
| `consensus.py` | G2: targets = smells both detectors confirm (`--detector consensus`), or either (`union`); "gone" only when both agree; `--detector tsdetect` is the -G2 ablation | consensus detector |
| `agreement.py` | E4-G2 without LLM: per-smell agreement and kappa of the two detectors on all 484 originals, and how many of [1]'s labels each confirms | detector agreement |
| `manual.py`, `labelling_guide.md` | rule iii: draw the 100-test sample as a labelling sheet, then score it (kappa labeller-labeller and detector-human, manual reduction) | manual sample, labelling guide |
| `stats.py` | mean ± sd, exact McNemar, Wilcoxon signed-rank, bootstrap CI, Holm, Cohen's kappa (pure Python) | stats module |
| `failures.py` | failure categories from the final report (plan's taxonomy) and counts | failure classifier |
| `figures.py` | paper figures from results/ only: systems, ablation, cost, failures | figures scripts |
| `failures.py --case NAME TEST_ID` | exports a representative case to `cases/NAME.md` (timeline + final code) and `cases/NAME.jsonl` | D09 |
| `gap_table.py` | gap-resolution table from `results/E2`, `E3` → `results/gap_table.{md,tex}`, and the README block between `<!-- gap-table -->` markers; "Addressed?" comes from the hand-written `results/gap_verdicts.json` | D10 |
| `check_refs.py` | ≥25 references, each with a resolving DOI (or a URL when there is none), all cited, none missing | E05 |
| rule ii in `../../eval/metrics.py` | `smell_reduction_strict`, and accepted-and-safe under rule ii | rules i/ii/iii |

First result (`results/E4/g2_agreement.json`, all 484 tests): JNose confirms 76.2% of [1]'s labels. The
detectors disagree most on ExceptionHandling (tsDetect 224, JNose 10) and IgnoredTest (0 vs 102; jnose-core 0.9.3
fixed an IgnoredTest false positive, but 0.9.3 needs Java 25).

## Where the core calls into these packages

| Core file | Change |
|---|---|
| `verify.py` | uses `KillsetGate`; runs JNose after the patch (`smells_after_jnose`); records `timings` |
| `contracts.py` | `VerificationReport` gains `killset_enforced`, `lost_mutants`, `smells_after_jnose`, `timings` |
| `pipeline.py` | `Config.detector`; a kill-set loss is a failure stage only when the gate is enforced |
| `agents/detection.py`, `agents/supervisor.py` | targets and "smells left" through `consensus` |
| `cli.py` | `--killset-gate`, `--detector`; JNose loaded when present; `RestoreCheck` around every test |
| `trace.py` | every traced text goes through `redact` |
| `eval/metrics.py` | rule ii |

## Commands

```bash
bash src/testdebt/team/hasan/get_jnose.sh                          # once
python3 -m testdebt.team.hasan.agreement --split all               # E4-G2, no LLM
python3 -m testdebt.team.hasan.failures runs/E3_s3_s1 --name E3 --case success1 '<test id>'   # + a case
python3 -m testdebt.team.hasan.gap_table --readme README.md        # gap table into results/ and the README
python3 -m testdebt.team.hasan.check_refs paper/refs.bib paper/*.tex
python3 -m testdebt.team.gulsher.experiments run E3 --dev --limit 5  # try the pipeline on dev
python3 -m testdebt.team.gulsher.experiments run E3 --frozen       # reported runs (clean tree)
python3 -m testdebt.team.gulsher.experiments summarize E3
bash experiments/run_all.sh                                       # everything, resumable (same runner)
```
