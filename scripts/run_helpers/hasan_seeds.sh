#!/usr/bin/env bash
# Parallel version of hasan_run.sh: one lane per API key, each lane in its own copy of the repo.
#   Lane A = ~/AgenticProj (key already in its .env), lane B = ~/AgenticProj_e1 (E1 is finished), lane C = ~/AgenticProj_c
# Rules kept: one LLM run at a time per key, one run at a time per folder, --frozen, no tracked file changed, keys never printed.
# Start (any Ubuntu tab):  bash hasan_all.sh   (no prompts: keeps every lane key, puts the spare key to work on a new lane, recycles keys of finished lanes)   (stops hasan_run.sh / hasan_par.sh itself, reuses lane keys already set)
# No Sunday-1-PM stop: runs until everything is done or DEADLINE (default Sun 8 Nov 23:00 PKT); packages every 2 h.
set -uo pipefail
export TZ=Asia/Karachi
SRC=/mnt/c/Users/ha797/Downloads/AgenticProj_backup_2026-11-06_v4/AgenticProj
OUT="$SRC/_hasan_runs/seeds"; ST="$OUT/state"; CL="$HOME/.hasan_seed_claims"; mkdir -p "$ST" "$CL"
MAIN="$HOME/AgenticProj"; LB="$HOME/AgenticProj_e1"; LC="$HOME/AgenticProj_c"; LD="$HOME/AgenticProj_d"; LE="$HOME/AgenticProj_e"; E1D="$LB"
COMMIT=e9ff1c8; J21=/usr/lib/jvm/java-21-openjdk-amd64
DEADLINE_TS=$(date -d "${DEADLINE:-2026-12-31 00:00}" +%s)   # no deadline: runs until every command is done; one package at the end
X="python3 -m testdebt.team.gulsher.experiments"
ORDER=(b1-2 mall-2 b0-2 G6-2 G2-2 mem-2 b2-2 ES-2 single-2 b1-3 mall-3 b0-3 G6-3 G2-3 mem-3 b2-3 ES-3 single-3)
declare -A ARGS=()
for s in 2 3; do ARGS[b1-$s]="E2 --only b1 --seeds $s"; ARGS[b0-$s]="E2 --only b0 --seeds $s"; ARGS[b2-$s]="E2 --only b2 --seeds $s"
  ARGS[single-$s]="E2 --only single --seeds $s"; ARGS[mall-$s]="E5 --only minus_all --seeds $s"; ARGS[G6-$s]="E5 --only s3-G6 --seeds $s"
  ARGS[G2-$s]="E5 --only s3-G2 --seeds $s"; ARGS[mem-$s]="E5 --only s3-memory --seeds $s"; ARGS[ES-$s]="ES --seeds $s"; done
declare -A NEXT=()
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
    if   grep -q "daily token cap reached" <<<"$t"; then wait_or_swap "$dir" "$L" cap
    elif grep -q "provider still rate-limiting" <<<"$t"; then wait_or_swap "$dir" "$L" provider
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
    [ -z "$n" ] && { recycle_key "$dir" "$L"; return; }
    run_cmd "$L" "$dir" "$n" ${ARGS[$n]}; rc=$?
    [ $rc -eq 2 ] && return
    [ $rc -eq 1 ] && { log "[$L] lane stopped after #$n failed (see cmd$n.log, last 40 lines)"; recycle_key "$dir" "$L"; return; }
  done; }

# ---------- lane setup ----------
mkvenv() { python3 -m venv .venv && source .venv/bin/activate && pip install -q --upgrade pip &&
  { pip install -q -r requirements.txt || pip install -q requests==2.34.2 pytest==9.1.1 matplotlib; } && pip install -q -e . && deactivate; }
