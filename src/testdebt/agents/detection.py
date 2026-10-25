"""Detection agent: which targeted smells are really present before any LLM call."""
from __future__ import annotations

from ..contracts import DebtFinding, TestRef
from ..verify import Verifier


class DetectionAgent:
    def __init__(self, verifier: Verifier):
        self.verifier = verifier

    def run(self, test: TestRef, src: str, finding: DebtFinding) -> list[str]:
        tsd = self.verifier.tsdetect
        if tsd and tsd.available():
            from ..tools.tsdetect import focal_class_file
            seen = tsd.detect_source(src, test.class_name, {test.method}, focal_class_file(test.file))
            present = [s for s in finding.smells if s in seen]
            return present or list(finding.smells)
        return list(finding.smells)
