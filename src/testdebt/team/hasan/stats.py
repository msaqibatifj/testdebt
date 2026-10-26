"""Statistics for the paper (pure Python; no scipy in requirements).

Paired comparisons use the same tests in every configuration:
  mcnemar_exact      accepted-and-safe (yes/no) of system A vs B on the same tests
  wilcoxon           tokens per test, A vs B (normal approximation with tie and continuity correction)
  bootstrap_ci       95% CI of the mean per-test difference (10,000 resamples over tests)
  holm               family-wise correction across the three gap hypotheses
  cohen_kappa        labeller vs labeller, detector vs adjudicated label (G2)
"""
from __future__ import annotations

import math
import random
from collections import Counter


def mean_sd(xs: list[float]) -> tuple[float | None, float | None]:
    """Mean and sample standard deviation (n-1); sd is 0 for one value."""
    xs = [x for x in xs if x is not None]
    if not xs:
        return None, None
    m = sum(xs) / len(xs)
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) if len(xs) > 1 else 0.0
    return round(m, 2), round(sd, 2)


def _phi(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def mcnemar_exact(a: list[bool], b: list[bool]) -> dict:
    """Two-sided exact McNemar on paired outcomes: binomial test on the discordant pairs."""
    only_a = sum(1 for x, y in zip(a, b) if x and not y)
    only_b = sum(1 for x, y in zip(a, b) if y and not x)
    n, k = only_a + only_b, min(only_a, only_b)
    p = min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1.0
    return {"only_a": only_a, "only_b": only_b, "p": round(p, 5)}


def wilcoxon(a: list[float], b: list[float]) -> dict:
    """Wilcoxon signed-rank test on paired values; zero differences dropped."""
    d = [x - y for x, y in zip(a, b) if x != y]
    n = len(d)
    if n == 0:
        return {"n": 0, "w_plus": 0.0, "p": 1.0}
    order = sorted(range(n), key=lambda i: abs(d[i]))
    ranks, i = [0.0] * n, 0
    while i < n:                                        # average ranks for ties
        j = i
        while j + 1 < n and abs(d[order[j + 1]]) == abs(d[order[i]]):
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    w_plus = sum(r for r, x in zip(ranks, d) if x > 0)
    mu = n * (n + 1) / 4
    ties = Counter(abs(x) for x in d)
    var = n * (n + 1) * (2 * n + 1) / 24 - sum(t ** 3 - t for t in ties.values()) / 48
    z = (abs(w_plus - mu) - 0.5) / math.sqrt(var) if var > 0 else 0.0
    return {"n": n, "w_plus": w_plus, "p": round(min(1.0, 2 * (1 - _phi(max(z, 0.0)))), 5)}


def bootstrap_ci(diffs: list[float], n: int = 10000, seed: int = 0, level: float = 0.95) -> list[float] | None:
    if not diffs:
        return None
    rng, k = random.Random(seed), len(diffs)
    means = sorted(sum(rng.choice(diffs) for _ in range(k)) / k for _ in range(n))
    lo, hi = means[int((1 - level) / 2 * n)], means[int((1 + level) / 2 * n) - 1]
    return [round(lo, 3), round(hi, 3)]


def holm(pvals: list[float]) -> list[float]:
    """Holm-Bonferroni adjusted p-values, in the input order."""
    m, out, running = len(pvals), [0.0] * len(pvals), 0.0
    for rank, i in enumerate(sorted(range(m), key=lambda i: pvals[i])):
        running = max(running, min(1.0, (m - rank) * pvals[i]))
        out[i] = round(running, 5)
    return out


def cohen_kappa(a: list, b: list) -> float | None:
    n = len(a)
    if not n:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / n ** 2
    return round((po - pe) / (1 - pe), 3) if pe < 1 else 1.0
