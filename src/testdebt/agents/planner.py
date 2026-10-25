"""Planner agent: which smells to target in this attempt, and with which prompt (KB rule / plain)."""
from __future__ import annotations

from ..prompts import KnowledgeBase, plain_prompt, utr_prompt


class PlannerAgent:
    STRATEGIES = ("kb", "plain")

    def __init__(self, kb: KnowledgeBase):
        self.kb = kb

    def prompt(self, strategy: str, original: str, context: str, smells: list[str]) -> str:
        if strategy == "kb" and self.kb.available():
            return utr_prompt(self.kb, original, context, smells)
        return plain_prompt(original, context, smells)

    def switch(self, strategy: str) -> str:
        return "plain" if strategy == "kb" else "kb"
