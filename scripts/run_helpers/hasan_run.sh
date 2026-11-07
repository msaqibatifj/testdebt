#!/usr/bin/env bash
# VeriRefactor Phase 2: test-split experiment runs for Hasan (runs only; changes no tracked file).
#   bash hasan_run.sh            setup (once, asks for sudo) + all runs in order + E1 in parallel + packages
#   bash hasan_run.sh status     print the status note now
#   bash hasan_run.sh package    make the two .tgz files + status note now
# Outputs (visible in Windows): ./_hasan_runs/  progress.log, cmd*.log, E1.log, STATUS.txt, hasan_runs.tgz, hasan_e1.tgz
set -uo pipefail
export TZ=Asia/Karachi
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$SRC/_hasan_runs"; ST="$OUT/state"; mkdir -p "$ST"
MAIN="$HOME/AgenticProj"; E1D="$HOME/AgenticProj_e1"
COMMIT=3b992f2
DEADLINE_TS=$(date -d "2026-11-08 13:00" +%s)
PARTIAL_TS=$(date -d "2026-11-07 22:00" +%s)
J21=/usr/lib/jvm/java-21-openjdk-amd64

log()  { echo "[$(date '+%a %d %b %H:%M:%S')] $*" | tee -a "$OUT/progress.log"; }
die()  { log "STOPPED: $*"; exit 1; }
envset() {  # step 2 of the prompt
  cd "$1" && source .venv/bin/activate
  export PATH=$J21/bin:$HOME/apache-maven-3.9.9/bin:$PATH PIT_THREADS=8
}
step() {  # step <name> <cmd...>: run, keep full log, on failure show last 30 lines and stop
  local name=$1; shift; log "setup: $name"
  if ! "$@" > "$OUT/setup_$name.log" 2>&1; then
    echo "---- last 30 lines of setup_$name.log ----"; tail -30 "$OUT/setup_$name.log"
    die "setup step '$name' failed (full log: _hasan_runs/setup_$name.log). Send these lines to Claude/Hasan."
  fi
}

# ---------------- step 1: setup ----------------
mkvenv() { python3 -m venv .venv && source .venv/bin/activate && pip install -q --upgrade pip &&
  { pip install -q -r requirements.txt || { echo "pinned install failed; installing requests/pytest pinned + matplotlib unpinned";
      pip install -q requests==2.34.2 pytest==9.1.1 matplotlib; }; } && pip install -q -e .; }
