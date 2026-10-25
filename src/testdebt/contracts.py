"""Structured contracts passed between pipeline stages (and, in Phase 2, between agents).

Every stage reads and writes these dataclasses only; RunState is the per-test state record that is
appended to runs/<run>/state.jsonl, so a run can be audited and resumed.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

Decision = Literal["accepted", "rejected", "escalated", "skipped", "error"]


@dataclass(frozen=True)
class TestRef:
    project: str          # e.g. "commons-cli"
    module_dir: str       # directory holding the pom.xml that builds this test (gson -> data/projects/gson/gson)
    file: str             # path to the .java test file
    class_name: str       # simple class name, used for -Dtest=
    method: str           # test method name

    @property
    def id(self) -> str:
        return f"{self.project}:{self.class_name}#{self.method}"


@dataclass
class DebtFinding:
    test: TestRef
    smells: list[str]                 # smell types targeted in this run
    detector: str = "rules"           # "rules" (our approximation) | "tsdetect" | "jnose"
    all_smells: list[str] = field(default_factory=list)  # everything the detector saw


@dataclass
class RefactorProposal:
    test: TestRef
    original: str
    refactored: str
    attempt: int
    tokens: int = 0
    reasoning_tokens: int = 0
    latency_s: float = 0.0
    cached: bool = False


@dataclass
class VerificationReport:
    sane: bool                        # cheap static checks (brackets, @Test, name, no assertion loss)
    compiled: bool | None = None      # None = not checked
    passed: bool | None = None
    killset_preserved: bool | None = None
    mutants_killed_before: int | None = None
    mutants_killed_after: int | None = None
    smells_after: list[str] = field(default_factory=list)
    assertions_before: int = 0
    assertions_after: int = 0
    problem: str = ""                 # short error text fed back to the LLM on retry

    @property
    def ok(self) -> bool:
        gates = [self.sane, self.compiled, self.passed, self.killset_preserved]
        return all(g is not False for g in gates) and self.sane


@dataclass
class RunState:
    """One record per test per system per seed: the unit of every metric."""
    run_id: str
    system: str                       # "single" | "b0replay" | "b0" | "b1" | "s3" (b2 in Phase 2)
    seed: int
    test: TestRef
    finding: DebtFinding
    proposals: list[RefactorProposal] = field(default_factory=list)
    reports: list[VerificationReport] = field(default_factory=list)
    decision: Decision = "skipped"
    reason: str = ""
    wall_time_s: float = 0.0
    trace: list[dict] = field(default_factory=list)   # S3 only: one entry per agent step (who, action, note)

    @property
    def final(self) -> VerificationReport | None:
        return self.reports[-1] if self.reports else None

    def to_json(self) -> dict:
        d = asdict(self)
        d["test_id"] = self.test.id
        d["retries"] = max(0, len(self.proposals) - 1)
        d["tokens"] = sum(p.tokens for p in self.proposals)
        return d
