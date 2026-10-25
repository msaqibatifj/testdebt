import json

from test_agents_s3 import FAIL, OK, run
from test_end_to_end_mock import BAD, kb  # noqa: F401  (pytest fixture)
from test_verify import GOOD
from testdebt.trace import Trace, file_name, timeline


def events(path):
    return [json.loads(l) for l in path.read_text().splitlines()]


def test_long_text_is_cut_and_kept_whole_in_a_blob(tmp_path):
    tr = Trace(tmp_path, "p:C#m")
    e = tr.event("refactor", "llm_call", input="x" * 3000, output="short")
    assert tr.path.name == file_name("p:C#m") == "p_C_m.jsonl"
    assert len(e["input"]) < 2200 and e["output"] == "short" and e["step"] == 1
    blob = tmp_path / "blobs" / e["input"].split("blobs/")[1].rstrip("]")
    assert blob.read_text() == "x" * 3000
    Trace(tmp_path, "p:C#m")                       # a resumed test starts a fresh trajectory
    assert tr.path.read_text() == ""


def test_s3_trajectory_records_llm_calls_tool_output_and_decisions(demo, kb, tmp_path):  # noqa: F811
    st, _, sup = run([BAD, f"```java\n{GOOD}\n```"], [OK, FAIL], demo, kb, tmp_path)
    ev = events(sup.tr.path)
    kinds = [(e["agent"], e["event"]) for e in ev]
    assert kinds[0] == ("detection", "tool_call") and kinds[-1] == ("supervisor", "state_change")
    assert kinds.count(("refactor", "llm_call")) == 2 and kinds.count(("verifier", "tool_call")) == 2
    llm = next(e for e in ev if e["event"] == "llm_call")
    assert llm["tokens"] == 100 and llm["cached"] is False and llm["input"] and llm["output"] == BAD
    verify = [e for e in ev if e.get("tool") == "verify"]
    assert json.loads(verify[0]["output"])["sane"] is False and "latency_s" in verify[0]
    assert ev[-1]["state_after"]["decision"] == st.decision
    assert [e["step"] for e in ev] == list(range(1, len(ev) + 1))
    assert "llm_call" in timeline(sup.run_dir, st.test.id)


def test_error_is_in_the_trajectory(demo, kb, tmp_path):  # noqa: F811
    st, _, sup = run([], [OK], demo, kb, tmp_path)
    ev = events(sup.tr.path)
    assert ("supervisor", "error") in [(e["agent"], e["event"]) for e in ev] and "IndexError" in ev[-2]["output"]