setup() {
  [ -f "$ST/setup.done" ] && { log "setup already done"; return; }
  log "setup start (WSL copy at $MAIN)"
  if [ ! -d "$MAIN/.git" ]; then
    cp -r "$SRC" "$MAIN" || die "copy to $MAIN failed"
    rm -rf "$MAIN/_hasan_runs" "$MAIN/.venv"
  fi
  cd "$MAIN"
  git config core.fileMode false            # Windows copy marks every file executable; not a content change
  git ls-files --deleted | grep -qx runs/.gitkeep && git checkout -- runs/.gitkeep   # restore the empty tracked file to the commit
  git log --oneline -1 | grep -q "^$COMMIT" || die "HEAD is $(git log --oneline -1), expected $COMMIT"
  [ -z "$(git status --porcelain --untracked-files=no)" ] || { git status --short | grep -v '^??' ; die "tracked files differ from $COMMIT (listed above)"; }
  [ -f .env ] || { cp .env.example .env; die "no .env: put YOUR Cerebras key in $MAIN/.env (CEREBRAS_API_KEY=...) and rerun"; }
  grep -q your_key_here .env && die "the .env still has the placeholder key: edit $MAIN/.env and rerun"
  log "setup: install_env (enter your Ubuntu password if asked)"
  bash scripts/install_env.sh 2>&1 | tee "$OUT/setup_install_env.log" | tail -3; [ ${PIPESTATUS[0]} -eq 0 ] || die "install_env.sh failed (see _hasan_runs/setup_install_env.log)"
  if [ ! -x $J21/bin/java ]; then log "setup: Java 21 for JNose"; sudo apt-get install -y openjdk-21-jdk >"$OUT/setup_java21.log" 2>&1 || die "Java 21 install failed"; fi
  export PATH=$J21/bin:$HOME/apache-maven-3.9.9/bin:$PATH
  step venv mkvenv; source .venv/bin/activate
  step setup_projects bash scripts/setup_projects.sh
  step get_jnose bash src/testdebt/team/hasan/get_jnose.sh
  step check_builds bash scripts/check_builds.sh
  grep -q "EXIT=[1-9]" "$OUT/setup_check_builds.log" && { cat "$OUT/setup_check_builds.log"; die "a project build failed (check_builds)"; }
  step pytest python3 -m pytest -q; log "pytest: $(tail -1 "$OUT/setup_pytest.log")"
  step smoke python3 scripts/smoke_test.py; log "smoke test: LLM call OK"
  sed -i '/^text  :/d' "$OUT/setup_smoke.log"
  [ -z "$(git status --porcelain --untracked-files=no)" ] || die "tree not clean after setup: $(git status --short | grep -v '^??')"
  for d in data/projects/*/; do [ -z "$(git -C "$d" status --porcelain --untracked-files=no)" ] || die "project $d modified after setup"; done
  if [ ! -d "$E1D/.git" ]; then   # step 4: separate copy for E1
    log "setup: E1 copy at $E1D"; cp -r "$MAIN" "$E1D" && cd "$E1D" && rm -rf runs/* .venv && deactivate && step venv_e1 mkvenv; cd "$MAIN"
  fi
  touch "$ST/setup.done"; log "setup done"
}

# ---------------- step 3/4: runs ----------------
X="python3 -m testdebt.team.gulsher.experiments"
CMDS=( "1|E3 --only s3 --seeds 1" "2|E5 --only s3-G1 --seeds 1" "3|E2 --only b1" "4|E2 --only b0" "5|E2 --only b2"
       "6|E3 --only s3 --seeds 2" "7|E5 --only s3-G1 --seeds 2" "8|E3 --only s3 --seeds 3" "9|E5 --only s3-G1 --seeds 3"
       "10|E2 --only single" "11a|E5 --only s3-G2" "11b|E5 --only s3-G6" "11c|E5 --only s3-memory" "11d|E5 --only minus_all"
       "12|ES" )
left() { echo $(( DEADLINE_TS - $(date +%s) )); }
fix_projects() { local d; for d in "$1"/data/projects/*/; do
  [ -n "$(git -C "$d" status --porcelain --untracked-files=no)" ] && { log "restoring project checkout $d"; git -C "$d" checkout -- .; }; done; }
wait_budget() {  # wait for the next PKT day (token cap) or 30 min (provider limit), never past the deadline
  local now=$(date +%s) until
  if [ "$1" = cap ]; then until=$(date -d "tomorrow 00:05" +%s); else until=$((now + 1800)); fi
  [ $until -gt $DEADLINE_TS ] && until=$DEADLINE_TS
  log "waiting until $(date -d @$until '+%a %H:%M') ($1)"; sleep $(( until - now > 0 ? until - now : 0 ))
}
run_cmd() {  # run_cmd <dir> <n> <exp args...>
  local dir=$1 n=$2; shift 2; local lf="$OUT/cmd$n.log" fails=0 rc
  [ "$(cat "$ST/$n" 2>/dev/null)" = finished ] && return 0
  while :; do
    [ "$(left)" -le 60 ] && { echo partial > "$ST/$n"; log "#$n stopped at the deadline"; return 2; }
    echo running > "$ST/$n"; log "#$n start: experiments run $* --frozen"
    ( envset "$dir"; timeout --signal=INT --kill-after=120 "$(left)" $X run "$@" --frozen ) >> "$lf" 2>&1; rc=$?
    [ $rc -eq 0 ] && { echo finished > "$ST/$n"; log "#$n finished"; return 0; }
    echo partial > "$ST/$n"
    if [ $rc -eq 124 ] || [ "$(left)" -le 60 ]; then log "#$n stopped at the deadline"; return 2; fi
    local t; t=$(tail -40 "$lf")
    if   grep -q "daily token cap reached" <<<"$t"; then wait_budget cap
    elif grep -q "provider still rate-limiting" <<<"$t"; then wait_budget provider
    elif grep -q "needs clean project checkouts" <<<"$t"; then fix_projects "$dir"
    elif grep -q "needs a clean tree" <<<"$t"; then echo failed > "$ST/$n"; die "#$n: --frozen needs a clean tree (a tracked file changed). Report to Hasan; nothing was reverted."
    else fails=$((fails+1)); log "#$n failed (attempt $fails): $(tail -1 "$lf")"
         [ $fails -ge 2 ] && { echo failed > "$ST/$n"; log "#$n failed twice; last 30 lines saved in cmd$n.log; moving on"; return 1; }
    fi
  done
}
e1_loop() { run_cmd "$E1D" E1 E1; }

