"""Planner agent: which prompt strategy to use, and (strategy 'planner') an LLM-written JSON plan per test.

Plan schema (validated; anything else falls back to the KB rule, strategy 'kb'):
  {"smells": {"<targeted smell>": "<what to change for it, following its DSL rule>", ...},
   "split_groups": ["<concern each new test checks>", ...],      # [] when the test is not split
   "shared_state": ["<setup every split test still needs>", ...]} # kept in one helper, never dropped
"""
from __future__ import annotations

import json
import re

from ..prompts import KnowledgeBase, plain_prompt, utr_prompt

PLANNER_SYSTEM = "You are a java testing expert who plans test refactorings. You answer with JSON only."

PLAN_TEMPLATE = """Plan how to remove these test smells from the JUnit test below, without changing what it checks.

Smells: {smells}
Refactoring rule for each smell:
{rules}

Test Code:
{test_code}
Context of the Test Code:
{context}
{memory}{failure}
Return only a JSON object with exactly these keys:
{{"smells": {{"<smell>": "<what to change for this smell>"}}, "split_groups": ["<concern of each new test, if the test is split>"], "shared_state": ["<setup or fixture state every split test still needs>"]}}
The "smells" object must have one entry for each smell listed above."""

# planner -> KB rule -> plain prompt -> re-plan: the order the Supervisor switches in
NEXT = {"planner": "kb", "kb": "plain", "plain": "planner"}


def parse_plan(reply: str, targets: list[str]) -> dict | None:
    """The plan if it matches the schema, else None (caller falls back to the KB rule)."""
    m = re.search(r"\{.*\}", reply, re.S)
    try:
        p = json.loads(m.group(0)) if m else None
    except json.JSONDecodeError:
        return None
    ok = (isinstance(p, dict) and isinstance(p.get("smells"), dict) and set(p["smells"]) == set(targets)
          and all(isinstance(v, str) and v.strip() for v in p["smells"].values())
          and all(isinstance(p.get(k, []), list) and all(isinstance(x, str) for x in p.get(k, []))
                  for k in ("split_groups", "shared_state")))
    return {"smells": p["smells"], "split_groups": p.get("split_groups", []),
            "shared_state": p.get("shared_state", [])} if ok else None


def render_plan(plan: dict, smells: list[str]) -> str:
    lines = ["Refactoring plan for this test (follow it):"]
    lines += [f"- {s}: {how}" for s, how in plan["smells"].items() if s in smells]   # targets may have narrowed
    if plan["split_groups"]:
        lines.append("- Split into one test per concern: " + "; ".join(plan["split_groups"]))
    if plan["shared_state"]:
        lines.append("- Every split test must still set up: " + "; ".join(plan["shared_state"])
                     + " (keep it in one private helper or the existing setUp; do not drop it)")
    return "\n".join(lines)


class PlannerAgent:
    STRATEGIES = tuple(NEXT)

    def __init__(self, kb: KnowledgeBase, llm=None, cfg=None):
        self.kb, self.llm, self.cfg = kb, llm, cfg

    def plan_prompt(self, original: str, context: str, smells: list[str], failed_before: dict[str, list[str]],
                    failure: tuple[str, str] | None) -> str:
        rules = "\n".join(f"{s}:\n{self.kb.rule(s) or '(no rule)'}" for s in smells)
        memory = "".join(f"Approaches that already failed for {s} in this project: " + " | ".join(v) + "\n"
                         for s, v in failed_before.items() if v)
        fail = f"The last attempt failed at {failure[0]}: {failure[1][:500]}\n" if failure else ""
        return PLAN_TEMPLATE.format(smells=smells, rules=rules, test_code=original, context=context,
                                    memory=memory, failure=fail)

    def plan(self, prompt: str, targets: list[str], tag: str) -> tuple[dict | None, dict]:
        """One LLM call -> (validated plan or None, raw LLM result for the trace and token count)."""
        r = self.llm.chat([{"role": "system", "content": PLANNER_SYSTEM}, {"role": "user", "content": prompt}],
                          temperature=self.cfg.temperature, max_tokens=self.cfg.max_tokens_per_call, tag=tag,
                          seed=self.cfg.seed)
        return parse_plan(r["text"], targets), r

    def prompt(self, strategy: str, original: str, context: str, smells: list[str], plan: dict | None = None) -> str:
        if strategy == "plain" or not self.kb.available():
            base = plain_prompt(original, context, smells)
        else:
            base = utr_prompt(self.kb, original, context, smells)
        return base + "\n\n" + render_plan(plan, smells) if strategy == "planner" and plan else base

    def switch(self, strategy: str) -> str:
        return NEXT[strategy]
