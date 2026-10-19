"""Fast compile + run: call Maven ONCE per module, then use javac + a JUnit launcher for each test.

`mvn test` per refactored test costs 20-60 s (Maven startup, plugin resolution, recompiling). Here:
  prepare (once per module, cached in target/testdebt/):
    mvn test-compile + dependency:build-classpath (test scope) + fetch junit-platform-console-standalone
  per test:
    javac ONLY the patched test file into a fresh dir that goes first on the classpath (~1-2 s),
    then run that one class with the JUnit 5 console launcher (JUnit 4 tests via its vintage engine,
    which we add to the classpath) or JUnitCore when the project is JUnit 4 only.
Same result contract as MavenRunner: {'compiled','passed','log'}.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .maven import SKIP_FLAGS, MavenRunner



class FastRunner(MavenRunner):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._prepared: dict[str, dict] = {}
        self._maven_only: set[tuple[str, str]] = set()   # classes the fast path cannot run faithfully

    def check_baseline(self, module_dir, class_name, project="", test_file=None) -> tuple[bool, str]:
        """Original class must pass. If it passes under Maven but not on the fast path (surefire argLine,
        system properties, ...), use Maven for this class from now on, so results stay faithful."""
        r = self.run_test_class(module_dir, class_name, project, test_file)
        if r["compiled"] and r["passed"]:
            return True, ""
        m = MavenRunner.run_test_class(self, module_dir, class_name, project)
        if m["compiled"] and m["passed"]:
            self._maven_only.add((str(Path(module_dir).resolve()), class_name))
            return True, "fast path disagreed with Maven; using Maven for this class"
        return False, m["log"]

    # ------------------------------------------------------------------ once per module
    def _mvn(self, module_dir: Path, project: str, *goals: str) -> subprocess.CompletedProcess:
        return subprocess.run([self.mvn, "-q", "-B", *goals, *SKIP_FLAGS, *self.extra], cwd=module_dir,
                              capture_output=True, text=True, timeout=self.timeout, env=self.env(project))

    def prepare(self, module_dir: str | Path, project: str = "") -> dict:
        key = str(Path(module_dir).resolve())
        if key in self._prepared:
            return self._prepared[key]
        m = Path(module_dir)
        work = m / "target/testdebt"
        work.mkdir(parents=True, exist_ok=True)
        cp_file = work / "classpath.txt"
        if not cp_file.exists() or not (m / "target/test-classes").exists():
            p = self._mvn(m, project, "test-compile", "dependency:build-classpath",
                          f"-Dmdep.outputFile={cp_file.resolve()}", "-Dmdep.includeScope=test")
            if p.returncode != 0 or not cp_file.exists():
                raise RuntimeError("prepare failed (mvn test-compile):\n" + (p.stdout + p.stderr)[-1500:])
        deps = cp_file.read_text().strip()
        # launcher must match the project's JUnit 5 version (jupiter 5.Y.Z <-> platform 1.Y.Z)
        jv = re.search(r"junit-jupiter-api-5\.(\d+)\.(\d+)", deps)
        minor, patch = (jv.group(1), jv.group(2)) if jv else ("10", "2")
        console, vintage_art = (f"org.junit.platform:junit-platform-console-standalone:1.{minor}.{patch}",
                                f"org.junit.vintage:junit-vintage-engine:5.{minor}.{patch}")
        tools = (work / "tools").resolve()
        launcher = tools / f"junit-platform-console-standalone-1.{minor}.{patch}.jar"
        vintage = tools / f"junit-vintage-engine-5.{minor}.{patch}.jar"
        if not launcher.exists():
            for art in (console, vintage_art):
                self._mvn(m, project, "dependency:copy", f"-Dartifact={art}", f"-DoutputDirectory={tools}")
        info = {"classes": str((m / "target/classes").resolve()), "test_classes": str((m / "target/test-classes").resolve()),
                "deps": deps, "launcher": str(launcher) if launcher.exists() else "",
                "vintage": [str(vintage)] if vintage.exists() else [], "jupiter": "junit-jupiter" in deps}
        self._prepared[key] = info
        return info

    # ------------------------------------------------------------------ per test
    def run_test_class(self, module_dir: str | Path, class_name: str, project: str = "",
                       test_file: str | Path | None = None) -> dict:
        if (str(Path(module_dir).resolve()), class_name) in self._maven_only:
            return super().run_test_class(module_dir, class_name, project)
        try:
            info = self.prepare(module_dir, project)
        except Exception as e:                       # fall back to plain Maven
            r = super().run_test_class(module_dir, class_name, project)
            r["log"] = f"(fast runner unavailable: {str(e)[:200]})\n" + r["log"]
            return r
        if test_file is None:
            hits = [p for p in Path(module_dir, "src/test").rglob(f"{class_name}.java")]
            if len(hits) != 1:
                return super().run_test_class(module_dir, class_name, project)
            test_file = hits[0]
        src = Path(test_file).read_text(encoding="utf-8", errors="replace")
        pkg = re.search(r"^\s*package\s+([\w.]+)\s*;", src, re.M)
        fqn = f"{pkg.group(1)}.{class_name}" if pkg else class_name
        sep = os.pathsep
        env = self.env(project)
        out_dir = Path(tempfile.mkdtemp(prefix="td_tc_"))
        try:
            base_cp = sep.join([info["test_classes"], info["classes"], info["deps"]])
            c = subprocess.run(["javac", "-nowarn", "-encoding", "UTF-8", "-proc:none", "-g", "-cp", base_cp,
                                "-d", str(out_dir), str(test_file)], capture_output=True, text=True,
                               timeout=self.timeout, env=env)
            if c.returncode != 0:
                return {"compiled": False, "passed": False, "log": "COMPILATION ERROR\n" + c.stderr[-3000:]}
            run_cp = sep.join([str(out_dir), base_cp])
            if info["launcher"]:
                # the standalone launcher bundles the platform + Jupiter engine; a second copy of an engine on the
                # class path makes JUnit refuse to start ("multiple engines with the same ID")
                own = [d for d in info["deps"].split(sep)
                       if not re.search(r"(junit-jupiter-engine|junit-vintage-engine|junit-platform-[\w-]+)-[\d.]+\.jar$", d)]
                run_cp = sep.join([str(out_dir), info["test_classes"], info["classes"], *own, *info["vintage"]])
                cmd = ["java", "-jar", info["launcher"], "execute", "--class-path", run_cp, "--select-class", fqn,
                       "--disable-banner", "--details=summary", "--disable-ansi-colors"]
            else:                                    # JUnit 4 only, no launcher available
                cmd = ["java", "-cp", run_cp, "org.junit.runner.JUnitCore", fqn]
            r = subprocess.run(cmd, cwd=module_dir, capture_output=True, text=True, timeout=self.timeout, env=env)
            out = r.stdout + r.stderr
            found = re.search(r"(\d+) tests found", out)
            ran = (found and int(found.group(1)) > 0) or re.search(r"OK \((?!0 tests)", out) or "Tests run:" in out
            if r.returncode == 0 and not ran:
                return {"compiled": True, "passed": False, "log": "no tests were executed:\n" + out[-1500:]}
            return {"compiled": True, "passed": r.returncode == 0, "log": _short(out)}
        except subprocess.TimeoutExpired:
            return {"compiled": True, "passed": False, "log": "TIMEOUT"}
        finally:
            shutil.rmtree(out_dir, ignore_errors=True)


def _short(out: str, n: int = 40) -> str:
    keep = [l for l in out.splitlines() if re.search(r"(✘|FAIL|Exception|Error|expected|but was|at org|tests? (failed|successful))", l)]
    return "\n".join(keep[:n] if keep else out.splitlines()[-n:])
