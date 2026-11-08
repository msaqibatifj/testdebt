#!/usr/bin/env bash
# Seeds 2 and 3: package them, then commit their logs on a new branch hasan/seeds-2-3 (from origin/main) and push it.
# Logs use the same layout as logs/<run_id>/ for seed 1: config.json, report.json, state.jsonl, trajectories.tar.gz.
# Raw runs/ (LLM and PIT caches) are not committed. Run in Ubuntu; git asks for your GitHub username and token at the push.
set -uo pipefail
REPO=/mnt/c/Users/ha797/Downloads/AgenticProj_backup_2026-11-06_v4/AgenticProj
BR=hasan/seeds-2-3
export GIT_AUTHOR_NAME="Hasan Altaf" GIT_AUTHOR_EMAIL="ha7971768@gmail.com" GIT_COMMITTER_NAME="Hasan Altaf" GIT_COMMITTER_EMAIL="ha7971768@gmail.com"
echo "== 1/4 packaging"; bash "$REPO/scripts/run_helpers/package_seeds.sh" >/dev/null && echo "packages in _hasan_runs/seeds"
git config --global --add safe.directory "$REPO" 2>/dev/null
cd "$REPO" || exit 1
echo "== 2/4 new branch $BR from origin/main"
git fetch -q origin || { echo "git fetch failed"; exit 1; }
if git rev-parse -q --verify "$BR" >/dev/null; then git checkout -q "$BR"; else git checkout -q -b "$BR" origin/main; fi || { echo "checkout failed: $(git status --short | head -5)"; exit 1; }
echo "   on $(git branch --show-current) at $(git log --oneline -1 | cut -c1-60)"
echo "== 3/4 copying logs of the seed-2/3 runs"
shopt -s nullglob; n=0
for d in "$HOME"/AgenticProj "$HOME"/AgenticProj_{e1,c,d,e,f,g,h,i,j,k,l}; do
  for r in "$d"/runs/E2_*_s[23] "$d"/runs/E5_*_s[23] "$d"/runs/ES_*_s[23]; do
    id=$(basename "$r"); [ -f "$r/report.json" ] || { echo "   skip $id (no report: unfinished)"; continue; }
    mkdir -p "logs/$id"; for f in config.json report.json state.jsonl; do [ -f "$r/$f" ] && cp -f "$r/$f" "logs/$id/"; done
    [ -d "$r/trajectories" ] && tar czf "logs/$id/trajectories.tar.gz" -C "$r" trajectories
    n=$((n+1)); done; done
echo "   $n runs copied"
if grep -rlE "csk-[A-Za-z0-9]{20,}" logs/E2_*_s[23] logs/E5_*_s[23] logs/ES_*_s[23] >/dev/null 2>&1; then echo "STOP: something that looks like an API key is in the logs; nothing committed."; exit 1; fi
git add logs/E2_*_s[23] logs/E5_*_s[23] logs/ES_*_s[23] scripts/run_helpers/hasan_seeds.sh scripts/run_helpers/package_seeds.sh scripts/run_helpers/push_seeds.sh
git commit -q -m "Seeds 2 and 3: logs of the E2, E5 and ES runs (commit e9ff1c8, --frozen)

E2 b0, b1, b2, single; E5 s3-G2, s3-G6, s3-memory, minus_all; ES retry caps 0/1/2/4; seeds 2 and 3.
Each logs/<run_id>/ holds config.json, report.json, state.jsonl and the compressed trajectories,
in the same layout as the seed-1 logs. Run with scripts/run_helpers/hasan_seeds.sh (one API key and one
repository copy per run); packaged with package_seeds.sh." && echo "   committed: $(git log --oneline -1)"
echo "== 4/4 pushing (GitHub username, then your personal access token as the password)"
git push -u origin "$BR" && echo "PUSHED: https://github.com/msaqibatifj/testdebt/tree/$BR"
