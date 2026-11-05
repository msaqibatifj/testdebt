from test_verify import GOOD, DEMO_TEST, FakePit, ref
from conftest import FakeMaven
from testdebt.java_utils import find_method
from testdebt.verify import Verifier


class LosesOne(FakePit):
    """The refactored test kills one mutant fewer than the original."""
    def run(self, *a, **k):
        mat = super().run(*a, **k)
        return {n: (s if n == "testTotals" and len(self.seen) == 1 else set(sorted(s)[1:])) for n, s in mat.items()}


def verify(demo, tmp_path, pit, **kw):
    f = demo / DEMO_TEST
    v = Verifier(FakeMaven(), pit=pit(f), pit_cache=tmp_path / "pit", **kw)
    return v, v.verify(ref(demo), find_method(f.read_text(), "testTotals")["text"], GOOD, [], ["AssertionRoulette"])


def test_lost_mutant_rejects_and_names_the_mutant(demo, tmp_path):
    _, rep = verify(demo, tmp_path, LosesOne)
    assert rep.killset_preserved is False and not rep.ok and len(rep.lost_mutants) == 1
    assert "kill-set lost: 1 mutant" in rep.problem and "ShoppingCart.total line 0" in rep.problem
    assert set(rep.timings) == {"smells", "compile_run", "pit"}


def test_gate_off_measures_but_does_not_reject(demo, tmp_path):
    _, rep = verify(demo, tmp_path, LosesOne, killset_enforce=False)
    assert rep.killset_preserved is False and rep.ok and rep.problem == "" and not rep.killset_enforced


def test_identical_class_runs_pit_once(demo, tmp_path):
    v, _ = verify(demo, tmp_path, FakePit)
    f = demo / DEMO_TEST
    v.verify(ref(demo), find_method(f.read_text(), "testTotals")["text"], GOOD, [], ["AssertionRoulette"])
    assert len(v.gate.pit.seen) == 2           # baseline + one refactored class; the second verify hit both caches
