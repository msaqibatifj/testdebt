"""Supervisor memory across tests: planned approaches that failed for a smell in a project, read by the planner.

Kept in runs/<run>/memory.json, so it survives a resumed run and never leaks between runs (seeds, ablations).
Within one test the Supervisor keeps its own memory (failed proposal hashes, (strategy, stage) pairs).
"""
from __future__ import annotations

import json
from pathlib import Path


class Memory:
    def __init__(self, path: str | Path, enabled: bool = True, keep: int = 3):
        self.path, self.enabled, self.keep = Path(path), enabled, keep
        self.data: dict = json.loads(self.path.read_text(encoding="utf-8")) if enabled and self.path.exists() else {}

    def failed(self, project: str, smells: list[str]) -> dict[str, list[str]]:
        """Most recent failed approaches per smell (empty when memory is off)."""
        return {s: self.data.get(project, {}).get(s, [])[-self.keep:] for s in smells} if self.enabled else {}

    def add(self, project: str, smell: str, approach: str, stage: str, problem: str) -> None:
        if not self.enabled or not approach:
            return
        self.data.setdefault(project, {}).setdefault(smell, []).append(
            f"{approach[:200]} -> failed at {stage}: {problem[:120]}")
        self.path.write_text(json.dumps(self.data, indent=1, ensure_ascii=False), encoding="utf-8")