# ---------------- step 5: package + status note ----------------
progress() {  # progress <dir> <run_id>: unique tests with a non-error decision
  python3 - "$1/runs/$2/state.jsonl" <<'PY' 2>/dev/null || echo 0
import json, sys
seen = set()
for l in open(sys.argv[1]):
    r = json.loads(l); t = r["test"]
    if r.get("decision") != "error": seen.add((t["project"], t["class_name"], t.get("method") or t.get("method_name")))
print(len(seen))
PY
}
rids() { local exp only seeds; set -- $1; exp=$1; shift; only=""; seeds=""
  while [ $# -gt 0 ]; do case $1 in --only) only=$2; shift;; --seeds) seeds=$2; shift;; esac; shift; done
  case "$exp/$only" in ES/) echo ES_s3-retries0_s1 ES_s3-retries1_s1 ES_s3-retries2_s1 ES_s3-retries4_s1;;
    *) echo "${exp}_${only}_s${seeds:-1}";; esac; }
status_note() {
  local fin="" par="" nr="" fl="" e n rest st r tot
  for e in "${CMDS[@]}"; do n=${e%%|*}; rest=${e#*|}; st=$(cat "$ST/$n" 2>/dev/null || echo notrun)
    case $st in
      finished) fin+="#$n, ";;
      partial|running) tot=150; [ "$n" = 12 ] && tot=80
        for r in $(rids "$rest"); do par+="#$n $r ($(progress "$MAIN" $r)/$( [ $n = 12 ] && echo 20 || echo 150)), "; done;;
      failed) fl+="#$n, ";;
      *) nr+="#$n, ";; esac; done
  local e1st=$(cat "$ST/E1" 2>/dev/null || echo notrun) e1n=$(progress "$E1D" E1_b0replay_s1)
  local errs; errs=$(cat "$OUT"/cmd*.log "$OUT"/E1.log 2>/dev/null | grep -E "failed; fix|Error|Exception|refuse" | sed 's/[0-9]\{2,\}/N/g' | sort | uniq -c | sort -rn | awk '$1>1' | head -5)
  cat <<NOTE
commit: $COMMIT
finished: ${fin%, }
partial:  ${par%, }
not run:  ${nr%, }
failed:   ${fl:-none}
E1: $( [ "$e1st" = finished ] && echo finished || echo "stopped at $e1n/484 ($e1st)")
errors seen: ${errs:-none}
NOTE
}
package() {  # package <label>
  log "packaging ($1)"
  ( cd "$MAIN" && tar czf "$HOME/hasan_runs.tgz" runs/E2_* runs/E3_* runs/E5_* runs/ES_* runs/llm_calls.jsonl 2>/dev/null )
  ( cd "$E1D" && tar czf "$HOME/hasan_e1.tgz" runs/E1_* 2>/dev/null )
  cp -f "$HOME/hasan_runs.tgz" "$HOME/hasan_e1.tgz" "$OUT/" 2>/dev/null
  status_note > "$OUT/STATUS.txt"; ls -lh "$OUT"/*.tgz | tee -a "$OUT/progress.log"; cat "$OUT/STATUS.txt"
  cp -f "$OUT/STATUS.txt" "$OUT/STATUS_$1.txt"
}
partial_timer() { local s=$(( PARTIAL_TS - $(date +%s) )); [ $s -gt 0 ] && { sleep $s; package saturday_partial; }; }

case "${1:-all}" in
  status)  status_note; exit;;
  package) package manual; exit;;
  setup)   setup; exit;;
  all)     setup
           log "E1 starts in parallel in $E1D (log: _hasan_runs/cmdE1.log)"; e1_loop & E1PID=$!
           partial_timer & PTPID=$!
           for e in "${CMDS[@]}"; do run_cmd "$MAIN" "${e%%|*}" ${e#*|}; [ $? -eq 2 ] && break; done
           log "LLM runs loop ended; waiting for E1 (until the deadline at most)"
           while kill -0 $E1PID 2>/dev/null && [ "$(left)" -gt 0 ]; do sleep 60; done
           kill $E1PID $PTPID 2>/dev/null
           if [ "$(left)" -le 60 ]; then pkill -INT -f "testdebt.cli --run-id"; sleep 30; pkill -f "testdebt.cli --run-id"; fi
           package final
           log "DONE. Send _hasan_runs/hasan_runs.tgz, hasan_e1.tgz and STATUS.txt to Saqib.";;
esac
