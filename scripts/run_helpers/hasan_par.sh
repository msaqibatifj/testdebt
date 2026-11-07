#!/usr/bin/env bash
# Parallel version of hasan_run.sh: one lane per API key, each lane in its own copy of the repo.
#   Lane A = ~/AgenticProj (key already in its .env), lane B = ~/AgenticProj_e1 (E1 is finished), lane C = ~/AgenticProj_c
# Rules kept: one LLM run at a time per key, one run at a time per folder, --frozen, no tracked file changed, keys never printed.
# Start (any Ubuntu tab):  bash hasan_par.sh   (it stops hasan_run.sh itself, then asks for the extra keys)
set -uo pipefail
export TZ=Asia/Karachi
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$SRC/_hasan_runs"; ST="$OUT/state"; CL="$HOME/.hasan_claims"; mkdir -p "$ST" "$CL"
MAIN="$HOME/AgenticProj"; LB="$HOME/AgenticProj_e1"; LC="$HOME/AgenticProj_c"; E1D="$LB"
COMMIT=3b992f2; J21=/usr/lib/jvm/java-21-openjdk-amd64
DEADLINE_TS=$(date -d "2026-11-08 13:00" +%s); PARTIAL_TS=$(date -d "2026-11-07 22:00" +%s)
X="python3 -m testdebt.team.gulsher.experiments"
ORDER=(1 2 3 4 5 6 7 8 9 10 11a 11b 11c 11d 12)
declare -A ARGS=([1]="E3 --only s3 --seeds 1" [2]="E5 --only s3-G1 --seeds 1" [3]="E2 --only b1" [4]="E2 --only b0"
  [5]="E2 --only b2" [6]="E3 --only s3 --seeds 2" [7]="E5 --only s3-G1 --seeds 2" [8]="E3 --only s3 --seeds 3"
  [9]="E5 --only s3-G1 --seeds 3" [10]="E2 --only single" [11a]="E5 --only s3-G2" [11b]="E5 --only s3-G6"
  [11c]="E5 --only s3-memory" [11d]="E5 --only minus_all" [12]="ES")
declare -A NEXT=([1]=2 [3]=4 [6]=7 [8]=9)          # same lane = shared LLM/PIT cache
log() { echo "[$(date '+%a %d %b %H:%M:%S')] $*" | tee -a "$OUT/progress.log"; }
left() { echo $(( DEADLINE_TS - $(date +%s) )); }
PITT=8

