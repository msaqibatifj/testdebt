"""tsDetect wrapper (the detector used by UTRefactor), method-level.

The jar in the UTRefactor package (detection/v3/TestSmellDetector.jar) takes a CSV of
`app,testFilePath,productionFilePath` and writes Output_TestSmellDetection_<ts>.csv with ONE row per test
FILE and a 0/1 flag per smell. UTRefactor gets method-level results by splitting each test class into one
file per test method; we do the same: each "unit" is the class with every other test method removed
(fields, setUp and helpers are kept, so fixture smells still see their context).
"""
from __future__ import annotations

import csv
import glob
import os
import subprocess
import tempfile
from pathlib import Path

from ..java_utils import extract_test_methods

# tsDetect column -> our smell id (same ids as smells.SMELL_DEFS where both exist)
COLUMN_TO_SMELL = {
    "Assertion Roulette": "AssertionRoulette", "Conditional Test Logic": "ConditionalTestLogic",
    "Constructor Initialization": "ConstructorInitialization", "Default Test": "DefaultTest",
    "EmptyTest": "EmptyTest", "Exception Catching Throwing": "ExceptionHandling",
    "General Fixture": "GeneralFixture", "Mystery Guest": "MysteryGuest", "Print Statement": "RedundantPrint",
    "Redundant Assertion": "RedundantAssertion", "Sensitive Equality": "SensitiveEquality",
    "Verbose Test": "VerboseTest", "Sleepy Test": "SleepyTest", "Eager Test": "EagerTest", "Lazy Test": "LazyTest",
    "Duplicate Assert": "DuplicateAssert", "Unknown Test": "UnknownTest", "IgnoredTest": "IgnoredTest",
    "Resource Optimism": "ResourceOptimism", "Magic Number Test": "MagicNumberTest",
    "Dependent Test": "DependentTest",
}
# UTRefactor report labels (e.g. "Assertion_Roulette") -> our smell ids
UTR_TO_SMELL = {k.replace(" ", "_"): v for k, v in COLUMN_TO_SMELL.items()}
UTR_TO_SMELL.update({"Print_Statement": "RedundantPrint", "Exception_Catching_Throwing": "ExceptionHandling"})
SMELL_TO_UTR = {v: k for k, v in UTR_TO_SMELL.items()}


def keep_only(src: str, keep: set[str]) -> str:
    """Remove every test method whose name is not in `keep` (back to front so offsets stay valid)."""
    for t in sorted(extract_test_methods(src), key=lambda t: -t["start"]):
        if t["name"] not in keep:
            src = src[:t["start"]] + src[t["end"]:]
    return src


def focal_class_file(test_file: str | Path) -> str:
    """Production file by naming convention FooTest -> Foo (empty string if not found; tsDetect accepts that)."""
    p = Path(test_file)
    name = p.stem[:-4] if p.stem.endswith("Test") else p.stem.removeprefix("Test")
    parts = list(p.parts)
    if "test" in parts:
        i = len(parts) - 1 - parts[::-1].index("test")
        cand = Path(*parts[:i], "main", *parts[i + 1:-1], name + ".java")
        if cand.exists():
            return str(cand.resolve())
    return ""


class TsDetect:
    def __init__(self, jar: str | Path, java: str = "java", timeout: int = 600):
        self.jar, self.java, self.timeout = Path(jar), java, timeout

    def available(self) -> bool:
        return self.jar.exists()

    def detect_units(self, units: list[dict]) -> dict[str, set[str]]:
        """units: [{'key', 'source', 'class_name', 'production_file'}] -> {key: set(smells)}.
        Each unit is written as <tmp>/<i>/<ClassName>.java and analysed in one jar call."""
        if not units:
            return {}
        with tempfile.TemporaryDirectory(prefix="tsdetect_") as tmp:
            rows, path_to_key = [], {}
            for i, u in enumerate(units):
                d = Path(tmp, str(i))
                d.mkdir()
                f = d / f"{u['class_name']}.java"
                f.write_text(u["source"], encoding="utf-8")
                prod = u.get("production_file", "")
                rows.append(["app", str(f.resolve()), str(Path(prod).resolve()) if prod else ""])
                path_to_key[str(f.resolve())] = u["key"]
            inp = Path(tmp, "input.csv")
            with inp.open("w", newline="", encoding="utf-8") as fh:
                csv.writer(fh).writerows(rows)
            p = subprocess.run([self.java, "-jar", str(self.jar.resolve()), str(inp)], cwd=tmp,
                               capture_output=True, text=True, timeout=self.timeout)
            outs = sorted(glob.glob(os.path.join(tmp, "Output_TestSmellDetection_*.csv")))
            if not outs:
                raise RuntimeError(f"tsDetect produced no output: {(p.stdout + p.stderr)[-500:]}")
            result: dict[str, set[str]] = {u["key"]: set() for u in units}
            with open(outs[-1], newline="", encoding="utf-8") as fh:
                for r in csv.DictReader(fh):
                    key = path_to_key.get(r["TestFilePath"])
                    if key is None:
                        continue
                    result[key] = {COLUMN_TO_SMELL[c] for c in COLUMN_TO_SMELL
                                   if c in r and str(r[c]).strip() not in ("", "0", "false")}
            return result

    def detect_methods(self, test_file: str | Path, methods: list[str] | None = None) -> dict[str, set[str]]:
        """Method-level smells for (some of) the test methods in one real test file."""
        src = Path(test_file).read_text(encoding="utf-8", errors="replace")
        names = methods or [t["name"] for t in extract_test_methods(src)]
        prod, cls = focal_class_file(test_file), Path(test_file).stem
        return self.detect_units([{"key": n, "source": keep_only(src, {n}), "class_name": cls,
                                   "production_file": prod} for n in names])

    def detect_source(self, source: str, class_name: str, keep: set[str], production_file: str = "") -> set[str]:
        """Smells of the unit made of `keep` methods inside `source` (used on refactored code)."""
        return self.detect_units([{"key": "x", "source": keep_only(source, keep), "class_name": class_name,
                                   "production_file": production_file}])["x"]
