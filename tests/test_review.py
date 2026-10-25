import json

from testdebt.eval import metrics
from testdebt.review import decisions, review, show, summary


def _run(tmp_path):
    def rec(i, decision):
        return {"test_id": f"p:C#m{i}", "test": {"project": "p"}, "decision": decision, "reason": "failed at compile",
                "tokens": 300, "retries": 2, "wall_time_s": 1.0, "finding": {"smells": ["A"]},
                "proposals": [{"original": "@Test void m() { a(); }", "refactored": "@Test void m() { b(); }"}],
                "reports": [{"sane": True, "compiled": True, "passed": True, "killset_preserved": False,
                             "mutants_killed_before": 4, "mutants_killed_after": 3, "smells_after": [],
                             "problem": "kill-set lost: 1 mutant"}]}
    (tmp_path / "state.jsonl").write_text("".join(json.dumps(rec(i, d)) + "\n" for i, d in
                                                  enumerate(["escalated", "accepted", "escalated", "escalated"])))
    return tmp_path


def test_review_records_decisions_without_touching_metrics(tmp_path):
    run = _run(tmp_path)
    before = metrics.report(metrics.load(run / "state.jsonl"))
    answers = iter(["x", "a", "looks right", "n", "ask Hasan", "q"])     # invalid key is asked again
    out = []
    assert review(run, ask=lambda _: next(answers), say=out.append, who="saqib") == 2
    assert "3 escalated test(s) waiting" in out[0] and "-@Test void m() { a(); }" in out[1]
    assert "kill-set: 4 -> 3" in out[1]
    d = decisions(run)
    assert d["p:C#m0"]["decision"] == "accepted" and "p:C#m2" not in d          # a note is not a decision
    assert summary(run) == {"escalated": 3, "reviewed": 1, "human_accepted": 1, "human_rejected": 0, "waiting": 2}
    assert metrics.report(metrics.load(run / "state.jsonl")) == before
    answers = iter(["r", ""])                                                   # next session: only undecided ones
    out.clear()
    review(run, ask=lambda _: next(answers, "q"), say=out.append, who="saqib")
    assert "2 escalated test(s) waiting (1 already decided)" in out[0] and decisions(run)["p:C#m2"]["decision"] == "rejected"


def test_show_lists_the_reason():
    r = {"test_id": "p:C#m", "proposals": [], "reports": [], "tokens": 0, "reason": "token cap",
         "finding": {"smells": ["A"]}}
    assert "why escalated: token cap" in show(r)
