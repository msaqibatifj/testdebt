"""Refactor agent: one LLM call per attempt."""
from __future__ import annotations

from ..pipeline import Config
from ..prompts import SYSTEM


class RefactorAgent:
    def __init__(self, llm, cfg: Config):
        self.llm, self.cfg = llm, cfg

    def run(self, prompt: str, tag: str) -> tuple[str, dict]:
        r = self.llm.chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
                          temperature=self.cfg.temperature, max_tokens=self.cfg.max_tokens_per_call, tag=tag,
                          seed=self.cfg.seed)
        return r["text"], r
