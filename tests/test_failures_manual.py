import csv
import json

from testdebt.team.hasan.failures import classify
from testdebt.team.hasan.manual import sample, score


def rec(decision="rejected", reason="", **rep):
    return {"decision": decision, "reason": reason, "test_id": "p:C#m", "finding": {"smells": ["A"]},
            "proposals": [{"original": "o", "refactored": rep.pop("block", "@Test void t(){}")}],
            "reports": [{"sane": True, **rep}]}


def test_failure_categories():
    assert classify(rec("error", "RuntimeError: HTTP 401"))[0] == "infrastructure error"
    assert classify(rec(sane=False, problem="assertions dropped: 3 -> 1"))[0] == "assertion dropped or empty test"
    assert classify(rec(compiled=False, problem="cannot find symbol: method assertDoesNotThrow"))[0] == \
        "compile: API not in the project"
    assert classify(rec(compiled=False, problem="cannot find symbol: variable cart"))[0] == \
        "compile: missing symbol or import"
    assert classify(rec(compiled=True, passed=False, block="@Before public void setUp(){}"))[0] == \
        "fixture clobbered by extracted setup"
    assert classify(rec(compiled=True, passed=True, killset_preserved=False))[0] == "weakened test: kill-set loss"
    assert classify(rec("escalated", "failed at compile | token cap reached", compiled=False))[0] == "budget exhausted"


def test_manual_sample_and_score(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    (run / "state.jsonl").write_text("\n".join(json.dumps(rec("accepted", smells_after=[], smells_after_jnose=["A"])
                                                          | {"test_id": f"p:C#m{i}"}) for i in range(4)) + "\n")
    sheet = sample(str(run), 3, 1, str(tmp_path / "out"))
    rows = list(csv.DictReader(open(sheet)))
    assert len(rows) == 3 and rows[0]["tsdetect_after"] == "0" and rows[0]["jnose_after"] == "1"
    for i, r in enumerate(rows):                      # both say present before; disagree on one 'after'
        r.update(present_before_hasan="1", present_before_gulsher="1", present_after_hasan="0",
                 present_after_gulsher="1" if i == 0 else "0", adjudicated_after="0" if i == 0 else "")
    with open(sheet, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    s = score(str(sheet))
    assert s["smell_reduction_manual"] == 100.0 and s["kappa_tsdetect_vs_human_after"] == 1.0
