# Team parts: who owns what

One package per owner. Saqib's parts (G6 and orchestration) live in the core package, not here: `agents/` (planner,
supervisor, memory), `trace.py`, `cli.py`, `data/splits.py`. Gulsher's package (`team/gulsher/`: G1 kill-set gate,
experiment runner, CI) is added by him.

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

## Where the core calls into team/hasan

| Core file | Change |
|---|---|
| `verify.py` | runs JNose on the refactored methods after the patch (`smells_after_jnose`) |
| `contracts.py` | `VerificationReport.smells_after_jnose` (None = JNose not run) |
| `pipeline.py` | `Config.detector` (`consensus` by default for S3) |
| `agents/detection.py`, `agents/supervisor.py` | targets and "smells left" through `consensus` |
| `cli.py` | `--detector`; JNose loaded when its jars are present |
| `eval/metrics.py` | rule ii |

## Commands

```bash
bash src/testdebt/team/hasan/get_jnose.sh                          # once
python3 -m testdebt.team.hasan.agreement --split all               # E4-G2, no LLM
python3 -m testdebt.team.hasan.failures runs/E3_s3_s1 --name E3 --case success1 '<test id>'   # + a case
python3 -m testdebt.team.hasan.gap_table --readme README.md        # gap table into results/ and the README
python3 -m testdebt.team.hasan.check_refs paper/refs.bib paper/*.tex
```
