"""Whole pipeline on the demo project with a fake LLM and a fake Maven (no network, no Java)."""
import json

import pytest

from conftest import DEMO_TEST, FakeLLM, FakeMaven
from test_verify import GOOD
from testdebt.contracts import DebtFinding, TestRef
from testdebt.eval import metrics
from testdebt.pipeline import Config, Pipeline
from testdebt.prompts import KnowledgeBase
from testdebt.verify import Verifier

BAD = "```java\n@Test\npublic void testTotals() { assertEquals(750, cart.total());\n```"   # unbalanced


@pytest.fixture
def kb(tmp_path):
    root = tmp_path / "utr/refactoring/prompt_generation"
    for folder in ("smelltype", "refactor_rules", "checkpoints"):
        (root / folder).mkdir(parents=True)
        (root / folder / "Assertion_Roulette.txt").write_text(folder)
    return KnowledgeBase(tmp_path / "utr")


def run(system, replies, maven_results, demo, kb, tmp_path):
    t = TestRef("demo", str(demo), str(demo / DEMO_TEST), "ShoppingCartTest", "testTotals")
    llm = FakeLLM(replies)
    p = Pipeline(llm, Verifier(FakeMaven(maven_results)), kb, Config(system=system), tmp_path / f"run_{system}")
    st = p.process(t, DebtFinding(t, ["AssertionRoulette", "DuplicateAssert"]))
    return st, llm, p


def test_b1_retries_with_error_text_then_accepts(demo, kb, tmp_path):
    fail = {"compiled": False, "passed": False, "log": "[ERROR] cannot find symbol: variable cart"}
    # call 1 = baseline check of the ORIGINAL class, then: attempt1 static fail, attempt2 compile fail, attempt3 ok
    st, llm, p = run("b1", [BAD, f"```java\n{GOOD}\n```", f"```java\n{GOOD}\n```"],
                     [{"compiled": True, "passed": True, "log": ""}, fail], demo, kb, tmp_path)
    assert st.decision == "accepted" and len(st.proposals) == 3
    assert "unbalanced" in llm.prompts[1] and "cannot find symbol" in llm.prompts[2]
    assert (demo / DEMO_TEST).read_text().count("expectedTotal") == 0         # project untouched
    rec = json.loads(p.state_file.read_text().splitlines()[0])
    assert rec["retries"] == 2 and rec["test_id"] == "demo:ShoppingCartTest#testTotals"


def test_b0_single_pass_rejects_without_retry(demo, kb, tmp_path):
    st, llm, _ = run("b0", [BAD], [], demo, kb, tmp_path)
    assert st.decision == "rejected" and len(st.proposals) == 1 and "Chain-of-Thought" in llm.prompts[0]


def test_skip_when_original_class_fails(demo, kb, tmp_path):
    st, llm, _ = run("b1", [], [{"compiled": True, "passed": False, "log": "boom"}], demo, kb, tmp_path)
    assert st.decision == "skipped" and not llm.prompts            # no tokens spent


def test_phase2_systems_are_explicitly_not_implemented(kb, tmp_path):
    with pytest.raises(NotImplementedError):
        Pipeline(FakeLLM([]), Verifier(None), kb, Config(system="b2"), tmp_path / "r")
    with pytest.raises(ValueError):                                 # s3 has its own runner (agents.Supervisor)
        Pipeline(FakeLLM([]), Verifier(None), kb, Config(system="s3"), tmp_path / "r")


def test_metrics_from_state(demo, kb, tmp_path):
    _, _, p = run("b0", [f"```java\n{GOOD}\n```"], [], demo, kb, tmp_path)
    rep = metrics.report(metrics.load(p.state_file))
    o = rep["overall"]
    assert o["tests"] == 1 and o["accepted_rate"] == 100.0 and o["smell_reduction_tsdetect"] == 100.0


def test_skip_verify_is_not_reported_as_acceptance(demo, kb, tmp_path):
    t = TestRef("demo", str(demo), str(demo / DEMO_TEST), "ShoppingCartTest", "testTotals")
    p = Pipeline(FakeLLM([f"```java\n{GOOD}\n```"]), Verifier(None, run_tests=False), kb, Config(system="b0"),
                 tmp_path / "rs")
    st = p.process(t, DebtFinding(t, ["AssertionRoulette"]))
    assert "NOT compiled" in st.reason
    o = metrics.report(metrics.load(p.state_file))["overall"]
    assert o["verified"] is False and o["accepted_rate"] is None and o["accepted_unverified"] == 1


def test_exception_is_recorded_as_error_and_retried_on_resume(demo, kb, tmp_path):
    # FakeLLM runs out of replies on attempt 2 -> IndexError, like an HTTP 401 mid-run
    st, _, p = run("b1", [BAD], [], demo, kb, tmp_path)
    assert st.decision == "error" and st.reason.startswith("IndexError") and len(st.proposals) == 1
    assert (demo / DEMO_TEST).read_text().count("expectedTotal") == 0         # project untouched
    assert p.done_ids() == set()                                               # resume retries it
    t = st.test
    p.llm = FakeLLM([f"```java\n{GOOD}\n```"])
    p.process(t, DebtFinding(t, ["AssertionRoulette"]))
    recs = metrics.load(p.state_file)
    assert len(p.state_file.read_text().splitlines()) == 2 and len(recs) == 1   # counted once, last record wins
    assert recs[0]["decision"] == "accepted" and metrics.summarize(recs)["errors"] == 0


def test_reduction_among_accepted_ignores_rejected_outputs():
    def rec(decision, after):
        return {"decision": decision, "finding": {"smells": ["A", "B"]}, "retries": 0, "tokens": 0,
                "wall_time_s": 0, "reports": [{"sane": True, "compiled": True, "passed": True, "smells_after": after}]}
    s = metrics.summarize([rec("accepted", ["A"]), rec("rejected", [])])
    assert s["smell_reduction_tsdetect"] == 75.0 and s["smell_reduction_accepted"] == 50.0
