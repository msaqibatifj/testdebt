from testdebt.eval.metrics import summarize, wilson


def rec(decision, smells, after, after_j=None, ks=None, tokens=100, retries=0):
    rep = {"sane": True, "compiled": True, "passed": True, "smells_after": after,
           "smells_after_jnose": after_j, "killset_preserved": ks, "mutants_killed_before": 3}
    return {"decision": decision, "finding": {"smells": smells}, "reports": [rep], "tokens": tokens,
            "retries": retries, "wall_time_s": 1.0, "test": {"project": "p"}}


def test_rule_i_vs_rule_ii_strict_and_safe():
    recs = [rec("accepted", ["A", "B"], [], after_j=[], ks=True),          # A gone by both
            rec("accepted", ["A"], [], after_j=["A"], ks=True),                 # rule i: gone; rule ii: JNose still sees it
            rec("rejected", ["A"], ["A"], after_j=["A"], ks=False)]
    s = summarize(recs)
    assert s["smell_reduction_tsdetect"] == 75.0           # 3 of 4 removed by tsDetect
    assert s["smell_reduction_strict"] == 50.0             # 2 of 4 removed by both
    assert s["accepted_rate"] == 66.7 and s["smell_reduction_accepted"] == 100.0
    assert s["accepted_safe"] == 1 and s["accepted_safe_rate"] == 33.3   # only the first: kill-set kept, smells gone
    assert s["accepted_losing_mutants"] == 0 and s["tokens_per_test"] == 100


def test_wilson_interval():
    lo, hi = wilson(5, 10)
    assert (lo, hi) == (23.7, 76.3) and wilson(0, 0) is None
