"""G2 consensus detection: "smell present" and "smell removed" no longer rest on one detector.

  detector="tsdetect"   (-G2 ablation)  targets and the "gone" check use tsDetect alone, as in [1]
  detector="consensus"  target a smell only if BOTH detectors report it; it counts as gone only if BOTH say gone
  detector="union"      target a smell if EITHER detector reports it; gone only if both say gone
Targets are always a subset of the smells [1] labelled for the test, so every system is scored on the same smells.
"""
from __future__ import annotations

from ...contracts import VerificationReport

DETECTORS = ("tsdetect", "consensus", "union")


def targets(labelled: list[str], ts: set[str], jn: set[str] | None, detector: str) -> tuple[list[str], str]:
    """-> (smells to target, note for the trace). Falls back step by step so a test is never left with none."""
    if detector != "tsdetect" and jn is not None:
        seen = ts & jn if detector == "consensus" else ts | jn
        hit = [s for s in labelled if s in seen]
        if hit:
            return hit, f"{detector} of tsDetect and JNose"
    hit = [s for s in labelled if s in ts]
    if hit:
        return hit, "tsDetect" if detector == "tsdetect" else f"no {detector} smell -> tsDetect"
    return list(labelled), "labels of [1] (no detector confirmed a labelled smell)"


def left(targets_: list[str], rep: VerificationReport, detector: str) -> list[str]:
    """Targeted smells still present after the refactoring (strict for consensus/union: either detector)."""
    after = set(rep.smells_after)
    if detector != "tsdetect" and rep.smells_after_jnose is not None:
        after |= set(rep.smells_after_jnose)
    return sorted(set(targets_) & after)