keyhash() { grep '^CEREBRAS_API_KEY=' "$1" 2>/dev/null | tr -d '\r' | sed 's/[[:space:]]*$//' | sha256sum | cut -c1-16; }
setkey() {  # setkey <dir> <label>: reuse the lane key if already set, else ask without echo; never prints it
  if [ -f "$1/.env.lane" ] && ( unset CEREBRAS_API_KEY; cd "$1" && source .venv/bin/activate && python3 scripts/smoke_test.py ) > "$OUT/setup_smoke_lane$2.log" 2>&1; then
    sed -i '/^text  :/d' "$OUT/setup_smoke_lane$2.log"; log "lane $2: existing key works (smoke test OK)"; return 0; fi
  local K; read -rsp "Paste the Cerebras API key for lane $2 (Enter = skip this lane): " K; echo
  [ -z "$K" ] && return 1
  [ "$(printf 'CEREBRAS_API_KEY=%s\n' "$K" | sha256sum | cut -c1-16)" = "$(keyhash "$MAIN/.env")" ] && { echo "That is lane A's key; skipped."; return 1; }
  for o in "$LB" "$LC" "$LD" "$LE"; do [ "$o" != "$1" ] && [ -f "$o/.env.lane" ] && [ "$(printf 'CEREBRAS_API_KEY=%s\n' "$K" | sha256sum | cut -c1-16)" = "$(keyhash "$o/.env")" ] && { echo "Same key as another lane; skipped."; return 1; }; done
  { grep -v '^CEREBRAS_API_KEY=' "$MAIN/.env"; printf 'CEREBRAS_API_KEY=%s\n' "$K"; } > "$1/.env"; chmod 600 "$1/.env"; touch "$1/.env.lane"; unset K
  if ! ( unset CEREBRAS_API_KEY; cd "$1" && source .venv/bin/activate && python3 scripts/smoke_test.py ) > "$OUT/setup_smoke_lane$2.log" 2>&1; then
    sed -i '/^text  :/d' "$OUT/setup_smoke_lane$2.log"; echo "Smoke test failed for lane $2 (see _hasan_runs/setup_smoke_lane$2.log); lane skipped."; return 1; fi
  sed -i '/^text  :/d' "$OUT/setup_smoke_lane$2.log"; log "lane $2: key works (smoke test OK)"; }
share_caches() {  # copy LLM and PIT caches into a lane (cache files are keyed by content, so copies are safe)
  mkdir -p "$1/runs/cache" "$1/runs/pit_cache"
  for s in "$MAIN" "$LB" "$LC" "$LD" "$LE"; do [ "$s" = "$1" ] && continue; [ -d "$s/runs" ] || continue
    [ -d "$s/runs/cache" ] && cp -rn "$s/runs/cache/." "$1/runs/cache/" 2>/dev/null
    [ -d "$s/runs/pit_cache" ] && cp -rn "$s/runs/pit_cache/." "$1/runs/pit_cache/" 2>/dev/null; done; }
make_lane() {  # make_lane <dir> <label>
  local D=$1 L=$2
  [ -d "$D/.git" ] && return 0
  log "lane $L: creating $D (copy of $MAIN without runs/ and .venv)"
  mkdir -p "$D" && ( cd "$MAIN" && tar cf - --exclude=./.venv --exclude=./runs --exclude=./.env.lane . ) | ( cd "$D" && tar xf - ) || return 1
  cd "$D" && mkdir -p runs && git checkout -- runs/.gitkeep 2>/dev/null; git config core.fileMode false
  fix_projects "$D" "$L"
  [ -z "$(git status --porcelain --untracked-files=no)" ] || { log "lane $L copy not clean"; cd "$SRC"; return 1; }
  mkvenv > "$OUT/setup_venv_lane$L.log" 2>&1 || { log "lane $L venv failed (see setup_venv_lane$L.log)"; cd "$SRC"; return 1; }; cd "$SRC"; }

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
  case "$exp/$only" in ES/) local k; for k in 0 1 2 4; do echo -n "ES_s3-retries${k}_s${seeds:-1} "; done; echo;; *) echo "${exp}_${only}_s${seeds:-1}";; esac; }
status_note() { local n st d r fin="" par="" nr="" fl=""
  for n in "${ORDER[@]}"; do st=$(cat "$ST/$n" 2>/dev/null || echo notrun); d=$(cat "$ST/$n.dir" 2>/dev/null || echo "")
    case $st in finished) fin+="$n, ";;
      partial|running) for r in $(rids "${ARGS[$n]}"); do par+="$n $r ($(progress "$d" $r)/$(case $n in ES-*) echo 20;; *) echo 150;; esac) in $(basename "$d")), "; done;;
      failed) fl+="$n ($(basename "$d")), ";; *) nr+="$n, ";; esac; done
  cat <<NOTE
