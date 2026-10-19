"""Prompts and the UTRefactor knowledge base (smell definitions, DSL rules, checkpoints).

The knowledge base is READ AT RUNTIME from the cloned UTRefactor package (no licence is shown there, so we do
not copy its files into this repo). B0 uses UTRefactor's own single-prompt template (build_prompt_total in
refactoring/buildindex/code_repo_v5.py), reproduced here with the same fields and wording.
"""
from __future__ import annotations

import re
from pathlib import Path

from .java_utils import extract_test_methods
from .tools.tsdetect import SMELL_TO_UTR

SYSTEM = "You are a java testing expert, and now you need to refactor the test code which contains bad test code smells."

OUTPUT_RULES = (
    "Output format: return ONE ```java block containing only the refactored test method(s) plus any NEW helper "
    "methods or constants they need. Do not repeat the class declaration, fields, setUp methods or unchanged tests. "
    "Put any new import lines at the top of the block. Keep every @Test annotation; if you split a test, give each "
    "new test a distinct name that starts with the original name."
)

# UTRefactor's build_prompt_total, same fields and wording (only our output-format rules are appended).
UTR_TEMPLATE = """
    Based on the provided test context information, you are required to refactor the test code. Use a Chain-of-Thought approach to break down the problem, understand the intent of the test, recognize the code smells present in the test code, comprehend the refactoring rules and measures, and refactor the test code accordingly.

    Test Code:
    {test_code}
    Context of the Test Code:
    {context}
    The test has the following code smells:
    {smell_list}
    The explanation for each smell is:
    {smell_desc_list}
    The corresponding refactoring DSL to eliminate the bad smell is:
    {refactoring_dsl}

    During the refactoring process, it is necessary to ensure that all code smells are addressed. checkpoints:
    {checkpoints}

    Instructions**:
    1. **Understand the test intent**: Make sure you understand the design intent of the test.
    2. **Understand the code smells**: Make sure you understand the insight of the existing code smells.
    3. **Understand the corresponding refactoring DSL**: Make sure you understand the corresponding refactoring DSL and how the test code should be refactored.
    4. **Refactoring the test code**: For the above analysis, refactor the test and provide the refactored test code. Make sure not to miss any code smell.
    Provide only the complete refactored code, including the test and any additional variable and method definitions, strictly following the refactoring steps, without any other responses.
"""

PLAIN_TEMPLATE = """Refactor the JUnit test method below to remove these test smells: {smell_list}.
Keep the test's behaviour and every check it performs; do not delete assertions.

Test Code:
{test_code}
Context of the Test Code:
{context}
"""

RETRY_TEMPLATE = """Your previous refactoring was rejected by an automatic check.

Check that failed: {stage}
Details:
{problem}

Previous attempt:
```java
{previous}
```
Fix the problem and return the corrected refactoring. {rules}"""


class KnowledgeBase:
    """Lookup of UTRefactor's smell descriptions / DSL rules / checkpoints by smell id."""

    def __init__(self, utr_dir: str | Path | None):
        self.root = Path(utr_dir, "refactoring/prompt_generation") if utr_dir else None

    def available(self) -> bool:
        return bool(self.root and self.root.exists())

    def _read(self, folder: str, smell: str) -> str:
        if not self.available():
            return ""
        name = SMELL_TO_UTR.get(smell, smell)
        for cand in (name, "Print_Statement" if smell == "RedundantPrint" else name):
            f = self.root / folder / f"{cand}.txt"
            if f.exists():
                return f.read_text(encoding="utf-8", errors="replace").strip()
        return ""

    def description(self, smell: str) -> str:
        return self._read("smelltype", smell)

    def rule(self, smell: str) -> str:
        return self._read("refactor_rules", smell)

    def checkpoint(self, smell: str) -> str:
        return self._read("checkpoints", smell)


def build_context(class_src: str, class_name: str, max_chars: int = 4000) -> str:
    """Package, imports, fields, setUp/helpers of the test class with all other @Test methods removed."""
    for t in sorted(extract_test_methods(class_src), key=lambda t: -t["start"]):
        class_src = class_src[:t["start"]] + class_src[t["end"]:]
    class_src = re.sub(r"/\*.*?\*/", "", class_src, flags=re.S)       # drop licence/javadoc blocks
    class_src = re.sub(r"\n\s*\n+", "\n", class_src).strip()
    ctx = f"Test class: {class_name}\n{class_src}"
    return ctx if len(ctx) <= max_chars else ctx[:max_chars] + "\n// ... (truncated)"


def utr_prompt(kb: KnowledgeBase, test_code: str, context: str, smells: list[str]) -> str:
    utr_names = [SMELL_TO_UTR.get(s, s) for s in smells]
    return UTR_TEMPLATE.format(
        test_code=test_code, context=context, smell_list=utr_names,
        smell_desc_list=[kb.description(s) for s in smells],
        refactoring_dsl=[kb.rule(s) for s in smells],
        checkpoints=[kb.checkpoint(s) for s in smells],
    ) + "\n" + OUTPUT_RULES


def plain_prompt(test_code: str, context: str, smells: list[str]) -> str:
    return PLAIN_TEMPLATE.format(test_code=test_code, context=context, smell_list=", ".join(smells)) + "\n" + OUTPUT_RULES


def retry_prompt(base: str, stage: str, problem: str, previous: str) -> str:
    return base + "\n\n" + RETRY_TEMPLATE.format(stage=stage, problem=problem[-2000:], previous=previous,
                                                 rules=OUTPUT_RULES)


def parse_reply(reply: str) -> tuple[str, list[str]]:
    """-> (code block with imports/class wrapper/package removed, list of import lines)."""
    blocks = re.findall(r"```(?:java)?[ \t]*\n(.*?)```", reply, re.S)
    code = "\n".join(blocks) if blocks else reply
    imports = sorted(set(re.findall(r"^\s*(import\s+(?:static\s+)?[\w.*]+\s*;)", code, re.M)))
    code = re.sub(r"^\s*(package|import)\s+[^;]+;\s*$", "", code, flags=re.M)
    m = re.search(r"^\s*(?:public\s+|final\s+|abstract\s+)*class\s+\w+[^{]*\{", code, re.M)
    if m:                                    # model returned a whole class: keep its body
        end = code.rfind("}")
        code = code[m.end():end] if end > m.end() else code[m.end():]
    return code.strip("\n"), imports
