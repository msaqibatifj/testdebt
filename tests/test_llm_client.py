"""LLM client: rate-limit retry with retry-after, and the daily token cap (no network)."""
import json
import time

import pytest

from testdebt import llm_client
from testdebt.llm_client import BudgetExhausted, LLMClient


class Resp:
    def __init__(self, status, headers=None, tokens=100):
        self.status_code, self.headers, self.text = status, headers or {}, "rate limited"
        self._tokens = tokens

    def json(self):
        return {"choices": [{"message": {"content": "ok"}}], "usage": {"total_tokens": self._tokens}}


def client(tmp_path, monkeypatch, responses, **kw):
    seq = list(responses)
    monkeypatch.setattr(llm_client.requests, "post", lambda *a, **k: seq.pop(0))
    sleeps = []
    c = LLMClient(api_key="k", log_path=tmp_path / "calls.jsonl", cache_dir=None, max_requests_per_min=1e9,
                  sleep=sleeps.append, **kw)
    return c, sleeps


def test_429_waits_for_retry_after_then_succeeds(tmp_path, monkeypatch):
    c, sleeps = client(tmp_path, monkeypatch, [Resp(429, {"retry-after": "2"}), Resp(200)])
    assert c.chat([{"role": "user", "content": "hi"}])["text"] == "ok"
    assert 2.0 in sleeps


def test_daily_cap_counts_todays_calls_only_and_stops_before_the_next_call(tmp_path, monkeypatch):
    log = tmp_path / "calls.jsonl"
    log.write_text(json.dumps({"ts": time.time() - 86400 * 2, "usage": {"total_tokens": 10**6}}) + "\n"  # older day
                   + json.dumps({"ts": time.time(), "usage": {"total_tokens": 150}}) + "\n")
    c, _ = client(tmp_path, monkeypatch, [Resp(200, tokens=100), Resp(200)], daily_token_cap=250)
    c.chat([{"role": "user", "content": "a"}])                   # 150 spent today < 250: allowed, now 250
    with pytest.raises(BudgetExhausted):
        c.chat([{"role": "user", "content": "b"}])               # 250 >= 250: stops before calling


def test_budget_stop_is_not_recorded_as_error_so_resume_retries_the_test(demo, tmp_path):
    from conftest import DEMO_TEST, FakeMaven
    from testdebt.contracts import DebtFinding, TestRef
    from testdebt.pipeline import Config, Pipeline
    from testdebt.prompts import KnowledgeBase
    from testdebt.verify import Verifier

    class BrokeLLM:
        model = "fake"

        def chat(self, messages, **kw):
            raise BudgetExhausted("cap")

    t = TestRef("demo", str(demo), str(demo / DEMO_TEST), "ShoppingCartTest", "testTotals")
    p = Pipeline(BrokeLLM(), Verifier(FakeMaven()), KnowledgeBase(tmp_path / "none"), Config(system="single"),
                 tmp_path / "run")
    with pytest.raises(BudgetExhausted):
        p.process(t, DebtFinding(t, ["AssertionRoulette"]))
    assert t.id not in p.done_ids()
