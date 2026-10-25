"""S3 (multi-agent with Supervisor) on the demo project with a fake LLM and a fake Maven."""
import json

from conftest import DEMO_TEST, FakeLLM, FakeMaven
from test_end_to_end_mock import BAD, kb  # noqa: F401  (pytest fixture)
from test_verify import GOOD
from testdebt.agents import Supervisor
from testdebt.agents.planner import parse_plan
from testdebt.contracts import DebtFinding, TestRef
from testdebt.eval import metrics
from testdebt.pipeline import Config
from testdebt.verify import Verifier

OK = {"compiled": True, "passed": True, "log": ""}
FAIL = {"compiled": False, "passed": False, "log": "[ERROR] cannot find symbol: variable cart"}
AR, DA = "AssertionRoulette", "DuplicateAssert"
G = f"```java\n{GOOD}\n```"
# messages added (Assertion Roulette gone) but the duplicate assert kept, so only DuplicateAssert is left
HALF = ('```java\n@Test\npublic void testTotals() {\n    ShoppingCart cart = new ShoppingCart();\n'
        '    cart.add(new Item("pen", 250), 3);\n    assertEquals("total", 750, cart.total());\n'
        '    assertEquals("count", 3, cart.itemCount());\n    assertEquals("total", 750, cart.total());\n'
        '    assertTrue("has pen", cart.hasItem("pen"));\n}\n```')
# compiles and passes, but Assertion Roulette is still there
SAME = ('```java\n@Test\npublic void testTotals() {\n    ShoppingCart cart = new ShoppingCart();\n'
        '    cart.add(new Item("pen", 250), 3);\n    assertEquals(750, cart.total());\n'
        '    assertEquals(3, cart.itemCount());\n    assertEquals(750, cart.total());\n'
        '    assertTrue(cart.hasItem("pen"));\n}\n```')


def plan(*smells):
    return json.dumps({"smells": {s: f"fix {s} by the rule" for s in smells}, "split_groups": [],
                       "shared_state": ["cart with 3 pens"]})


def run(replies, maven, demo, kb, tmp_path, smells=(AR,), sup=None, **cfg):
    t = TestRef("demo", str(demo), str(demo / DEMO_TEST), "ShoppingCartTest", "testTotals")
    llm = FakeLLM(replies)
    if sup is None:
        sup = Supervisor(llm, Verifier(FakeMaven(maven)), kb, Config(system="s3", **cfg), tmp_path / "s3")
    else:
        sup.planner.llm = sup.refactor.llm = llm
        sup.verifier.maven = FakeMaven(maven)
    return sup.process(t, DebtFinding(t, list(smells))), llm, sup


def actions(st):
    return [(e["agent"], e["action"]) for e in st.trace]


def test_parse_plan_validates_the_schema():
    p = parse_plan("```json\n" + plan(AR) + "\n```", [AR])
    assert p["smells"] == {AR: f"fix {AR} by the rule"} and p["shared_state"] == ["cart with 3 pens"]
    assert parse_plan(plan(AR), [AR, DA]) is None                    # a targeted smell has no step
    assert parse_plan('{"smells": {"%s": 3}}' % AR, [AR]) is None    # step is not text
    assert parse_plan("I would add messages.", [AR]) is None
    assert parse_plan('{"smells": {"%s": "x"}, "split_groups": "a"}' % AR, [AR]) is None


def test_plan_goes_into_the_refactor_prompt_and_counts_tokens(demo, kb, tmp_path):
    st, llm, sup = run([plan(AR), G], [OK], demo, kb, tmp_path)
    assert st.decision == "accepted" and st.plan["smells"] == {AR: f"fix {AR} by the rule"}
    assert "Refactoring plan" in llm.prompts[1] and "cart with 3 pens" in llm.prompts[1]
    rec = json.loads(sup.state_file.read_text().splitlines()[0])
    assert rec["tokens"] == 200 and rec["plan_tokens"] == 100 and rec["trace"][0]["agent"] == "detection"
    assert (demo / DEMO_TEST).read_text().count("expectedTotal") == 0          # project restored


def test_invalid_plan_falls_back_to_the_kb_rule(demo, kb, tmp_path):
    st, llm, _ = run(["no plan here", G], [OK], demo, kb, tmp_path)
    assert st.decision == "accepted" and st.plan is None and ("planner", "plan-invalid") in actions(st)
    assert "Chain-of-Thought" in llm.prompts[1] and "Refactoring plan" not in llm.prompts[1]


