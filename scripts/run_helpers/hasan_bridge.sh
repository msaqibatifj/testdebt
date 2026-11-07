#!/usr/bin/env bash
# Lets Claude run commands in this Ubuntu (WSL) while the experiments run, without you typing them.
# Claude writes a command file into _bridge/ (in this project folder); this loop runs it as you (no sudo) and writes the output back.
# Every command and its output stay visible in _bridge/ and in this window.  Stop any time with Ctrl+C.
B="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_bridge"; mkdir -p "$B/done"
echo "Bridge running: watching $B (Ctrl+C to stop)"
while :; do
  for f in "$B"/cmd_*.sh; do [ -f "$f" ] || continue
    id=$(basename "$f" .sh); id=${id#cmd_}
    echo "[$(date '+%H:%M:%S')] running $id:"; sed 's/^/    /' "$f"
    ( cd "$HOME" && timeout 900 bash "$f" ) > "$B/out_$id.txt" 2>&1; echo "exit=$?" >> "$B/out_$id.txt"
    mv -f "$f" "$B/done/"; echo "[$(date '+%H:%M:%S')] done $id ($(tail -1 "$B/out_$id.txt"))"
  done
  sleep 3
done
