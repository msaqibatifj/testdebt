#!/usr/bin/env bash
# Read-only key check: one tiny request per key (a few tokens). Prints only the HTTP status and Cerebras rate-limit headers.
# The key is typed hidden and never printed or saved.  Usage: bash check_key.sh   (Enter on an empty prompt to stop)
while :; do
  read -rsp "Paste a Cerebras key to check (Enter = done): " K; echo
  [ -z "$K" ] && break
  H=$(mktemp); code=$(curl -sS -m 60 -o /dev/null -D "$H" -w '%{http_code}' https://api.cerebras.ai/v1/chat/completions \
      -H "Authorization: Bearer $K" -H "Content-Type: application/json" \
      -d '{"model":"gpt-oss-120b","messages":[{"role":"user","content":"hi"}],"max_completion_tokens":5}'); unset K
  case $code in
    200) echo "  -> WORKS (limit available)";;
    429) echo "  -> STILL LIMITED (429)";;
    401|403) echo "  -> key rejected ($code): wrong or revoked key";;
    *) echo "  -> HTTP $code";;
  esac
  grep -iE '^(x-ratelimit|retry-after)' "$H" | sed 's/^/     /'; rm -f "$H"
done
