"""B2 (single tool-using agent) on the demo project with a fake LLM and a fake Maven."""
from conftest import DEMO_TEST, FakeLLM, FakeMaven
from test_agents_s3 import FAIL, OK, actions
from test_end_to_end_mock import BAD, kb  # noqa: F401  (pytest fixture)
from test_verify import GOOD
from testdebt.agents import B2Agent
from testdebt.contracts import DebtFinding, TestRef
from testdebt.pipeline import Config
from testdebt.verify import Verifier

G = f"```java\n{GOOD}\n```"


def run(replies, maven, demo, kb, tmp_path, **cfg):
    t = TestRef("demo", str(demo), str(demo / DEMO_TEST), "ShoppingCartTest", "testTotals")
    llm, mvn = FakeLLM(replies), FakeMaven(maven)
    agent = B2Agent(llm, Verifier(mvn), kb, Config(system="b2", **cfg), tmp_path / "b2")
    return agent.process(t, DebtFinding(t, ["AssertionRoulette"])), llm, mvn


def test_agent_uses_tools_then_submits(demo, kb, tmp_path):  # noqa: F811
    st, llm, mvn = run([f"ACTION: detect\n{G}", f"ACTION: compile_and_run\n{G}", f"ACTION: submit\n{G}"],
                       [OK, OK, OK], demo, kb, tmp_path)
    assert st.decision == "accepted" and st.system == "b2" and len(st.proposals) == 3
    assert "ACTION: submit" in llm.prompts[0] and "NOT enabled" in llm.prompts[0]       # no PIT in this run
    assert llm.prompts[1].startswith("Tool result (detect)") and "none" in llm.prompts[1]
    assert "compiles and all tests of the class pass" in llm.prompts[2]
    assert mvn.results == []                    # baseline + compile_and_run + submit; detect never builds
    assert [a for a in actions(st) if a[0] == "verifier"] == [("verifier", "detect"), ("verifier", "compile_and_run"),
                                                              ("verifier", "submit")]
    assert (demo / DEMO_TEST).read_text().count("expectedTotal") == 0          # project restored


def test_failed_submit_is_rejected_without_a_retry(demo, kb, tmp_path):  # noqa: F811
    st, llm, _ = run([f"ACTION: submit\n{G}", f"ACTION: submit\n{G}"], [OK, FAIL], demo, kb, tmp_path)
    assert st.decision == "rejected" and "compilation failed" in st.reason and len(llm.prompts) == 1


def test_tool_feedback_lets_the_agent_fix_its_code(demo, kb, tmp_path):  # noqa: F811
    st, llm, _ = run([f"ACTION: compile_and_run\n{BAD}", "no action here", f"ACTION: submit\n{G}"], [OK, OK],
                     demo, kb, tmp_path)
    assert "unbalanced" in llm.prompts[1] and "No action found" in llm.prompts[2] and st.decision == "accepted"
    assert ("agent", "invalid-action") in actions(st)


def test_stops_at_max_steps_or_token_cap(demo, kb, tmp_path):  # noqa: F811
    st, _, _ = run([f"ACTION: detect\n{G}"] * 2, [OK], demo, kb, tmp_path, max_steps=2)
    assert st.decision == "rejected" and st.reason == "no submit within 2 replies" and len(st.proposals) == 2
    st, _, _ = run([f"ACTION: detect\n{G}"] * 5, [OK], demo, kb, tmp_path / "cap", token_cap_per_test=200)
    assert st.reason == "token cap reached before submit" and len(st.proposals) == 2
