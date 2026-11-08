"""JaCoCo line coverage for single test methods (post-hoc check, not a gate in the agent loop).

Reuses FastRunner's per-module preparation (compiled main + test classes, test class path, JUnit console launcher).
Per call: javac the given test class source into a fresh dir, run only the named methods with the JaCoCo agent,
then `jacococli report --xml` over target/classes (main code only) and read the covered lines.
Jars (data/tools/jacoco/): org.jacoco.agent-0.8.12-runtime.jar, org.jacoco.cli-0.8.12-nodeps.jar, fetched with
  mvn dependency:copy -Dartifact=org.jacoco:org.jacoco.cli:0.8.12:jar:nodeps -DoutputDirectory=data/tools/jacoco
  mvn dependency:copy -Dartifact=org.jacoco:org.jacoco.agent:0.8.12:jar:runtime -DoutputDirectory=data/tools/jacoco
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from .fastrun import FastRunner

JACOCO_VERSION = "0.8.12"
JAR_DIR = Path("data/tools/jacoco")
Line = tuple[str, int]          # (package/SourceFile.java, line number)


def parse_report(xml_path: str | Path) -> set[Line]:
    """Lines with at least one covered instruction, from a JaCoCo XML report."""
    out: set[Line] = set()
    for pkg in ET.parse(xml_path).getroot().iter("package"):
        for sf in pkg.iter("sourcefile"):
            for ln in sf.iter("line"):
                if int(ln.get("ci", "0")) > 0:
                    out.add((f"{pkg.get('name')}/{sf.get('name')}", int(ln.get("nr"))))
    return out


def compare(before: set[Line], after: set[Line]) -> dict:
    lost = before - after
    return {"lines_before": len(before), "lines_after": len(after), "lost": len(lost), "gained": len(after - before),
            "preserved": not lost, "lost_lines": sorted(lost)[:20]}


class JacocoRunner:
    def __init__(self, runner: FastRunner, jar_dir: str | Path = JAR_DIR, timeout: int = 600):
        self.runner, self.timeout = runner, timeout
        d = Path(jar_dir).resolve()
        self.agent = d / f"org.jacoco.agent-{JACOCO_VERSION}-runtime.jar"
        self.cli = d / f"org.jacoco.cli-{JACOCO_VERSION}-nodeps.jar"

    def available(self) -> bool:
        return self.agent.exists() and self.cli.exists()

    def covered_lines(self, module_dir: str | Path, project: str, test_file: str | Path, class_src: str,
                      methods: list[str] | set[str]) -> dict:
        """Run `methods` of the class whose source is `class_src` (written to a temp copy, never into the project).
        -> {'ok', 'passed', 'lines', 'log'}"""
        info = self.runner.prepare(module_dir, project)
        if not info["launcher"]:
            return {"ok": False, "passed": False, "lines": set(), "log": "no JUnit console launcher"}
        pkg = re.search(r"^\s*package\s+([\w.]+)\s*;", class_src, re.M)
        cls = Path(test_file).stem
        fqn = f"{pkg.group(1)}.{cls}" if pkg else cls
        env, sep = self.runner.env(project), os.pathsep
        work = Path(tempfile.mkdtemp(prefix="td_jacoco_"))
        try:
            src = work / "src" / Path(test_file).name
            src.parent.mkdir()
            src.write_text(class_src, encoding="utf-8")
            out = work / "classes"
            base_cp = sep.join([info["test_classes"], info["classes"], info["deps"]])
            c = subprocess.run(["javac", "-nowarn", "-encoding", "UTF-8", "-proc:none", "-g", "-cp", base_cp,
                                "-d", str(out), str(src)], capture_output=True, text=True, timeout=self.timeout, env=env)
            if c.returncode != 0:
                return {"ok": False, "passed": False, "lines": set(), "log": "COMPILATION ERROR\n" + c.stderr[-1500:]}
            selectors = self._selectors(out, fqn, set(methods), env)
            if not selectors:
                return {"ok": False, "passed": False, "lines": set(), "log": f"methods not found: {sorted(methods)}"}
            own = [d for d in info["deps"].split(sep)
                   if not re.search(r"(junit-jupiter-engine|junit-vintage-engine|junit-platform-[\w-]+)-[\d.]+\.jar$", d)]
            run_cp = sep.join([str(out), info["test_classes"], info["classes"], *own, *info["vintage"]])
            exec_file = work / "jacoco.exec"
            cmd = ["java", f"-javaagent:{self.agent}=destfile={exec_file}", "-jar", info["launcher"], "execute",
                   "--class-path", run_cp, *[a for s in selectors for a in ("--select-method", s)],
                   "--disable-banner", "--details=summary", "--disable-ansi-colors"]
            r = subprocess.run(cmd, cwd=module_dir, capture_output=True, text=True, timeout=self.timeout, env=env)
            log = (r.stdout + r.stderr)[-1500:]
            found = re.search(r"(\d+) tests successful", r.stdout)
            if not exec_file.exists() or not found:
                return {"ok": False, "passed": False, "lines": set(), "log": log}
            xml = work / "report.xml"
            rep = subprocess.run(["java", "-jar", str(self.cli), "report", str(exec_file), "--classfiles",
                                  info["classes"], "--xml", str(xml)], capture_output=True, text=True,
                                 timeout=self.timeout, env=env)
            if rep.returncode != 0 or not xml.exists():
                return {"ok": False, "passed": False, "lines": set(), "log": rep.stderr[-1500:]}
            return {"ok": True, "passed": r.returncode == 0 and int(found.group(1)) > 0,
                    "lines": parse_report(xml), "log": log}
        except subprocess.TimeoutExpired:
            return {"ok": False, "passed": False, "lines": set(), "log": "TIMEOUT"}
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def _selectors(self, classes_dir: Path, fqn: str, methods: set[str], env: dict) -> list[str]:
        """'fqn#name(param types)' for each requested method, from javap (parameterized tests need the types)."""
        p = subprocess.run(["javap", "-cp", str(classes_dir), fqn], capture_output=True, text=True,
                           timeout=self.timeout, env=env)
        out = []
        for m in re.finditer(r"\b(\w+)\(([^)]*)\)", p.stdout):
            if m.group(1) in methods:
                out.append(f"{fqn}#{m.group(1)}({m.group(2).replace(' ', '')})")
        return sorted(set(out))
