#!/usr/bin/env bash
# E1-E6 in order on the frozen commit; every step resumes where it stopped. Needs a clean tree (--frozen).
set -euo pipefail
cd "$(dirname "$0")/../../../.."
X="python3 -m testdebt.team.gulsher.experiments"
for e in E2 E1 E3 E5; do $X run $e --frozen; $X summarize $e; done
$X summarize E4
$X summarize E6
python3 -m testdebt.team.hasan.failures runs/E3_s3_s1 runs/E3_s3_s2 runs/E3_s3_s3 --name E3
python3 -m testdebt.team.hasan.figures
