import json

from testdebt.eval import metrics
from testdebt.team.gulsher import experiments as ex


def _state(decision, killset, left):
    return {"test_id": "", "test": {"project": "p"}, "decision": decision, "reason": "", "retries": 0, "tokens": 100, "wall_time_s": 1.0,
            "finding": {"smells": ["A"]}, "proposals": [{}],
            "reports": [{"sane": True, "compiled": True, "passed": True, "killset_preserved": killset,
                         "smells_after": left, "smells_after_jnose": [], "timings": {"pit": 2.0}}]}


def _write_run(rid, outcomes):
    d = __import__("pathlib").Path("runs", rid)
    (d / "trajectories").mkdir(parents=True)
    recs = [dict(_state(*o), test_id=f"p:C#m{i}") for i, o in enumerate(outcomes)]
    (d / "state.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs))
    (d / "report.json").write_text(json.dumps(metrics.report(recs)))
    (d / "trajectories" / "x.jsonl").write_text(json.dumps({"event": "llm_call", "latency_s": 2}) + "\n")


def test_summaries_from_saved_runs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    good, lost, rej = ("accepted", True, []), ("accepted", False, []), ("rejected", None, ["A"])
    for s in (1, 2, 3):
        _write_run(f"E3_s3_s{s}", [good] * 8 + [rej] * 2)
        _write_run(f"E2_b1_s{s}", [good] * 4 + [rej] * 6)
        _write_run(f"E2_b0_s{s}", [lost] * 5 + [good] * 5)
    summ = ex.summarize("E3", dev=False)
    assert summ["s3"]["accepted_rate"] == (80.0, 0.0) and (tmp_path / "results/E3/table.tex").exists()
    assert (tmp_path / "results/E3/runs/E3_s3_s1/report.json").exists()
    e4 = ex.summarize_e4()
    g6 = e4["paired_tests"]["G6: s3 vs b1 (accepted and safe)"]
    assert g6["pairs"] == 10 and g6["mcnemar"]["only_a"] == 4 and "p_holm" in g6
    assert {r["system"]: r["lost"] for r in e4["g1_killset_loss"]}["E2/b0"] == 5
    e6 = ex.summarize_e6()
    assert e6["E3/s3"]["llm_calls_per_test"] == (0.1, 0.0) and e6["E3/s3"]["pit_s_per_test"] == (2.0, 0.0)


def test_figures_from_summaries(tmp_path):
    from testdebt.team.hasan.figures import make_all
    s = {"accepted_safe_rate": [60.0, 2.0], "accepted_losing_mutants_rate": [3.0, 1.0], "tokens_per_test": [4000, 90]}
    for e, names in (("E1", ["b1"]), ("E3", ["s3"]), ("E5", ["s3-G1"])):
        (tmp_path / e).mkdir()
        (tmp_path / e / "summary.json").write_text(json.dumps({n: s for n in names}))
    assert make_all(tmp_path) == ["fig_systems.pdf", "fig_ablation.pdf", "fig_cost.pdf"]   # no failures file yet
