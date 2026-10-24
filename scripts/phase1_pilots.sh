#!/usr/bin/env bash
# Phase 1 pilot runs (WSL, after setup_projects.sh and with CEREBRAS_API_KEY in .env).
# Each run's report.md / report.json / decisions.json / config.json is copied to results/phase1/<run_id>/
# so the numbers quoted in docs/results_phase1.md are backed by committed artifacts.
#
#   bash scripts/phase1_pilots.sh            # all pilots (~45 min, ~150k tokens)
#   bash scripts/phase1_pilots.sh pit        # only the PIT pilot (no LLM)
#   bash scripts/phase1_pilots.sh llm        # only the LLM pilots
set -euo pipefail
cd "$(dirname "$0")/.."
WHAT=${1:-all}
N=10                                         # same first 10 Commons-cli tests for every LLM system

save() { mkdir -p "results/phase1/$1"; cp runs/"$1"/{report.md,report.json,decisions.json,config.json} "results/phase1/$1/"; }
run()  { local id=$1; shift; python3 -m testdebt.eval.run_baseline --run-id "$id" "$@"; save "$id"; }

if [[ $WHAT == all || $WHAT == pit ]]; then
  # G1 tool check: PIT kill-sets on UTRefactor's own outputs. If killset_checked stays 0 or every kill-set is
  # empty, fullMutationMatrix is not filling killingTests: fix tools/pit.py before relying on G1.
  run pit_pilot_b0replay_cli --system b0replay --eval data/eval_set.jsonl --project commons-cli --limit 5 --pit
  python3 - <<'PY'
import json; o = json.load(open("runs/pit_pilot_b0replay_cli/report.json"))["overall"]
print(f"PIT pilot: kill-set checked on {o['killset_checked']} accepted tests, {o['accepted_losing_mutants']} lost mutants")
assert o["killset_checked"] > 0, "PIT produced no kill-sets - check tools/pit.py (plugin version / fullMutationMatrix)"
PY
fi

if [[ $WHAT == all || $WHAT == llm ]]; then
  run b0replay_cli_full --system b0replay --eval data/eval_set.jsonl --project commons-cli
  for sys in single b0 b1 s3; do
    run "${sys}_cli_pilot${N}" --system "$sys" --eval data/eval_set.jsonl --project commons-cli --limit $N --seed 1
  done
  python3 - <<'PY'
import json, pathlib
rows = []
for d in sorted(pathlib.Path("results/phase1").glob("*_cli_pilot10")):
    o = json.load(open(d / "report.json"))["overall"]
    rows.append(f"| {d.name.split('_')[0]} | {o['tests']} | {o['accepted_rate']} | {o['compile_rate']} | {o['pass_rate']} | "
                f"{o['smell_reduction_tsdetect']} | {o['retried']} | {o['tokens_per_test']} |")
print("| System | Tests | Accepted % | Compile % | Pass % | Reduction % | Retried | Tokens/test |")
print("|---|---|---|---|---|---|---|---|")
print("\n".join(rows))
PY
fi
