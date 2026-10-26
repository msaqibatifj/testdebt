"""Detection agent: which targeted smells are really present before any LLM call (G2: one or two detectors)."""
from __future__ import annotations

from ..contracts import DebtFinding, TestRef
from ..team.hasan import consensus
from ..tools.tsdetect import focal_class_file
from ..verify import Verifier


class DetectionAgent:
    def __init__(self, verifier: Verifier, detector: str = "tsdetect"):
        self.verifier, self.detector = verifier, detector

    def run(self, test: TestRef, src: str, finding: DebtFinding) -> tuple[list[str], dict]:
        """-> (targets, evidence: what each detector saw on the original method)."""
        tsd, jn = self.verifier.tsdetect, self.verifier.jnose
        prod = focal_class_file(test.file)
        ts = (tsd.detect_source(src, test.class_name, {test.method}, prod) if tsd and tsd.available()
              else set(finding.smells))          # no jar: the labels of [1] came from tsDetect
        jns = (jn.detect_source(src, test.class_name, {test.method}, prod)
               if self.detector != "tsdetect" and jn and jn.available() else None)
        targets, note = consensus.targets(finding.smells, ts, jns, self.detector)
        return targets, {"tsdetect": sorted(ts), "jnose": None if jns is None else sorted(jns), "rule": note}