commit: $COMMIT (seeds 2 and 3)
finished: ${fin%, }
partial:  ${par%, }
not run:  ${nr%, }
failed:   ${fl:-none}
NOTE
}
package() { log "packaging ($1)"; local L d b
  for L in A B C D E F G H I J K L; do d=${DIRS[$L]}; [ -d "$d/runs" ] || continue; b=$(basename "$d")
    ( cd "$d" && r=$(ls -d runs/E2_*_s[23] runs/E5_*_s[23] runs/ES_*_s[23] 2>/dev/null) && [ -n "$r" ] && tar czf "$HOME/seeds_$b.tgz" $r && cp -f "$HOME/seeds_$b.tgz" "$OUT/" ); done
  status_note > "$OUT/STATUS.txt"; cp -f "$OUT/STATUS.txt" "$OUT/STATUS_$1.txt"
  ls -lh "$OUT"/seeds_*.tgz 2>/dev/null | tee -a "$OUT/progress.log"; cat "$OUT/STATUS.txt"; }
declare -A DIRS=([A]="$HOME/AgenticProj" [B]="$HOME/AgenticProj_e1" [C]="$HOME/AgenticProj_c" [D]="$HOME/AgenticProj_d" [E]="$HOME/AgenticProj_e" [F]="$HOME/AgenticProj_f"
  [G]="$HOME/AgenticProj_g" [H]="$HOME/AgenticProj_h" [I]="$HOME/AgenticProj_i" [J]="$HOME/AgenticProj_j" [K]="$HOME/AgenticProj_k" [L]="$HOME/AgenticProj_l")
POOL="$HOME/.hasan_seed_keypool"; PLOCK="$POOL.lock"
case "${1:-all}" in
  addkeys)  # add keys to a running job: lanes whose key runs out pick them up within 5 minutes
    POOL="$HOME/.hasan_seed_keypool"; PLOCK="$POOL.lock"; umask 077; touch "$POOL"; n=0
    echo "Paste extra keys (hidden), empty line = done."
    while read -rsp "keys: " LINE; do echo; [ -z "$LINE" ] && break
      for K in $(echo "$LINE" | tr ',;' '  '); do until mkdir "$PLOCK" 2>/dev/null; do sleep 0.2; done
        printf '%s\n' "$K" >> "$POOL"; rmdir "$PLOCK"; n=$((n+1)); done; unset LINE K; done
    echo "$n key(s) added; pool now has $(grep -c . "$POOL") key(s)."; exit;;
  status)  status_note; exit;;
  package) package manual; exit;;
esac


# ---------- key pool: spare keys (hidden, file mode 600 in WSL home, deleted at the end); a lane whose key runs out takes the next one ----------
POOL="$HOME/.hasan_keypool"; PLOCK="$HOME/.hasan_keypool.lock"
pool_size() { if [ -s "$POOL" ]; then grep -c . "$POOL"; else echo 0; fi; }
pool_pop() { local k=""; until mkdir "$PLOCK" 2>/dev/null; do sleep 0.2; done
  if [ -s "$POOL" ]; then k=$(head -1 "$POOL"); tail -n +2 "$POOL" > "$POOL.t"; mv -f "$POOL.t" "$POOL"; chmod 600 "$POOL"; fi
  rmdir "$PLOCK"; printf '%s' "$k"; }
put_key() {  # put_key <dir> <label> <key>: install key in a lane, fresh daily counter, smoke test; 0 = works
  local D=$1 L=$2 K=$3 stamp; stamp=$(date +%Y%m%d_%H%M%S)
  cp -p "$D/.env" "$D/.env.prev" 2>/dev/null || cp -p "$MAIN/.env" "$D/.env.prev"
  { grep -v '^CEREBRAS_API_KEY=' "$D/.env.prev"; printf 'CEREBRAS_API_KEY=%s\n' "$K"; } > "$D/.env.new"
  mv -f "$D/.env.new" "$D/.env"; chmod 600 "$D/.env"; touch "$D/.env.lane"
  [ -f "$D/runs/llm_calls.jsonl" ] && mv "$D/runs/llm_calls.jsonl" "$D/runs/llm_calls_key_until_$stamp.jsonl"
  if ( unset CEREBRAS_API_KEY; cd "$D" && source .venv/bin/activate && python3 scripts/smoke_test.py ) > "$OUT/setup_smoke_lane$L.log" 2>&1; then
    sed -i '/^text  :/d' "$OUT/setup_smoke_lane$L.log"; rm -f "$D/.env.prev"; return 0; fi
  sed -i '/^text  :/d' "$OUT/setup_smoke_lane$L.log"
  mv -f "$D/.env.prev" "$D/.env"; [ -f "$D/runs/llm_calls.jsonl" ] && cat "$D/runs/llm_calls.jsonl" >> "$D/runs/llm_calls_key_until_$stamp.jsonl"
  mv -f "$D/runs/llm_calls_key_until_$stamp.jsonl" "$D/runs/llm_calls.jsonl"; return 1; }
