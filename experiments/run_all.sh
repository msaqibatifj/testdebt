#!/usr/bin/env bash
# E1-E6 (+ ES sensitivity on dev) -> results/, logs/, paper/tables, paper/figures in one command, resumable
# (a finished run is skipped). Needs: scripts/setup_projects.sh done, .env with the Cerebras key, JNose jars.
# Seeds per config (1-3 everywhere) are in src/testdebt/team/gulsher/experiments/E*.json.
#   bash experiments/run_all.sh                    # test split, frozen (clean tree)
#   SPLIT=dev LIMIT=2 bash experiments/run_all.sh  # smoke test on dev, writes results/dev/E1..E5
#   RUN=0 bash experiments/run_all.sh              # no new runs: rebuild results/ and paper tables from runs/ (make reproduce)
set -euo pipefail
cd "$(dirname "$0")/.."
command -v mvn >/dev/null || export PATH="${MAVEN_HOME:-$HOME/apache-maven-3.9.9}/bin:$PATH"
X="python3 -m testdebt.team.gulsher.experiments"
if [ "${SPLIT:-test}" = dev ]; then
  for e in E1 E2 E3 E5; do $X run $e --dev --limit "${LIMIT:-2}"; $X summarize $e --dev; done
  exit 0
fi
for e in E1 E2 E3 E5 ES; do [ "${RUN:-1}" = 0 ] || $X run $e --frozen; $X summarize $e; done   # E5 after E3: its delta table needs E3
[ "${RUN:-1}" = 0 ] || python3 -m testdebt.team.hasan.agreement --split all   # E4 detector agreement, no LLM (needs JNose)
$X summarize E4
$X summarize E6
python3 -m testdebt.team.hasan.failures runs/E3_s3_s1 runs/E3_s3_s2 runs/E3_s3_s3 --name E3
python3 scripts/paired_extra.py >/dev/null
python3 -m testdebt.team.hasan.figures
python3 -m testdebt.team.hasan.gap_table --readme README.md

# the paper \input's these (paper/main.tex: \resultinput / \resultfig); never typed by hand
mkdir -p paper/tables paper/figures
for e in E2 E3 E5 E6 ES; do [ -f results/$e/table.tex ] && cp results/$e/table.tex paper/tables/$e.tex; done
[ -f results/E5/delta.tex ] && cp results/E5/delta.tex paper/tables/E5_delta.tex
[ -f results/E2/vs_paper.tex ] && cp results/E2/vs_paper.tex paper/tables/E2_vs_paper.tex
[ -f results/failures/E3_table.tex ] && cp results/failures/E3_table.tex paper/tables/failures.tex
[ -f results/gap_table.tex ] && cp results/gap_table.tex paper/tables/gap_table.tex
cp results/figures/*.pdf paper/figures/ 2>/dev/null || true
echo "done: results/, logs/, paper/tables/, paper/figures/"
