"""G1 kill-set gate: a refactoring may not weaken the test.

  K(original) must be a subset of the union of K(t) over the refactored tests t   (PIT full mutation matrix)

Both kill matrices are cached by the SHA-256 of the test class source, so
  * the baseline matrix is computed once per class, from the unmodified file (the Phase 1 bug cannot come back), and
  * an identical refactored class (same output across systems, seeds or retries) runs PIT only once.
enforce=False (--killset-gate off, the -G1 ablation): PIT still measures, so E4 can report the loss, but a loss no
longer rejects the attempt or triggers a retry.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ...contracts import TestRef
from ...tools import pit as pitmod


class KillsetGate:
    def __init__(self, pit: pitmod.PitRunner, cache_dir: str | Path = "runs/pit_cache", enforce: bool = True):
        self.pit, self.cache_dir, self.enforce = pit, Path(cache_dir), enforce

    def _matrix(self, test: TestRef, src: str) -> dict[str, set]:
        """Kill matrix of the class whose source is `src`; that source must be what is on disk right now."""
        sha = hashlib.sha256(src.encode()).hexdigest()[:16]
        f = self.cache_dir / f"{test.project}__{test.class_name}__{sha}.json"
        if f.exists():
            return {k: {tuple(x) for x in v} for k, v in json.loads(f.read_text()).items()}
        pkg = pitmod.package_of(src)
        fqn, targets = (f"{pkg}.{test.class_name}", f"{pkg}.*") if pkg else (test.class_name, "*")
        mat = self.pit.run(test.module_dir, fqn, targets, test.project)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({k: sorted(v) for k, v in mat.items()}))
        return mat

    def before(self, test: TestRef, original_src: str) -> set:
        """K(original method), from the UNMODIFIED class: call before the patch is written."""
        return pitmod.kill_set(self._matrix(test, original_src), {test.method})

    def check(self, test: TestRef, patched_src: str, new_tests: set[str], before: set) -> dict:
        """Call while the patched class is on disk. -> compare() result plus 'problem' text for the retry prompt."""
        cmp = pitmod.compare(before, pitmod.kill_set(self._matrix(test, patched_src), new_tests))
        cmp["problem"] = "" if cmp["preserved"] else (
            f"kill-set lost: {cmp['lost']} mutant(s) killed by the original test are no longer killed. "
            "Keep an assertion that detects each of these changes (class, method, line, mutator): "
            + "; ".join(f"{c}.{m} line {l} {mu.rsplit('.', 1)[-1]}" for c, m, l, mu, _ in cmp["lost_mutants"][:5]))
        return cmp