pool_swap() {  # pool_swap <dir> <label>: replace a used-up key with the next working spare
  local D=$1 L=$2 K
  while [ "$(pool_size)" -gt 0 ]; do K=$(pool_pop); [ -z "$K" ] && break
    if put_key "$D" "$L" "$K"; then unset K; log "[$L] key used up -> switched to a spare key ($(pool_size) spare left)"; return 0; fi
    unset K; log "[$L] a spare key failed its test (limited or wrong); dropped"; done
  return 1; }
used_today() { TZ=Asia/Karachi python3 - "$1/runs/llm_calls.jsonl" <<'PYX' 2>/dev/null || echo 0
import json, sys, time
t0 = time.mktime(time.strptime(time.strftime("%Y-%m-%d"), "%Y-%m-%d")); u = 0
for l in open(sys.argv[1], encoding="utf-8"):
    try: r = json.loads(l)
    except Exception: continue
    if r.get("ts", 0) >= t0 and not r.get("cached"): u += (r.get("usage") or {}).get("total_tokens", 0)
print(u)
PYX
}

wait_or_swap() {  # a used-up lane takes a spare/recycled key at once; otherwise checks the pool every 5 min until its own key resets
  local D=$1 L=$2 kind=$3 until
  pool_swap "$D" "$L" && return 0
  if [ "$kind" = cap ]; then until=$(date -d "tomorrow 00:05" +%s); else until=$(( $(date +%s) + 1800 )); fi
  log "[$L] key used up and no spare right now; checking every 5 min for a recycled key, otherwise retrying at $(date -d @$until '+%a %H:%M')"
  while [ "$(date +%s)" -lt "$until" ]; do sleep 300; pool_swap "$D" "$L" && return 0; done; }
recycle_key() {  # a lane with nothing left gives its key (and whatever limit it still has) to lanes that run out
  local D=$1 L=$2 k; k=$(grep '^CEREBRAS_API_KEY=' "$D/.env" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '\r')
  [ -z "$k" ] && { log "[$L] nothing left to run"; return; }
  until mkdir "$PLOCK" 2>/dev/null; do sleep 0.2; done; printf '%s\n' "$k" >> "$POOL"; chmod 600 "$POOL"; rmdir "$PLOCK"; unset k
  log "[$L] nothing left to run; its key moved to the pool for lanes that run out ($(pool_size) in pool)"; }
# ---------- main ----------
POOL="$HOME/.hasan_seed_keypool"; PLOCK="$POOL.lock"
OLD=$(pgrep -f "hasan_(run|par|fast|go|keys|swap|more|all|seeds)\.sh" | grep -vx "$$" | tr "\n" " ")
if [ -n "$OLD" ] || pgrep -f "testdebt.cli" >/dev/null; then
  echo "Stopping old runners..."; [ -n "$OLD" ] && kill $OLD 2>/dev/null; pkill -INT -f "testdebt.cli"
  for i in $(seq 60); do pgrep -f "testdebt.cli" >/dev/null || break; sleep 1; done; pkill -9 -f "testdebt.cli" 2>/dev/null; sleep 2; fi
log "=== seeds 2 and 3 (commit $COMMIT), 12 lanes ==="
# Step 1: update the existing folders to origin/main and check them
update() { local L=$1 d=${DIRS[$1]}
  ( cd "$d" && git fetch -q origin && git checkout -q main && git merge -q --ff-only origin/main ) > "$OUT/update_$L.log" 2>&1 || { log "lane $L: git update failed (see update_$L.log)"; return 1; }
  cd "$d"; git log --oneline -1 | grep -q "^$COMMIT" || { log "lane $L: HEAD is $(git log --oneline -1 | cut -c1-40), not $COMMIT"; cd "$SRC"; return 1; }
  [ -z "$(git status --porcelain --untracked-files=no)" ] || { log "lane $L: tracked files modified: $(git status --short --untracked-files=no | head -3 | tr '\n' ' ')"; cd "$SRC"; return 1; }
  [ -z "$(git ls-files --others --exclude-standard -- src configs experiments data/splits)" ] || { log "lane $L: untracked files under src/configs/experiments/data/splits"; cd "$SRC"; return 1; }
  fix_projects "$d" "$L"; pip_ok=1; cd "$SRC"; }
