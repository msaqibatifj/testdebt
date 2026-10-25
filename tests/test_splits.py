from collections import Counter

from testdebt.data.build_eval_set import stratified
from testdebt.data.splits import load, make


def test_committed_splits_are_disjoint_and_cover_the_eval_set():
    dev, test, rest = load("dev"), load("test"), load("rest")
    assert (len(dev), len(test), len(rest)) == (80, 150, 254)
    assert len(set(dev) | set(test) | set(rest)) == 484
    assert sorted(load("all")) == sorted(dev + test + rest)


def _rows():
    return [{"project": p, "class_name": f"C{i % 7}", "method": f"m{i}", "multi_smell": i % 3 == 0}
            for p, n in [("a", 50), ("b", 31), ("c", 19)] for i in range(n)]


def test_stratified_returns_exactly_n_and_is_seeded():
    rows = _rows()
    for n in (7, 33, 80):
        assert len(stratified(rows, n, 1)) == n
    assert stratified(rows, 33, 1) == stratified(rows, 33, 1)
    assert stratified(rows, 33, 1) != stratified(rows, 33, 2)
    got = Counter(r["project"] for r in stratified(rows, 50, 1))   # strata are project x multi, so +-1 per project
    assert all(abs(got[p] - want) <= 1 for p, want in {"a": 25, "b": 15.5, "c": 9.5}.items())


def test_make_splits_are_disjoint():
    s = make(_rows(), 1)
    ids = [r["project"] + r["method"] for part in s.values() for r in part]
    assert len(ids) == len(set(ids)) == 100
