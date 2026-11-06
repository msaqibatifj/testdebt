# Architecture

![Architecture: baselines and the S3 multi-agent system](architecture.png)

Supervisor drives Detection (tsDetect + JNose consensus, G2), Planner, Refactor and Verifier (kill-set gate, G1); adaptive policy and memory are G6. Same figure as the paper.

Gap switches: G1 `--pit` (kill-set gate), G2 `--detector consensus|tsdetect`, G6 `--policy`, `--memory`. Every step is a trajectory event in `runs/<id>/trajectories/`.