READY=()
for L in A B C D E F G H; do [ -d "${DIRS[$L]}/.git" ] || continue; update $L && READY+=($L) && log "lane $L: at $COMMIT, clean"; done
case " ${READY[*]} " in *" A "*) ;; *) echo "~/AgenticProj could not be updated; see $OUT/update_A.log"; exit 1;; esac
( cd "${DIRS[A]}" && source .venv/bin/activate && pip install -q -e . >/dev/null 2>&1; python3 -m pytest -q ) > "$OUT/pytest.log" 2>&1
log "pytest (~/AgenticProj): $(tail -1 "$OUT/pytest.log")"
grep -q "103 passed, 2 skipped" "$OUT/pytest.log" || { echo "pytest did not give '103 passed, 2 skipped' (see $OUT/pytest.log); stopping."; exit 1; }
for L in "${READY[@]}"; do [ $L = A ] && continue; ( cd "${DIRS[$L]}" && source .venv/bin/activate && pip install -q -e . ) >/dev/null 2>&1; done
# new lanes I-L as copies of ~/AgenticProj (now at the new commit)
for L in I J K L; do
  if [ ! -d "${DIRS[$L]}/.git" ]; then
    free=$(df -Pm "$HOME" | awk 'NR==2{print $4}'); [ "${free:-0}" -lt 4000 ] && { log "not creating lane $L: only ${free} MB disk free"; continue; }
    make_lane "${DIRS[$L]}" $L || continue
  fi
  update $L && READY+=($L) && log "lane $L: at $COMMIT, clean"; done
# keys: pasted hidden, one or several per line; Enter on an empty line ends
umask 077; : > "$POOL"; SEEN=" "; n=0
echo "Paste ALL your keys (hidden): one per line, or all of them on one line separated by spaces."
echo "There are ${#READY[@]} lanes. Press Enter on an EMPTY line only after the last key."
while read -rsp "keys: " LINE; do echo; [ -z "$LINE" ] && break
  for K in $(echo "$LINE" | tr ',;' '  '); do h=$(printf '%s' "$K" | sha256sum | cut -c1-16)
    case "$SEEN" in *" $h "*) continue;; esac; SEEN+="$h "; printf '%s\n' "$K" >> "$POOL"; n=$((n+1)); done
  unset LINE K; echo "  $n key(s) so far (lanes: ${#READY[@]}); paste the next key, or press Enter on an empty line if that was the last"; done
umask 022; log "keys given: $(pool_size)"
# one key per lane; a key that fails its smoke test is dropped and the next one is tried
LANES=()
for L in "${READY[@]}"; do pool_swap "${DIRS[$L]}" $L && LANES+=($L) || log "lane $L: no working key left; not started"; done
log "lanes with a key: ${LANES[*]} ($(pool_size) spare)"
# initial queues: b1 -> minus_all -> b0 share LLM calls within a seed, so they stay in one folder
declare -A Q=([A]="b1-2 mall-2 b0-2" [B]="b1-3 mall-3 b0-3" [C]="G2-2" [D]="mem-2" [E]="G2-3" [F]="mem-3" [G]="b2-2" [H]="b2-3"
  [I]="G6-2" [J]="G6-3" [K]="ES-2 single-2" [L]="ES-3 single-3")
rm -rf "$CL"; mkdir -p "$CL"
for L in "${LANES[@]}"; do for u in ${Q[$L]}; do claim $L $u; done; done
PITT=$(( $(nproc) / ${#LANES[@]} )); [ $PITT -lt 2 ] && PITT=2; [ $PITT -gt 8 ] && PITT=8
log "start: ${#LANES[@]} lanes, PIT_THREADS=$PITT, $(free -g | awk '/Mem:/{print $7" GB RAM free"}')"
for L in "${LANES[@]}"; do log "lane $L ($(basename ${DIRS[$L]})): ${Q[$L]}"; lane $L "${DIRS[$L]}" ${Q[$L]} & done
( while sleep 7200; do package "snapshot_$(date +%a_%H%M)" >/dev/null; done ) & PT=$!
while [ -n "$(jobs -rp | grep -v "^$PT$")" ]; do sleep 60; done
kill $PT 2>/dev/null
shred -u "$POOL" 2>/dev/null || rm -f "$POOL"
package final
log "DONE. Send the seeds_*.tgz files and STATUS.txt from _hasan_runs/seeds to Saqib."
