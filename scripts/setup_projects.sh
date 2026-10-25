#!/usr/bin/env bash
# Clone the UTRefactor replication package and the 3 primary projects, check out the commits that match
# UTRefactor's inputs (data/pins.json), then build the evaluation sets.
#   bash scripts/setup_projects.sh            # use the shipped pins
#   bash scripts/setup_projects.sh --repin    # recompute pins from git history (≈15 s)
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data/projects runs
[ -d data/utrefactor/.git ] || git clone https://github.com/testmigrator/testsmellrefactoring.git data/utrefactor

for name in commons-cli gson jsoup; do
  url=$(python3 -c "import json;print(json.load(open('data/pins.json'))['$name']['url'])")
  dir=data/projects/$name
  if [ ! -d "$dir/.git" ]; then
    if [ -d "data/$name/.git" ]; then mv "data/$name" "$dir"; else git clone "$url" "$dir"; fi   # reuse old clones
  fi
  [ "$(git -C "$dir" rev-parse --is-shallow-repository)" = "true" ] && git -C "$dir" fetch -q --unshallow
  git -C "$dir" checkout -q -- . 2>/dev/null || true
done

if [ "${1:-}" = "--repin" ]; then
  python3 -m testdebt.data.utr_dataset pin --project cli   --repo data/projects/commons-cli
  python3 -m testdebt.data.utr_dataset pin --project gson  --repo data/projects/gson
  python3 -m testdebt.data.utr_dataset pin --project jsoup --repo data/projects/jsoup
fi

for name in commons-cli gson jsoup; do
  c=$(python3 -c "import json;print(json.load(open('data/pins.json'))['$name']['commit'])")
  git -C data/projects/$name checkout -q "$c" && echo "$name -> $c"
done

python3 -m testdebt.data.build_eval_set
python3 -m testdebt.data.build_eval_set --subset 150 --seed 1 --out data/eval_subset150.jsonl
