from testdebt.team.hasan.stats import bootstrap_ci, cohen_kappa, holm, mcnemar_exact, mean_sd, wilcoxon


def test_mean_sd():
    assert mean_sd([1, 2, 3]) == (2.0, 1.0) and mean_sd([5]) == (5.0, 0.0) and mean_sd([]) == (None, None)


def test_mcnemar_exact_matches_the_binomial_tail():
    a = [True] * 10 + [False] * 2 + [True] * 5
    b = [False] * 10 + [True] * 2 + [True] * 5
    r = mcnemar_exact(a, b)
    assert (r["only_a"], r["only_b"]) == (10, 2) and abs(r["p"] - 158 / 4096) < 1e-4


def test_wilcoxon_normal_approximation():
    r = wilcoxon([i + 1 for i in range(10)], [0] * 10)        # 10 positive, distinct differences
    assert r["w_plus"] == 55 and abs(r["p"] - 0.0059) < 0.0005
    assert wilcoxon([1, 2], [1, 2])["p"] == 1.0


def test_bootstrap_ci_contains_the_mean():
    lo, hi = bootstrap_ci([1.0, 2.0, 3.0, 4.0] * 10, n=2000)
    assert lo < 2.5 < hi


def test_holm_and_kappa():
    assert holm([0.01, 0.04, 0.03]) == [0.03, 0.06, 0.06]
    assert cohen_kappa([1, 1, 0, 0], [1, 0, 0, 0]) == 0.5 and cohen_kappa([1, 0], [1, 0]) == 1.0
