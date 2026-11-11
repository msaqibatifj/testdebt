# Gulsher backup (written by Saqib as a fallback; replace with Gulsher's own work if it arrives)

Gulsher's code is already in the repo (`team/gulsher/`: G1 gate, robustness, experiments runner, Dockerfile, CI).
This folder covers the non-code parts of his plan. Nothing here has numbers that are not in the repo; every gap is a `[TODO ...]`.

| Plan item | File | State |
|---|---|---|
| w6 Experimental Setup | `setup.tex` | drafted from repo facts; hardware line TODO |
| w6 Evaluation Methodology | `methodology.tex` | drafted from `eval/metrics.py`; metric-difference list TODO |
| w8 Limitations, Conclusion | `limitations_conclusion.tex` | Limitations done; Conclusion needs E3/E5 numbers |
| w9 ~10 references | `refs.bib` | 11 entries; **DOIs from memory, run `check_refs.py`** |
| s7 devlog | `devlog.md` | dated entries from git history; "measured effect" columns TODO |
| r4 secrets, requirements, .env.example | `checklist.md` | secrets check done (clean); pin requirements |
| e2 E2 labels reproduced vs paper-reported | `checklist.md` | not done: needs `E2_base_paper` numbers from the paper |
| p1 Phase 1 feedback line | `checklist.md` | I do not have the supervisor's comments: fill in |
| r5 splits README | `checklist.md` | `data/splits/README.md` missing (table text provided) |

Use: `\input{backups/gulsher_backup/setup}` etc. in `paper/main.tex` (or copy the files into `paper/`), and append `refs.bib` to `paper/refs.bib`.