# ---------- one command, same stop handling as hasan_run.sh ----------
fix_projects() { local d; for d in "$1"/data/projects/*/; do
  [ -n "$(git -C "$d" status --porcelain --untracked-files=no)" ] && { log "[$2] restoring project checkout $d"; git -C "$d" checkout -- .; }; done; }
wait_budget() { local now=$(date +%s) until
  if [ "$2" = cap ]; then until=$(date -d "tomorrow 00:05" +%s); else until=$((now + 1800)); fi
  [ $until -gt $DEADLINE_TS ] && until=$DEADLINE_TS
  log "[$1] waiting until $(date -d @$until '+%a %H:%M') ($2)"; sleep $(( until - now > 0 ? until - now : 0 )); }
run_cmd() { local L=$1 dir=$2 n=$3; shift 3; local lf="$OUT/cmd$n.log" fails=0 rc t
  [ "$(cat "$ST/$n" 2>/dev/null)" = finished ] && return 0
  echo "$dir" > "$ST/$n.dir"
  while :; do
    [ "$(left)" -le 60 ] && { echo partial > "$ST/$n"; log "[$L] #$n stopped at the deadline"; return 2; }
    echo running > "$ST/$n"; log "[$L] #$n start: experiments run $* --frozen"
    ( unset CEREBRAS_API_KEY; cd "$dir" && source .venv/bin/activate && export PATH=$J21/bin:$HOME/apache-maven-3.9.9/bin:$PATH PIT_THREADS=$PITT PYTHONUNBUFFERED=1 &&
      timeout --signal=INT --kill-after=120 "$(left)" $X run "$@" --frozen ) >> "$lf" 2>&1; rc=$?
    [ $rc -eq 0 ] && { echo finished > "$ST/$n"; log "[$L] #$n finished"; return 0; }
    echo partial > "$ST/$n"
    if [ $rc -eq 124 ] || [ "$(left)" -le 60 ]; then log "[$L] #$n stopped at the deadline"; return 2; fi
    t=$(tail -40 "$lf")
    if   grep -q "daily token cap reached" <<<"$t"; then wait_budget "$L" cap
    elif grep -q "provider still rate-limiting" <<<"$t"; then wait_budget "$L" provider
    elif grep -q "needs clean project checkouts" <<<"$t"; then fix_projects "$dir" "$L"
    elif grep -q "needs a clean tree" <<<"$t"; then echo failed > "$ST/$n"; log "[$L] #$n STOPPED: --frozen needs a clean tree (tracked file changed). Report to Hasan."; return 1
    else fails=$((fails+1)); log "[$L] #$n failed (attempt $fails): $(tail -1 "$lf")"
         [ $fails -ge 2 ] && { echo failed > "$ST/$n"; log "[$L] #$n failed twice; moving on"; return 1; }; fi
  done; }

# ---------- lanes ----------
claim() { [ "$(cat "$ST/$2" 2>/dev/null)" = finished ] && return 1; mkdir "$CL/$2" 2>/dev/null && echo "$1" > "$CL/$2/lane"; }
next_free() { local n nx; for n in "${ORDER[@]}"; do claim "$1" "$n" && { nx=${NEXT[$n]:-}; if [ -n "$nx" ] && claim "$1" "$nx"; then echo "$n $nx"; else echo "$n"; fi; return; }; done; }
lane() { local L=$1 dir=$2; shift 2; local queue=("$@") n nx rc
  while :; do
    if [ ${#queue[@]} -gt 0 ]; then n=${queue[0]}; queue=("${queue[@]:1}"); else read -r n nx <<<"$(next_free "$L")"; [ -n "${nx:-}" ] && queue=("$nx"); fi
    [ -z "$n" ] && { log "[$L] nothing left to run"; return; }
    run_cmd "$L" "$dir" "$n" ${ARGS[$n]}; rc=$?
    [ $rc -eq 2 ] && return
  done; }

# ---------- lane setup ----------
mkvenv() { python3 -m venv .venv && source .venv/bin/activate && pip install -q --upgrade pip &&
  { pip install -q -r requirements.txt || pip install -q requests==2.34.2 pytest==9.1.1 matplotlib; } && pip install -q -e . && deactivate; }
keyhash() { grep '^CEREBRAS_API_KEY=' "$1" 2>/dev/null | tr -d '\r' | sed 's/[[:space:]]*$//' | sha256sum | cut -c1-16; }
setkey() {  # setkey <dir> <label>: asks for the key without echo, writes it to <dir>/.env, never prints it
  local K; read -rsp "Paste the Cerebras API key for lane $2 (Enter = skip this lane): " K; echo
  [ -z "$K" ] && return 1
  [ "$(printf 'CEREBRAS_API_KEY=%s\n' "$K" | sha256sum | cut -c1-16)" = "$(keyhash "$MAIN/.env")" ] && { echo "That is lane A's key; skipped."; return 1; }
  for o in "$LB" "$LC"; do [ "$o" != "$1" ] && [ -f "$o/.env.lane" ] && [ "$(printf 'CEREBRAS_API_KEY=%s\n' "$K" | sha256sum | cut -c1-16)" = "$(keyhash "$o/.env")" ] && { echo "Same key as another lane; skipped."; return 1; }; done
  { grep -v '^CEREBRAS_API_KEY=' "$MAIN/.env"; printf 'CEREBRAS_API_KEY=%s\n' "$K"; } > "$1/.env"; chmod 600 "$1/.env"; touch "$1/.env.lane"; unset K
  if ! ( unset CEREBRAS_API_KEY; cd "$1" && source .venv/bin/activate && python3 scripts/smoke_test.py ) > "$OUT/setup_smoke_lane$2.log" 2>&1; then
    sed -i '/^text  :/d' "$OUT/setup_smoke_lane$2.log"; echo "Smoke test failed for lane $2 (see _hasan_runs/setup_smoke_lane$2.log); lane skipped."; return 1; fi
  sed -i '/^text  :/d' "$OUT/setup_smoke_lane$2.log"; log "lane $2: key works (smoke test OK)"; }
share_caches() {  # copy LLM and PIT caches into a lane (cache files are keyed by content, so copies are safe)
  mkdir -p "$1/runs/cache" "$1/runs/pit_cache"
  for s in "$MAIN" "$LB"; do [ "$s" = "$1" ] && continue
    [ -d "$s/runs/cache" ] && cp -rn "$s/runs/cache/." "$1/runs/cache/" 2>/dev/null
    [ -d "$s/runs/pit_cache" ] && cp -rn "$s/runs/pit_cache/." "$1/runs/pit_cache/" 2>/dev/null; done; }
make_lane_c() {
  [ -d "$LC/.git" ] && return 0
  log "lane C: creating $LC (copy of $MAIN without runs/ and .venv)"
  mkdir -p "$LC" && ( cd "$MAIN" && tar cf - --exclude=./.venv --exclude=./runs . ) | ( cd "$LC" && tar xf - ) || return 1
  cd "$LC" && mkdir -p runs && git checkout -- runs/.gitkeep 2>/dev/null; git config core.fileMode false
  fix_projects "$LC" C
  [ -z "$(git status --porcelain --untracked-files=no)" ] || { log "lane C copy not clean"; return 1; }
  mkvenv > "$OUT/setup_venv_laneC.log" 2>&1 || { log "lane C venv failed (see setup_venv_laneC.log)"; return 1; }; cd "$SRC"; }

# ---------- package + status ----------
progress() { python3 - "$1/runs/$2/state.jsonl" <<'PY' 2>/dev/null || echo 0
import json, sys
seen = set()
for l in open(sys.argv[1]):
    r = json.loads(l); t = r["test"]
    if r.get("decision") != "error": seen.add((t["project"], t["class_name"], t.get("method")))
print(len(seen))
PY
}
rids() { local exp only seeds; set -- $1; exp=$1; shift; only=""; seeds=""
  while [ $# -gt 0 ]; do case $1 in --only) only=$2; shift;; --seeds) seeds=$2; shift;; esac; shift; done
  case "$exp/$only" in ES/) echo ES_s3-retries0_s1 ES_s3-retries1_s1 ES_s3-retries2_s1 ES_s3-retries4_s1;; *) echo "${exp}_${only}_s${seeds:-1}";; esac; }
status_note() { local fin="" par="" nr="" fl="" n st r d lanes=""
  for n in "${ORDER[@]}"; do st=$(cat "$ST/$n" 2>/dev/null || echo notrun); d=$(cat "$ST/$n.dir" 2>/dev/null || echo "$MAIN")
    [ -f "$ST/$n.dir" ] && lanes+="#$n:$(basename "$d") "
    case $st in finished) fin+="#$n, ";;
      partial|running) for r in $(rids "${ARGS[$n]}"); do par+="#$n $r ($(progress "$d" $r)/$( [ $n = 12 ] && echo 20 || echo 150)), "; done;;
      failed) fl+="#$n, ";; *) nr+="#$n, ";; esac; done
  local e1st=$(cat "$ST/E1" 2>/dev/null || echo notrun) errs
  errs=$(cat "$OUT"/cmd*.log 2>/dev/null | grep -E "failed; fix|STOP:|Traceback" | sed 's/[0-9]\{2,\}/N/g' | sort | uniq -c | sort -rn | awk '$1>1' | head -5)
  cat <<NOTE
commit: $COMMIT
finished: ${fin%, }
partial:  ${par%, }
not run:  ${nr%, }
failed:   ${fl:-none}
E1: $( [ "$e1st" = finished ] && echo "finished (19/484 tests end in deterministic tool errors: Jsoup network tests under PIT, PIT compile, 1 JNose parse)" || echo "stopped at $(progress "$E1D" E1_b0replay_s1)/484")
errors seen: ${errs:-none}
lanes (one API key per folder, runs never shared a key or folder): ${lanes% }
NOTE
}
package() { log "packaging ($1)"; local P="$HOME/hasan_pkg" n r d
  rm -rf "$P"; mkdir -p "$P/runs"
  for n in "${ORDER[@]}"; do d=$(cat "$ST/$n.dir" 2>/dev/null) || continue
    for r in $(rids "${ARGS[$n]}"); do [ -d "$d/runs/$r" ] && ln -sfn "$d/runs/$r" "$P/runs/$r"; done; done
  [ -f "$MAIN/runs/llm_calls.jsonl" ] && cp "$MAIN/runs/llm_calls.jsonl" "$P/runs/llm_calls.jsonl"
  for x in B:$LB C:$LC; do [ -f "${x#*:}/runs/llm_calls.jsonl" ] && [ -f "${x#*:}/.env.lane" ] && cp "${x#*:}/runs/llm_calls.jsonl" "$P/runs/llm_calls_lane${x%%:*}.jsonl"; done
  ( cd "$P" && tar czhf "$HOME/hasan_runs.tgz" runs )
  ( cd "$E1D" && tar czf "$HOME/hasan_e1.tgz" runs/E1_* 2>/dev/null )
  cp -f "$HOME/hasan_runs.tgz" "$HOME/hasan_e1.tgz" "$OUT/" 2>/dev/null
  status_note > "$OUT/STATUS.txt"; cp -f "$OUT/STATUS.txt" "$OUT/STATUS_$1.txt"
  ls -lh "$OUT"/*.tgz | tee -a "$OUT/progress.log"; cat "$OUT/STATUS.txt"; }

case "${1:-all}" in
  status)  status_note; exit;;
  package) package manual; exit;;
esac

# ---------- main ----------
if pgrep -f "hasan_run.sh" >/dev/null || pgrep -f "testdebt.cli" >/dev/null; then
  echo "Stopping the old single-key runner (the test in progress is redone on resume)..."
  pkill -f "hasan_run.sh"; pkill -INT -f "testdebt.team.gulsher.experiments"; pkill -INT -f "testdebt.cli"
  for i in $(seq 60); do pgrep -f "testdebt.cli" >/dev/null || break; sleep 1; done
  pkill -9 -f "testdebt.cli" 2>/dev/null; pkill -9 -f "pitest|org.codehaus.plexus.classworlds" 2>/dev/null; sleep 2
  log "old runner stopped; switching to hasan_par.sh"
fi
cd "$MAIN" && git log --oneline -1 | grep -q "^$COMMIT" || { echo "lane A is not at $COMMIT"; exit 1; }
fix_projects "$MAIN" A
rm -rf "$CL"; mkdir -p "$CL"
LANES=(A)
echo "Lane A = your current key (in ~/AgenticProj). Up to two more keys, each from a DIFFERENT Cerebras account."
if setkey "$LB" B; then share_caches "$LB"; fix_projects "$LB" B; LANES+=(B); fi
if make_lane_c && setkey "$LC" C; then share_caches "$LC"; LANES+=(C); fi
PITT=$(( $(nproc) / ${#LANES[@]} )); [ $PITT -gt 8 ] && PITT=8; [ $PITT -lt 2 ] && PITT=2
log "parallel start: lanes ${LANES[*]}, PIT_THREADS=$PITT each, $(free -g | awk '/Mem:/{print $2" GB RAM, "$7" GB free"}')"
# initial queues (cache affinity): A keeps #1 then #2; B takes #3 then #4; C takes #5; afterwards each lane takes the next free command
for n in 1 2; do claim A $n; done
case ${#LANES[@]} in
  1) lane A "$MAIN" 1 2 & ;;
  2) claim B 3; claim B 4; lane A "$MAIN" 1 2 & lane B "$LB" 3 4 & ;;
  3) claim B 3; claim B 4; claim C 5; lane A "$MAIN" 1 2 & lane B "$LB" 3 4 & lane C "$LC" 5 & ;;
esac
( s=$(( PARTIAL_TS - $(date +%s) )); [ $s -gt 0 ] && { sleep $s; package saturday_partial; } ) & PT=$!
while [ -n "$(jobs -rp | grep -v "^$PT$")" ] && [ "$(left)" -gt 0 ]; do sleep 60; done
kill $PT 2>/dev/null
if [ "$(left)" -le 60 ]; then pkill -INT -f "testdebt.cli --run-id"; sleep 30; pkill -f "testdebt.cli --run-id"; fi
package final
log "DONE. Send _hasan_runs/hasan_runs.tgz, hasan_e1.tgz and STATUS.txt to Saqib."
