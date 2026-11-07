#!/usr/bin/env bash
# Finish #2 (E5 s3-G1 seed 1, 143/150 saved) in lane A, then rebuild the final package.
# 1) picks a key that Cerebras says still has >=150k tokens today (checks lane A's key and the pool; keys never printed)
# 2) runs the same --frozen command (resumes from the saved tests) with a watchdog: no new test for 20 min -> switch key, rerun
# 3) marks #2 finished and rebuilds hasan_runs.tgz / hasan_e1.tgz / STATUS.txt
export TZ=Asia/Karachi
SRC=/mnt/c/Users/ha797/Downloads/AgenticProj_backup_2026-11-06_v4/AgenticProj; OUT="$SRC/_hasan_runs"
LANE="$HOME/AgenticProj"; POOL="$HOME/.hasan_keypool"
cd "$LANE" && source .venv/bin/activate || exit 1
export PATH=/usr/lib/jvm/java-21-openjdk-amd64/bin:$HOME/apache-maven-3.9.9/bin:$PATH PIT_THREADS=8 PYTHONUNBUFFERED=1; unset CEREBRAS_API_KEY
left_today() { curl -sS -m 60 -o /dev/null -D - https://api.cerebras.ai/v1/chat/completions -H "Authorization: Bearer $1" \
  -H "Content-Type: application/json" -d '{"model":"gpt-oss-120b","messages":[{"role":"user","content":"hi"}],"max_completion_tokens":5}' \
  | tr -d '\r' | awk '/^HTTP/{c=$2} tolower($1)=="x-ratelimit-remaining-tokens-day:"{v=$2} END{print (c==200 ? v+0 : 0)}'; }
pick_key() {  # install the first key with >=150k tokens left today into lane A
  local cands=() k n i=0
  cands+=("$(grep '^CEREBRAS_API_KEY=' "$LANE/.env" | tail -1 | cut -d= -f2- | tr -d '\r')")
  [ -s "$POOL" ] && while IFS= read -r k; do [ -n "$k" ] && cands+=("$k"); done < "$POOL"
  for k in "${cands[@]}"; do i=$((i+1)); n=$(left_today "$k"); echo "  key $i: ${n:-0} tokens left today"
    if [ "${n:-0}" -ge 150000 ]; then
      { grep -v '^CEREBRAS_API_KEY=' "$LANE/.env"; printf 'CEREBRAS_API_KEY=%s\n' "$k"; } > "$LANE/.env.new"; mv -f "$LANE/.env.new" "$LANE/.env"; chmod 600 "$LANE/.env"
      [ -f runs/llm_calls.jsonl ] && mv runs/llm_calls.jsonl "runs/llm_calls_key_until_$(date +%Y%m%d_%H%M%S).jsonl"
      unset k cands; return 0; fi; done
  unset k cands; return 1; }
for try in 1 2 3; do
  echo "== attempt $try: choosing a key"; pick_key || { echo "No key has >=150k tokens left right now. Try again later (keys free up over 24 h)."; exit 1; }
  for d in data/projects/*/; do [ -n "$(git -C "$d" status --porcelain --untracked-files=no)" ] && { echo "restoring $d"; git -C "$d" checkout -- .; }; done
  echo "== running #2 (resumes from saved tests)"; echo running > "$OUT/state/2"
  python3 -m testdebt.team.gulsher.experiments run E5 --only s3-G1 --seeds 1 --frozen >> "$OUT/cmd2.log" 2>&1 & P=$!
  while kill -0 $P 2>/dev/null; do sleep 30
    if [ $(( $(date +%s) - $(stat -c %Y "$OUT/cmd2.log") )) -gt 1200 ]; then echo "no progress for 20 min -> switching key"
      pkill -INT -f "testdebt.cli --run-id E5_s3-G1_s1"; sleep 20; pkill -9 -f "testdebt.cli --run-id E5_s3-G1_s1"; kill $P 2>/dev/null; break; fi
    grep -E '^\[[0-9]+/150\]' "$OUT/cmd2.log" | tail -1 | cut -c1-100; done
  wait $P; rc=$?
  if [ $rc -eq 0 ]; then echo finished > "$OUT/state/2"; echo "== #2 finished; rebuilding the package"
    bash "$SRC/hasan_all.sh" package; shred -u "$POOL" 2>/dev/null; echo "ALL DONE. Send _hasan_runs/hasan_runs.tgz, hasan_e1.tgz and STATUS.txt to Saqib."; exit 0; fi
  echo "run stopped (rc=$rc); last lines:"; tail -3 "$OUT/cmd2.log" | cut -c1-160
done
echo partial > "$OUT/state/2"; echo "#2 not finished after 3 tries; tell Claude."; exit 1
