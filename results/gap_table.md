| Gap | Method / component | Metric | Base paper result | Our result (S3) | Addressed? |
|---|---|---|---|---|---|
| G1 | Kill-set gate (`killset_gate.py`) | Accepted outputs losing a mutant (%) | 2.17 ± 0.84 (b0, reproduced); 3.4 (b0replay, reproduced) | 0 | Fully |
| G2 | Consensus detector, tsDetect + JNose (`consensus.py`) | Smell reduction, rule ii (%) | 63.07 ± 1.31 (b0, reproduced); 54.6 (b0replay, reproduced); rule i: 86 / 89 / 91 (reported in [1]) | 52.47 ± 1.7 | Partially |
| G6 | Adaptive Supervisor + memory (`agents/supervisor.py`) | Accepted and safe (%) | 26 ± 1.76 (b0, reproduced); 11.8 (b0replay, reproduced) | 25.8 ± 1.56 | Partially |
