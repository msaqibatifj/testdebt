#!/usr/bin/env bash
# Lane A (#2) has printed nothing since 20:56. Usual cause: a Maven/PIT step hit its timeout, Maven was killed, but a forked
# Java process (PIT minion / test JVM) kept running and holds the output pipe, so the run waits forever.
# This lists Java/Maven processes working inside ~/AgenticProj (lane A only, not the _c/_d/... copies) running > 20 min,
# then stops them. The test in progress is then recorded as a tool error and the run continues. No file is changed.
LANE="$HOME/AgenticProj"
found=""
for p in $(pgrep -f 'java|mvn|plexus'); do
  cwd=$(readlink "/proc/$p/cwd" 2>/dev/null) || continue
  case "$cwd/" in "$LANE"/*) ;; *) continue;; esac
  et=$(ps -o etimes= -p "$p" 2>/dev/null | tr -d ' '); [ "${et:-0}" -gt 1200 ] || continue
  echo "PID $p  running $((et/60)) min  in ${cwd#$HOME/}  : $(ps -o args= -p "$p" | cut -c1-90)"; found+="$p "
done
[ -z "$found" ] && { echo "No Java/Maven process in lane A older than 20 min. Tell Claude (the hang is elsewhere)."; exit 0; }
read -rp "Stop these processes? [y/N] " a; [ "$a" = y ] || exit 0
kill $found; sleep 15; for p in $found; do kill -0 "$p" 2>/dev/null && kill -9 "$p"; done
echo "Stopped. Lane A should log its next test within a few minutes."
