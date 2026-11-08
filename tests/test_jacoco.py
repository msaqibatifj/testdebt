from testdebt.eval.coverage import summarize
from testdebt.tools.jacoco import compare, parse_report

XML = """<?xml version="1.0"?><report name="r">
<package name="org/x"><class name="org/x/A" sourcefilename="A.java"/>
<sourcefile name="A.java"><line nr="3" mi="0" ci="2" mb="0" cb="0"/><line nr="4" mi="1" ci="0" mb="0" cb="0"/>
<line nr="7" mi="0" ci="1" mb="0" cb="0"/></sourcefile></package></report>"""


def test_parse_report_keeps_only_covered_lines(tmp_path):
    f = tmp_path / "r.xml"
    f.write_text(XML)
    assert parse_report(f) == {("org/x/A.java", 3), ("org/x/A.java", 7)}


def test_compare_lost_and_gained():
    c = compare({("a", 1), ("a", 2)}, {("a", 2), ("a", 3)})
    assert (c["lost"], c["gained"], c["preserved"]) == (1, 1, False)
    assert compare({("a", 1)}, {("a", 1), ("a", 2)})["preserved"]


def test_summary_leaves_empty_and_unmeasured_out_of_the_rate():
    rows = [{"project": "p", "status": "preserved", "lost": 0}, {"project": "p", "status": "lost", "lost": 4},
            {"project": "p", "status": "empty", "lost": 0}, {"project": "p", "status": "unmeasured"}]
    s = summarize(rows)
    assert (s["measured"], s["preserved"], s["preserved_rate"], s["empty"], s["unmeasured"]) == (2, 1, 50.0, 1, 1)
    assert s["lines_lost_mean_when_lost"] == 4.0
