#!/usr/bin/env bash
# One command for E1-E6 -> results/. Needs: scripts/setup_projects.sh done, .env with the Cerebras key, mvn on PATH.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/apache-maven-3.9.9/bin:$PATH"
python3 -m experiments.run_all
python3 -m testdebt.team.hasan.gap_table --readme README.md
