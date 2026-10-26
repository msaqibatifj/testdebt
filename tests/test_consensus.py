from testdebt.contracts import VerificationReport
from testdebt.team.hasan.consensus import left, targets


def test_targets_by_detector_mode_with_fallbacks():
    labelled, ts, jn = ["A", "B", "C"], {"A", "B"}, {"B", "C"}
    assert targets(labelled, ts, jn, "consensus")[0] == ["B"]
    assert targets(labelled, ts, jn, "union")[0] == ["A", "B", "C"]
    assert targets(labelled, ts, jn, "tsdetect")[0] == ["A", "B"]
    assert targets(labelled, ts, None, "consensus") == (["A", "B"], "no consensus smell -> tsDetect")
    assert targets(labelled, {"A"}, {"C"}, "consensus")[0] == ["A"]          # no agreement -> tsDetect's
    assert targets(labelled, set(), set(), "consensus")[0] == labelled      # nothing confirmed -> labels


def test_gone_is_strict_unless_tsdetect_only():
    rep = VerificationReport(sane=True, smells_after=["A"], smells_after_jnose=["B"])
    assert left(["A", "B", "C"], rep, "consensus") == ["A", "B"]
    assert left(["A", "B", "C"], rep, "tsdetect") == ["A"]
