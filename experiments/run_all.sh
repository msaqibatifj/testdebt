#!/usr/bin/env bash
# E1-E6 -> results/ in one command, resumable (a finished run is skipped). Needs: scripts/setup_projects.sh done,
# .env with the Cerebras key, JNose jars. Reduced grid: seeds per config are in src/testdebt/team/gulsher/experiments/E*.json.
#   bash experiments/run_all.sh                    # test split, frozen (clean tree), writes results/E1..E6
#   SPLIT=dev LIMIT=2 bash experiments/run_all.sh  # smoke test on dev, writes results/dev/E1..E5
set -euo pipefail
cd "$(dirname "$0")/.."
command -v mvn >/dev/null || export PATH="${MAVEN_HOME:-$HOME/apache-maven-3.9.9}/bin:$PATH"
X="python3 -m testdebt.team.gulsher.experiments"
if [ "${SPLIT:-test}" = dev ]; then
  for e in E1 E2 E3 E5; do $X run $e --dev --limit "${LIMIT:-2}"; $X summarize $e --dev; done
  exit 0
fi
for e in E1 E2 E3 E5; do $X run $e --frozen; $X summarize $e; done
python3 -m testdebt.team.hasan.agreement --split all      # E4 detector agreement, no LLM
$X summarize E4
$X summarize E6
python3 -m testdebt.team.hasan.failures runs/E3_s3_s1 runs/E3_s3_s2 runs/E3_s3_s3 --name E3
python3 -m testdebt.team.hasan.figures
python3 -m testdebt.team.hasan.gap_table --readme README.md
