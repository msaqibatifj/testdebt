#!/usr/bin/env bash
# Read-only: tokens each lane's CURRENT key used today (PKT day, uncached calls, same rule as the run's daily cap).
export TZ=Asia/Karachi
for L in A:AgenticProj B:AgenticProj_e1 C:AgenticProj_c D:AgenticProj_d E:AgenticProj_e; do
  f="$HOME/${L#*:}/runs/llm_calls.jsonl"; [ -f "$f" ] || { echo "lane ${L%%:*}: no calls yet"; continue; }
  python3 - "$f" "${L%%:*}" <<'PY'
import json, sys, time
t0 = time.mktime(time.strptime(time.strftime("%Y-%m-%d"), "%Y-%m-%d")); used = 0; err429 = 0
for line in open(sys.argv[1], encoding="utf-8"):
    try: r = json.loads(line)
    except Exception: continue
    if r.get("ts", 0) < t0: continue
    if "error" in r and "429" in str(r["error"]): err429 += 1
    if not r.get("cached"): used += (r.get("usage") or {}).get("total_tokens", 0)
print(f"lane {sys.argv[2]}: {used:,} used today, {max(0, 950000 - used):,} left of 950,000"
      + (f"  ({err429} rate-limit refusals from Cerebras)" if err429 else ""))
PY
done
