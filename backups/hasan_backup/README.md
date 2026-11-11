# Hasan backup (written by Saqib as a fallback; replace with Hasan's own work if it arrives)

Hasan's code is already in the repo (`team/hasan/`: JNose, consensus G2, agreement E4, stats, failures, figures, gap_table, check_refs, manual sampling), and E4 detector agreement is in `results/E4/`.
What is NOT done is everything that needs the test-split runs (E1, E5, E3 numbers), so his paper sections are a skeleton with `[R: file]` placeholders: the structure, hypotheses and category list are real, the numbers are not.

| Plan item | File | State |
|---|---|---|
| w7 Results, Ablation, Failure Analysis | `results_ablation_failures.tex` | skeleton; numbers wait for the test-split runs |
| w9 ~10 references | `refs.bib` | 12 entries; **DOIs from memory, run `check_refs.py`** |
| e4 hypotheses H1-H3 and subsets | in the .tex and below | written |
| e8, e9, figures, e10, r3, p1, s7 | `checklist.md` | commands and status |

## Commands once the test-split runs exist
```bash
python3 -m testdebt.team.gulsher.experiments summarize E3        # or: bash experiments/run_all.sh
python3 -m testdebt.team.hasan.failures runs/E3_s3_s1 runs/E3_s3_s2 runs/E3_s3_s3 --name E3 \
    --case success1 '<id>' --case failure1 '<id>'                # ids from the decisions of those runs
python3 -m testdebt.team.hasan.figures
python3 -m testdebt.team.hasan.gap_table --readme README.md      # after editing results/gap_verdicts.json
python3 -m testdebt.team.hasan.check_refs paper/refs.bib paper/*.tex
```