def test_retry_with_feedback_then_accept(demo, kb, tmp_path):
    st, llm, _ = run([plan(AR), BAD, G], [OK], demo, kb, tmp_path)
    assert st.decision == "accepted" and len(st.proposals) == 2
    assert ("supervisor", "retry") in actions(st) and "unbalanced" in llm.prompts[2]


def test_switch_after_the_same_strategy_fails_twice_at_the_same_gate(demo, kb, tmp_path):
    st, llm, _ = run([plan(AR), G, G.replace("3)", "3 )"), G.replace("750", "750 ")], [OK, FAIL, FAIL, OK],
                     demo, kb, tmp_path)
    assert actions(st).count(("supervisor", "retry")) == 1 and ("supervisor", "switch") in actions(st)
    assert "Refactoring plan" in llm.prompts[2] and "Refactoring plan" not in llm.prompts[3]   # planner -> KB rule
    assert st.decision == "accepted"


def test_narrow_to_the_smells_still_left(demo, kb, tmp_path):
    st, llm, _ = run([plan(AR, DA), HALF, G], [OK], demo, kb, tmp_path, smells=(AR, DA))
    assert ("supervisor", "narrow") in actions(st) and st.decision == "accepted"
    assert f"- {DA}:" in llm.prompts[2] and f"- {AR}:" not in llm.prompts[2]


def test_revert_retries_from_the_best_earlier_proposal(demo, kb, tmp_path):
    st, llm, _ = run([plan(AR), SAME, G.replace("cart.total()", "cart.totl()"), G], [OK, OK, FAIL, OK],
                     demo, kb, tmp_path)
    assert ("supervisor", "revert") in actions(st) and st.decision == "accepted"
    assert "targeted smells still present" in llm.prompts[3] and "cart.totl()" not in llm.prompts[3]


def test_repeated_proposal_is_not_reverified_and_escalates(demo, kb, tmp_path):
    st, _, sup = run([plan(AR), BAD, BAD, BAD], [OK], demo, kb, tmp_path)
    assert st.decision == "escalated" and len(st.proposals) == 3
    assert ("supervisor", "memory-hit") in actions(st) and ("supervisor", "switch") in actions(st)
    assert ("supervisor", "escalate") in actions(st)
    o = metrics.report(metrics.load(sup.state_file))["overall"]
    assert o["tests"] == 1 and o["accepted_rate"] == 0.0


def test_failed_approaches_reach_the_planner_of_the_next_test(demo, kb, tmp_path):
    _, _, sup = run([plan(AR), BAD, BAD, BAD], [OK], demo, kb, tmp_path)
    assert f"fix {AR} by the rule -> failed at static check" in (sup.run_dir / "memory.json").read_text()
    _, llm, _ = run([plan(AR), G], [OK], demo, kb, tmp_path, sup=sup)
    assert "Approaches that already failed for AssertionRoulette" in llm.prompts[0]


def test_memory_off(demo, kb, tmp_path):
    st, _, sup = run([plan(AR), BAD, BAD, BAD], [OK], demo, kb, tmp_path, memory=False)
    assert ("supervisor", "memory-hit") not in actions(st) and not (sup.run_dir / "memory.json").exists()


def test_fixed_policy_is_b1s_retry_script(demo, kb, tmp_path):
    st, llm, _ = run([BAD, BAD, BAD], [OK], demo, kb, tmp_path, policy="fixed")
    assert st.decision == "escalated" and len(st.proposals) == 3 and st.plan is None
    assert all("Chain-of-Thought" in p for p in llm.prompts) and len(llm.prompts) == 3      # no planner call
    acts = actions(st)
    assert acts.count(("supervisor", "retry")) == 2 and not {("supervisor", "switch"), ("supervisor", "memory-hit")} & set(acts)


def test_token_cap_counts_the_planner_call(demo, kb, tmp_path):
    st, _, _ = run([plan(AR), BAD], [OK], demo, kb, tmp_path, token_cap_per_test=150)
    assert st.decision == "escalated" and "token cap" in st.reason and len(st.proposals) == 1


def test_s3_records_exception_as_error(demo, kb, tmp_path):
    st, _, sup = run([], [OK], demo, kb, tmp_path)
    assert st.decision == "error" and "IndexError" in st.reason
    assert metrics.summarize(metrics.load(sup.state_file))["errors"] == 1
