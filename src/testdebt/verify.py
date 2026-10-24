"""Verifier: patch -> static checks -> smells after -> compile + run -> kill-set -> ALWAYS restore.

Every number comes from a tool (Maven, tsDetect, PIT, the rules detector), never from the LLM.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .contracts import TestRef, VerificationReport
from .java_utils import extract_test_methods, find_method, mask
from .smells import analyze_code, count_assertions, removable_assertions
from .tools import pit as pitmod
from .tools.maven import MavenRunner
from .tools.tsdetect import TsDetect, focal_class_file


def add_imports(src: str, imports: list[str]) -> str:
    missing = [i for i in imports if re.sub(r"\s+", " ", i) not in re.sub(r"\s+", " ", src)]
    if not missing:
        return src
    anchor = list(re.finditer(r"^\s*import\s[^;]+;\s*$", src, re.M)) or list(re.finditer(r"^\s*package\s[^;]+;\s*$", src, re.M))
    pos = anchor[-1].end() if anchor else 0
    return src[:pos] + "\n" + "\n".join(missing) + src[pos:]


JUNIT4_ASSERT = {"assertEquals", "assertNotEquals", "assertTrue", "assertFalse", "assertNull", "assertNotNull",
                 "assertSame", "assertNotSame", "assertArrayEquals", "assertThrows", "assertThat", "fail"}


def missing_assert_imports(src: str, block: str) -> list[str]:
    """Static imports for JUnit assertions the new code uses but the file does not import.
    Applied identically to every system (deterministic, no LLM). Names JUnit 4 does not have
    (e.g. assertDoesNotThrow in a JUnit 4 project) are left alone, so they fail to compile as they should."""
    jupiter = "org.junit.jupiter" in src
    owner = "org.junit.jupiter.api.Assertions" if jupiter else "org.junit.Assert"
    if re.search(r"import\s+static\s+" + re.escape(owner) + r"\.\*\s*;", src):
        return []
    used = set(re.findall(r"(?<![\w.])(assert\w+|fail)\s*\(", mask(block)))
    out = []
    for name in sorted(used):
        if re.search(r"import\s+static\s+[\w.]+\." + name + r"\s*;", src):
            continue
        if re.search(r"\b[\w<>\[\]]+\s+" + name + r"\s*\([^)]*\)\s*(throws[^{]*)?\{", src + "\n" + block):
            continue                                  # a helper with that name exists in the class/block
        if jupiter or name in JUNIT4_ASSERT:
            out.append(f"import static {owner}.{name};")
    return out


JUPITER_PARAMS = {"ParameterizedTest": "org.junit.jupiter.params.ParameterizedTest",
                  "CsvSource": "org.junit.jupiter.params.provider.CsvSource",
                  "ValueSource": "org.junit.jupiter.params.provider.ValueSource",
                  "MethodSource": "org.junit.jupiter.params.provider.MethodSource",
                  "Arguments": "org.junit.jupiter.params.provider.Arguments"}


def missing_param_imports(src: str, block: str) -> list[str]:
    """Imports for JUnit 5 parameterized-test annotations used by new code (JUnit 5 files only)."""
    if "org.junit.jupiter" not in src:
        return []
    out = []
    for name, fq in JUPITER_PARAMS.items():
        if re.search(r"(@|\b)" + name + r"\b", block) and not re.search(
                r"import\s+(" + re.escape(fq) + r"|" + re.escape(fq.rsplit(".", 1)[0]) + r"\.\*)\s*;", src):
            out.append(f"import {fq};")
    return out


def patch_source(src: str, method: str, block: str, imports: list[str]) -> str | None:
    """Replace test `method` with `block` (one or more members), re-indented; add imports."""
    t = find_method(src, method)
    if t is None:
        return None
    indent = re.match(r"[ \t]*", src[t["start"]:]).group(0)
    lines = block.strip("\n").splitlines()
    base = min((len(l) - len(l.lstrip()) for l in lines if l.strip()), default=0)
    body = "\n".join((indent + l[base:]) if l.strip() else "" for l in lines)
    return add_imports(src[:t["start"]] + body + src[t["end"]:], imports)


def static_checks(original: str, block: str) -> tuple[bool, str, dict]:
    m = mask(block)
    new_tests = [t["name"] for t in extract_test_methods(block)]
    info = {"new_tests": new_tests, "assertions_before": count_assertions(original),
            "assertions_after": count_assertions(block)}
    if not block.strip():
        return False, "empty reply / no Java code block", info
    if m.count("{") != m.count("}") or m.count("(") != m.count(")"):
        return False, "unbalanced braces or parentheses", info
    if not new_tests:
        return False, "no @Test method in the reply", info
    parameterized = re.search(r"@(ParameterizedTest|RunWith\s*\(\s*Parameterized)", block) is not None
    dropped = info["assertions_before"] - info["assertions_after"]
    # Allowed drops: a data-driven rewrite has fewer call sites (PIT's kill-set is the real check), and
    # removing duplicate (DuplicateAssert) or redundant (RedundantAssertion) assertions is the intended fix.
    # Never allowed: ending with no assertion at all.
    allowed = parameterized or dropped <= removable_assertions(original)
    if dropped > 0 and (not allowed or (info["assertions_before"] > 0 and info["assertions_after"] == 0)):
        return False, f"assertions dropped: {info['assertions_before']} -> {info['assertions_after']}", info
    return True, "", info


class Verifier:
    def __init__(self, maven: MavenRunner | None, tsdetect: TsDetect | None = None, pit: pitmod.PitRunner | None = None,
                 pit_cache: str | Path = "runs/pit_cache", run_tests: bool = True):
        self.maven, self.tsdetect, self.pit = maven, tsdetect, pit
        self.pit_cache, self.run_tests = Path(pit_cache), run_tests

    # ---- baseline kill matrix per test class (cached on disk, computed once) ----
    def _pit_target(self, test: TestRef, src: str) -> tuple[str, str]:
        pkg = pitmod.package_of(src)
        return (f"{pkg}.{test.class_name}" if pkg else test.class_name), (f"{pkg}.*" if pkg else "*")

    def baseline_matrix(self, test: TestRef) -> dict[str, set]:
        f = self.pit_cache / f"{test.project}__{test.class_name}.json"
        if f.exists():
            return {k: {tuple(x) for x in v} for k, v in json.loads(f.read_text()).items()}
        src = Path(test.file).read_text(encoding="utf-8")
        fqn, targets = self._pit_target(test, src)
        mat = self.pit.run(test.module_dir, fqn, targets, test.project)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({k: sorted(v) for k, v in mat.items()}))
        return mat

    # ---- the ORIGINAL class must compile and pass here, otherwise nothing after can be trusted ----
    def baseline_ok(self, test: TestRef) -> tuple[bool, str]:
        if not (self.run_tests and self.maven):
            return True, ""
        key = (test.module_dir, test.class_name)
        if not hasattr(self, "_baseline"):
            self._baseline = {}
        if key not in self._baseline:
            if hasattr(self.maven, "check_baseline"):
                self._baseline[key] = self.maven.check_baseline(test.module_dir, test.class_name, test.project, test.file)
            else:
                r = self.maven.run_test_class(test.module_dir, test.class_name, test.project)
                self._baseline[key] = (r["compiled"] and r["passed"], r["log"])
        return self._baseline[key]

    # ---- main entry ----
    def verify(self, test: TestRef, original: str, block: str, imports: list[str], targeted: list[str]) -> VerificationReport:
        sane, problem, info = static_checks(original, block)
        rep = VerificationReport(sane=sane, problem=problem, assertions_before=info["assertions_before"],
                                 assertions_after=info["assertions_after"])
        if not sane:
            return rep
        path = Path(test.file)
        src = path.read_text(encoding="utf-8")
        patched = patch_source(src, test.method, block, imports + missing_assert_imports(src, block)
                               + missing_param_imports(src, block))
        if patched is None:
            rep.sane, rep.problem = False, f"could not locate {test.method} uniquely in {path.name}"
            return rep
        new_tests = set(info["new_tests"])
        # smells after: tsDetect when available (the measurement of record), else the rules approximation
        if self.tsdetect and self.tsdetect.available():
            after = self.tsdetect.detect_source(patched, test.class_name, new_tests, focal_class_file(path))
        else:
            after = set(analyze_code(block))
        rep.smells_after = sorted(after)
        # The baseline kill matrix MUST come from the unmodified class, so it is computed (or read from cache)
        # before the patch is written. Computing it lazily after the write measured the refactored code.
        before = (pitmod.kill_set(self.baseline_matrix(test), {test.method})
                  if self.pit and self.run_tests and self.maven else None)
        try:
            path.write_text(patched, encoding="utf-8")
            if self.run_tests and self.maven:
                r = self.maven.run_test_class(test.module_dir, test.class_name, test.project, test_file=path)
                rep.compiled, rep.passed = r["compiled"], r["passed"]
                if not r["compiled"]:
                    rep.problem = "compilation failed:\n" + r["log"]
                elif not r["passed"]:
                    rep.problem = "test run failed:\n" + r["log"]
            if self.pit and rep.compiled and rep.passed and not before:
                # empty baseline kill-set: nothing to preserve is NOT evidence of safety -> unknown, not preserved
                # (counted as "killset_unknown" in metrics; not a rejection reason by itself)
                rep.killset_preserved, rep.mutants_killed_before = None, 0
            elif self.pit and rep.compiled and rep.passed:
                fqn, targets = self._pit_target(test, patched)
                after_mat = self.pit.run(test.module_dir, fqn, targets, test.project)
                cmp = pitmod.compare(before, pitmod.kill_set(after_mat, new_tests))
                rep.killset_preserved = cmp["preserved"]
                rep.mutants_killed_before, rep.mutants_killed_after = cmp["killed_before"], cmp["killed_after"]
                if not cmp["preserved"]:
                    rep.problem = (f"kill-set lost: {cmp['lost']} mutant(s) killed by the original test are no longer "
                                   f"killed, e.g. {cmp['lost_mutants'][:3]}")
        finally:
            path.write_text(src, encoding="utf-8")          # never leave the project modified
        return rep
