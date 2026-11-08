#!/usr/bin/env bash
# Package the seed-2/3 runs (Step 4 of the seeds prompt): one ~/seeds_<folder>.tgz per folder, copied to
# _hasan_runs/seeds/ in the Windows folder, plus STATUS.txt listing every run, its test count and whether its report exists.
OUT=/mnt/c/Users/ha797/Downloads/AgenticProj_backup_2026-11-06_v4/AgenticProj/_hasan_runs/seeds; mkdir -p "$OUT"
shopt -s nullglob
{ echo "commit: e9ff1c8 (seeds 2 and 3), packaged $(TZ=Asia/Karachi date '+%a %d %b %H:%M PKT')"; echo; } > "$OUT/STATUS.txt"
for d in "$HOME"/AgenticProj "$HOME"/AgenticProj_{e1,c,d,e,f,g,h,i,j,k,l}; do
  [ -d "$d/runs" ] || continue; cd "$d" || continue
  runs=(runs/E2_*_s[23] runs/E5_*_s[23] runs/ES_*_s[23]); [ ${#runs[@]} -eq 0 ] && continue
  b=$(basename "$d"); tar czf "$HOME/seeds_$b.tgz" "${runs[@]}" && cp -f "$HOME/seeds_$b.tgz" "$OUT/"
  for r in "${runs[@]}"; do
    n=$(python3 -c "import json,sys;print(len({(x['test']['project'],x['test']['class_name'],x['test']['method']) for x in map(json.loads,open(sys.argv[1]))}))" "$r/state.jsonl" 2>/dev/null || echo 0)
    printf '%-28s %-18s tests=%-4s report=%s\n' "$(basename "$r")" "$b" "$n" "$([ -f "$r/report.json" ] && echo yes || echo NO)" >> "$OUT/STATUS.txt"
  done
done
ls -lh "$OUT"/seeds_*.tgz; echo; cat "$OUT/STATUS.txt"
