"""S3 (multi-agent with Supervisor) on the demo project with a fake LLM and a fake Maven."""
import json

from conftest import DEMO_TEST, FakeLLM, FakeMaven
from test_end_to_end_mock import BAD, kb  # noqa: F401  (pytest fixture)
from test_verify import GOOD
from testdebt.agents import Supervisor
from testdebt.contracts import DebtFinding, TestRef
from testdebt.eval import metrics
from testdebt.pipeline import Config
from testdebt.verify import Verifier

OK = {"compiled": True, "passed": True, "log": ""}
FAIL = {"compiled": False, "passed": False, "log": "[ERROR] cannot find symbol: variable cart"}


def run(replies, maven, demo, kb, tmp_path):
    t = TestRef("demo", str(demo), str(demo / DEMO_TEST), "ShoppingCartTest", "testTotals")
    llm = FakeLLM(replies)
    sup = Supervisor(llm, Verifier(FakeMaven(maven)), kb, Config(system="s3"), tmp_path / "s3")
    return sup.process(t, DebtFinding(t, ["AssertionRoulette"])), llm, sup


def actions(st):
    return [(e["agent"], e["action"]) for e in st.trace]


def test_s3_retries_with_feedback_then_accepts(demo, kb, tmp_path):
    st, llm, sup = run([BAD, f"```java\n{GOOD}\n```"], [OK], demo, kb, tmp_path)
    assert st.decision == "accepted" and len(st.proposals) == 2
    assert ("supervisor", "retry") in actions(st) and ("supervisor", "accept") in actions(st)
    assert "unbalanced" in llm.prompts[1]
    assert (demo / DEMO_TEST).read_text().count("expectedTotal") == 0          # project restored
    rec = json.loads(sup.state_file.read_text().splitlines()[0])
    assert rec["system"] == "s3" and rec["trace"][0]["agent"] == "detection"


def test_s3_switches_strategy_after_same_gate_fails_twice(demo, kb, tmp_path):
    good = f"```java\n{GOOD}\n```"
    st, llm, _ = run([good, good.replace("3)", "3 )"), good.replace("750", "750 ")], [OK, FAIL, FAIL, OK],
                     demo, kb, tmp_path)
    assert ("supervisor", "switch") in actions(st)
    assert "Chain-of-Thought" in llm.prompts[0] and "Chain-of-Thought" not in llm.prompts[2]   # KB -> plain


def test_s3_memory_blocks_repeated_proposal_and_escalates(demo, kb, tmp_path):
    st, _, sup = run([BAD, BAD, BAD], [OK], demo, kb, tmp_path)
    assert st.decision == "escalated" and len(st.proposals) == 3
    assert ("supervisor", "memory-hit") in actions(st) and ("supervisor", "escalate") in actions(st)
    o = metrics.report(metrics.load(sup.state_file))["overall"]
    assert o["tests"] == 1 and o["accepted_rate"] == 0.0


def test_s3_records_exception_as_error(demo, kb, tmp_path):
    st, _, sup = run([], [OK], demo, kb, tmp_path)
    assert st.decision == "error" and "IndexError" in st.reason
    assert metrics.summarize(metrics.load(sup.state_file))["errors"] == 1
