#!/usr/bin/env bash
# Lane A (#2) silent since 20:56 with no long Java process: most likely its key hit Cerebras' limit and the LLM client is
# sleeping on a long "retry-after" (same as the old keys B/C this morning). This shows the evidence, then (if you agree)
# gives lane A a key from the pool and restarts only lane A's run; it resumes from its saved tests. Keys are never printed.
export TZ=Asia/Karachi
LANE="$HOME/AgenticProj"; POOL="$HOME/.hasan_keypool"; PLOCK="$HOME/.hasan_keypool.lock"
echo "== lane A run process:"; pgrep -af "testdebt.cli --run-id E5_s3-G1_s1" | cut -c1-120 || echo "  (none running)"
echo "== last LLM calls of lane A:"
python3 - "$LANE/runs/llm_calls.jsonl" <<'PY'
import json, sys, time
rows = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
for r in rows[-4:]:
    print("  ", time.strftime("%H:%M:%S", time.localtime(r.get("ts", 0))), "cached" if r.get("cached") else "",
          (r.get("error") or "")[:110] or f"ok, {(r.get('usage') or {}).get('total_tokens', 0)} tokens")
t0 = time.mktime(time.strptime(time.strftime("%Y-%m-%d"), "%Y-%m-%d"))
print("   tokens used today on this key:", sum((r.get("usage") or {}).get("total_tokens", 0) for r in rows if r.get("ts", 0) >= t0 and not r.get("cached")))
PY
echo "== keys in pool: $( [ -s "$POOL" ] && grep -c . "$POOL" || echo 0 )"
read -rp "Give lane A a pool key and restart lane A's run? [y/N] " a; [ "$a" = y ] || exit 0
until mkdir "$PLOCK" 2>/dev/null; do sleep 0.2; done
K=$(head -1 "$POOL"); tail -n +2 "$POOL" > "$POOL.t"; mv -f "$POOL.t" "$POOL"; chmod 600 "$POOL"; rmdir "$PLOCK"
[ -z "$K" ] && { echo "pool empty"; exit 1; }
cp -p "$LANE/.env" "$LANE/.env.prev"; { grep -v '^CEREBRAS_API_KEY=' "$LANE/.env.prev"; printf 'CEREBRAS_API_KEY=%s\n' "$K"; } > "$LANE/.env"; unset K; chmod 600 "$LANE/.env"; rm -f "$LANE/.env.prev"
mv "$LANE/runs/llm_calls.jsonl" "$LANE/runs/llm_calls_key_until_$(date +%Y%m%d_%H%M%S).jsonl"
pkill -INT -f "testdebt.cli --run-id E5_s3-G1_s1"; sleep 10; pkill -9 -f "testdebt.cli --run-id E5_s3-G1_s1" 2>/dev/null
echo "Done: lane A has a new key; the runner restarts #2 within a few seconds and resumes from test 144."
