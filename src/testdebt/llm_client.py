"""Small logged, rate-limited, cached client for an OpenAI-compatible chat API (Cerebras).

Why this exists (AI4015 test-debt project):
  * every call is logged to JSONL (prompt, response, tokens, latency) -> cost/latency metrics + reproducibility
  * identical requests are served from a disk cache -> reruns do not burn free-tier quota
  * client-side pacing for the free-tier limits (5 requests/min) and retry/backoff on HTTP 429/5xx

Usage:
    export CEREBRAS_API_KEY=...            # never commit the key; use env var or an untracked .env
    from llm_client import LLMClient
    llm = LLMClient()                      # default model: gpt-oss-120b
    r = llm.chat([{"role": "user", "content": "Say hi"}], tag="smoke_test")
    print(r["text"], r["usage"])
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import requests


def _load_dotenv(path: str = ".env") -> None:
    """Minimal .env loader (KEY=VALUE lines); real environment variables win."""
    f = Path(path)
    if not f.exists():
        return
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()

BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.cerebras.ai/v1")
DEFAULT_MODEL = os.environ.get("LLM_MODEL", "gpt-oss-120b")  # pin ONE model for all experiments


class BudgetExhausted(BaseException):
    """Daily token cap reached. A BaseException so the per-test error capture (except Exception) does not record
    the current test as 'error': the run stops, and rerunning the same --run-id tomorrow resumes it."""


class LLMClient:
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
        base_url: str = BASE_URL,
        log_path: str | Path = "runs/llm_calls.jsonl",
        cache_dir: str | Path | None = "runs/cache",
        max_requests_per_min: float = 5,   # free trial limit; raise on a paid plan
        max_retries: int = 6,
        timeout: float = 120,
        sleep=time.sleep,
        daily_token_cap: int = 0,          # 0 = no cap; non-cached tokens per calendar day, counted from the log
    ) -> None:
        self.model = model
        self.api_key = api_key or os.environ.get("CEREBRAS_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.log_path = Path(log_path)
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.min_interval = 60.0 / max_requests_per_min
        self.max_retries = max_retries
        self.timeout = timeout
        self._sleep = sleep
        self._last_call = 0.0
        self.daily_token_cap = daily_token_cap
        self._day, self._spent = "", 0
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ helpers
    def _key(self, payload: dict[str, Any]) -> str:
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    def _pace(self) -> None:
        wait = self.min_interval - (time.monotonic() - self._last_call)
        if wait > 0:
            self._sleep(wait)

    def spent_today(self) -> int:
        # shortcut: reads the log once per day, then counts this process's calls; parallel processes sharing one
        # key each see only their own spend after start-up. Re-read the log per call if runs go parallel.
        day = time.strftime("%Y-%m-%d")
        if day != self._day:
            self._day = day
            self._spent = total_tokens(self.log_path, since=time.mktime(time.strptime(day, "%Y-%m-%d")))
        return self._spent

    def _log(self, record: dict[str, Any]) -> None:
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # --------------------------------------------------------------------- main
    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        tag: str = "",
        use_cache: bool = True,
        **extra: Any,
    ) -> dict[str, Any]:
        """Return {"text", "usage", "latency_s", "cached", "model"}. Raises RuntimeError after retries."""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **extra,
        }
        key = self._key(payload)
        cache_file = self.cache_dir / f"{key}.json" if self.cache_dir else None

        if use_cache and cache_file and cache_file.exists():
            hit = json.loads(cache_file.read_text(encoding="utf-8"))
            self._log({"ts": time.time(), "tag": tag, "key": key, "cached": True, **hit})
            return {**hit, "cached": True}

        if not self.api_key:
            raise RuntimeError("CEREBRAS_API_KEY is not set")
        if self.daily_token_cap and self.spent_today() >= self.daily_token_cap:
            raise BudgetExhausted(f"daily token cap reached ({self.spent_today()} >= {self.daily_token_cap} tokens "
                                  "today): rerun the same command with the same --run-id tomorrow to resume")

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        last_err = ""
        for attempt in range(self.max_retries):
            self._pace()
            t0 = time.monotonic()
            self._last_call = t0
            try:
                resp = requests.post(
                    f"{self.base_url}/chat/completions", headers=headers, json=payload, timeout=self.timeout
                )
            except requests.RequestException as e:  # network error -> retry
                last_err = f"network: {e}"
                self._sleep(min(2 ** attempt, 60))
                continue

            if resp.status_code == 200:
                data = resp.json()
                latency = time.monotonic() - t0
                msg = data["choices"][0]["message"]
                result = {
                    "model": data.get("model", self.model),
                    "text": msg.get("content") or "",
                    "usage": data.get("usage", {}),
                    "latency_s": round(latency, 3),
                    "request": payload,
                    "response_raw_message": msg,
                }
                if cache_file:
                    cache_file.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
                self._log({"ts": time.time(), "tag": tag, "key": key, "cached": False, **result})
                self.spent_today()
                self._spent += result["usage"].get("total_tokens", 0)
                return {**result, "cached": False}

            last_err = f"HTTP {resp.status_code}: {resp.text[:300]}"
            if resp.status_code == 400 and "seed" in payload and "seed" in resp.text.lower():
                payload.pop("seed")          # provider does not accept a seed: retry without it
                continue
            if resp.status_code in (429, 500, 502, 503, 504):
                retry_after = resp.headers.get("retry-after")
                delay = float(retry_after) if retry_after and retry_after.replace(".", "", 1).isdigit() else min(2 ** attempt * 5, 90)
                self._sleep(delay)
                continue
            break  # 4xx other than 429: do not retry

        self._log({"ts": time.time(), "tag": tag, "key": key, "error": last_err})
        raise RuntimeError(f"LLM call failed after retries: {last_err}")


def total_tokens(log_path: str | Path = "runs/llm_calls.jsonl", include_cached: bool = False, since: float = 0) -> int:
    """Sum total_tokens over the call log, for calls at or after `since` (epoch seconds)."""
    total = 0
    if not Path(log_path).exists():
        return 0
    for line in Path(log_path).read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if (rec.get("cached") and not include_cached) or rec.get("ts", 0) < since:
            continue
        total += rec.get("usage", {}).get("total_tokens", 0)
    return total
