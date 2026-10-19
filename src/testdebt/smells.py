"""Fast rule-based test-smell detector (Python, no Java).

An APPROXIMATION of tsDetect rules, used to (1) pre-filter candidates and (2) re-check refactored code
inside the loop. Final numbers in the report must come from tsDetect (tools/tsdetect.py) and JNose.
Each smell type is counted at most once per test method. Handles JUnit 4 (message first) and JUnit 5
(message last) assertion signatures.
"""
from __future__ import annotations

import re
from collections import Counter

from .java_utils import extract_test_methods, mask, match_close, split_args

SMELL_DEFS = {
    "AssertionRoulette": "two or more assertions without an explanatory message",
    "MagicNumberTest": "numeric literals (other than 0, 1, -1) used directly in assertions",
    "ConditionalTestLogic": "if/for/while/switch inside the test",
    "DuplicateAssert": "the same assertion statement appears more than once",
    "EagerTest": "the test exercises 4+ different production methods (heuristic)",
    "ExceptionHandling": "try/catch or throw inside the test body",
    "SleepyTest": "Thread.sleep used to wait",
    "RedundantPrint": "System.out/err printing inside the test",
    "EmptyTest": "test body has no statements",
    "IgnoredTest": "test is disabled with @Ignore/@Disabled",
    "UnknownTest": "test has no assertion, fail(), verify() or expected exception",
}

# number of non-message arguments per assertion
ASSERT_MIN = {"assertEquals": 2, "assertNotEquals": 2, "assertSame": 2, "assertNotSame": 2,
              "assertArrayEquals": 2, "assertIterableEquals": 2, "assertLinesMatch": 2,
              "assertThrows": 2, "assertDoesNotThrow": 1, "assertTimeout": 2, "assertInstanceOf": 2,
              "assertTrue": 1, "assertFalse": 1, "assertNull": 1, "assertNotNull": 1, "assertAll": 99}
STOP_CALLS = {"equals", "toString", "hashCode", "size", "get", "add", "length", "isEmpty", "contains",
              "put", "of", "asList", "format", "println", "print", "sleep", "getClass", "name", "append",
              "build", "builder", "valueOf", "trim", "split", "stream", "collect", "toArray", "iterator"}
_NUM = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?[LlFfDd]?(?![\w.])")
_TRIVIAL = {"0", "1", "-1", "0.0", "1.0"}


def _assertions(text: str, m: str):
    found = []
    for mt in re.finditer(r"(?<![\w.])(?:Assert(?:ions)?\s*\.\s*)?(assert[A-Z]\w*|fail)\s*\(", m):
        op = mt.end() - 1
        cl = match_close(m, op, "(", ")")
        if cl < 0:
            continue
        found.append((mt.group(1), split_args(text, m, op + 1, cl),
                      re.sub(r"\s+", " ", text[mt.start():cl + 1])))
    return found


def count_assertions(text: str) -> int:
    return len(_assertions(text, mask(text)))


def has_message(name: str, args) -> bool:
    if name == "assertThat":                       # Hamcrest: assertThat(reason, actual, matcher)
        return len(args) == 3
    if name == "assertAll":
        return bool(args) and args[0][0].startswith('"')
    mn = ASSERT_MIN.get(name, 1)
    if len(args) <= mn:
        return False
    first, last = args[0], args[-1]
    if first[0].startswith('"'):                   # JUnit 4: message first
        return True
    if name in ("assertEquals", "assertNotEquals", "assertArrayEquals") and len(args) == mn + 1 \
            and _NUM.fullmatch(last[1].strip()):   # (expected, actual, delta) for doubles
        return False
    return True                                    # JUnit 5: message (String or Supplier) last


def analyze_method(text: str) -> set[str]:
    """Smell names found in one test method (text includes annotations)."""
    m, smells = mask(text), set()
    bo = m.find("{")
    header, body = (m[:bo], m[bo + 1:-1]) if bo >= 0 else (m, "")
    asserts = _assertions(text, m)
    real = [a for a in asserts if a[0] != "fail"]
    if sum(1 for n, args, _ in real if not has_message(n, args)) >= 2:
        smells.add("AssertionRoulette")
    for n, args, _ in real:
        if any(x.rstrip("LlFfDd") not in _TRIVIAL for _, am in args for x in _NUM.findall(am)):
            smells.add("MagicNumberTest")
            break
    if re.search(r"\b(if|for|while|switch)\s*\(", body):
        smells.add("ConditionalTestLogic")
    if any(c > 1 for c in Counter(s for _, _, s in real).values()):
        smells.add("DuplicateAssert")
    calls = {c for c in re.findall(r"\.\s*(\w+)\s*\(", body) if not c.startswith("assert")} - STOP_CALLS
    if len(calls) >= 4:
        smells.add("EagerTest")
    if re.search(r"\bcatch\s*\(|\bthrow\s+new\b", body):
        smells.add("ExceptionHandling")
    if re.search(r"Thread\s*\.\s*sleep\s*\(", body):
        smells.add("SleepyTest")
    if re.search(r"System\s*\.\s*(out|err)\s*\.\s*print", body):
        smells.add("RedundantPrint")
    if not body.strip():
        smells.add("EmptyTest")
    elif not asserts and not re.search(r"\b(verify|assertThrows)\s*\(", body) and "expected" not in header:
        smells.add("UnknownTest")
    if re.search(r"@(Ignore|Disabled)\b", header):
        smells.add("IgnoredTest")
    return smells


def analyze_code(code: str) -> Counter:
    """Smell counts over every test method in code (or the whole snippet if none found)."""
    methods = extract_test_methods(code)
    c: Counter = Counter()
    for t in (methods or [{"text": code}]):
        c.update(analyze_method(t["text"]))
    return c
