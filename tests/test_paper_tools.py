"""Paper tooling: gap-resolution table from results/, reference checker, case export."""
import json

from testdebt.team.hasan import check_refs, gap_table
from testdebt.team.hasan.failures import export_case


def test_gap_table_from_summaries_and_readme_block(tmp_path):
    for exp, body in (("E2", {"b0": {"accepted_losing_mutants_rate": [9.0, 1.0], "smell_reduction_strict": [70.0, 2.0],
                                     "accepted_safe_rate": [55.0, 3.0]}}),
                      ("E3", {"s3": {"accepted_losing_mutants_rate": [0.0, 0.0], "smell_reduction_strict": [80.5, 1.5],
                                     "accepted_safe_rate": [72.0, 2.0]}})):
        (tmp_path / exp).mkdir()
        (tmp_path / exp / "summary.json").write_text(json.dumps(body))
    (tmp_path / "gap_verdicts.json").write_text(json.dumps({"G1": "Fully"}))
    rs = gap_table.rows(tmp_path)
    assert rs[0][3] == "9 ± 1 (b0, reproduced)" and rs[0][4] == "0" and rs[0][5] == "Fully"
    assert "reported in [1]" in rs[1][3] and rs[2][5] == "TBD"
    md = gap_table.markdown(rs)
    readme = "# X\n<!-- gap-table -->\nold\n<!-- /gap-table -->\nrest\n"
    assert gap_table.replace_block(readme, md) == f"# X\n<!-- gap-table -->\n{md}<!-- /gap-table -->\nrest\n"
    assert "$\\pm$" in gap_table.latex(rs) and "\\%" in gap_table.latex(rs)


def _bib(n, extra=""):
    entries = [f"@article{{r{i},\n  title = {{T{i}}},\n  doi = {{10.1/{i}}},\n}}" for i in range(n)]
    return "\n\n".join(entries) + extra


def test_refs_ok_and_problems():
    tex = "\\cite{" + ",".join(f"r{i}" for i in range(25)) + "}"
    assert check_refs.check(_bib(25), [tex], resolve=lambda d: True) == []
    bad = _bib(24, "\n\n@misc{arx,\n  title = {A},\n}\n\n@misc{gone,\n  url = {https://arxiv.org/abs/1},\n}")
    tex = "\\citep[p.~3]{r0,missing} % \\cite{gone}\n" + "\\cite{" + ",".join(f"r{i}" for i in range(1, 24)) + ",arx}"
    probs = check_refs.check(bad, [tex], resolve=lambda d: d != "10.1/5")
    assert "arx: no doi and no url" in probs and "r5: doi 10.1/5 does not resolve" in probs
    assert "missing: cited but not in the .bib" in probs and "gone: in the .bib but never cited" in probs
    assert not any(p.startswith("26 references") for p in probs)


def test_export_case(tmp_path):
    run = tmp_path / "run"
    (run / "trajectories").mkdir(parents=True)
    rec = {"test_id": "p:C#m", "decision": "rejected", "reason": "failed", "tokens": 10, "finding": {"smells": ["A"]},
           "proposals": [{"refactored": "@Test void m(){}"}], "reports": [{"sane": True, "compiled": False,
                                                                           "problem": "cannot find symbol: x"}]}
    (run / "state.jsonl").write_text(json.dumps(rec) + "\n")
    (run / "trajectories" / "p_C_m.jsonl").write_text(json.dumps({"step": 1, "t": 0.1, "agent": "refactor",
                                                                  "event": "llm_call"}) + "\n")
    md = export_case(run, "p:C#m", tmp_path / "cases", "failure1").read_text()
    assert "compile: missing symbol or import" in md and "llm_call" in md and "@Test void m(){}" in md
    assert (tmp_path / "cases/failure1.jsonl").exists()
