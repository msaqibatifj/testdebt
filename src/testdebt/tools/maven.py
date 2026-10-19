"""Maven tool: compile + run one test class in a project/module (needs Maven >= 3.9 for Apache projects)."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

# Plugins that do not affect test semantics but slow down or block the build.
SKIP_FLAGS = ["-Denforcer.skip=true", "-Drat.skip=true", "-Dcheckstyle.skip=true", "-Dspotbugs.skip=true",
              "-Dpmd.skip=true", "-Danimal.sniffer.skip=true", "-Djapicmp.skip=true", "-Dmaven.javadoc.skip=true",
              "-Djacoco.skip=true", "-Dcyclonedx.skip=true", "-Dmoditect.skip=true", "-Drevapi.skip=true",
              "-Dbnd.skip=true", "-Dspotless.check.skip=true", "-Derrorprone.skip=true", "-Dgpg.skip=true"]
COMPILE_MARKERS = ("COMPILATION ERROR", "Compilation failure", "cannot find symbol")


class MavenRunner:
    def __init__(self, mvn: str = "mvn", timeout: int = 900, offline: bool = False, extra: list[str] | None = None,
                 java_homes: dict[str, str] | None = None):
        self.mvn, self.timeout, self.offline, self.extra = mvn, timeout, offline, extra or []
        self.java_homes = java_homes or {}     # project -> JAVA_HOME (old jsoup needs JDK <= 19 for -source 1.7)

    def env(self, project: str = "") -> dict:
        e = dict(os.environ)
        jh = self.java_homes.get(project)
        if jh:
            e["JAVA_HOME"] = jh
            e["PATH"] = f"{jh}/bin:" + e.get("PATH", "")
        return e

    def _cmd(self, goal_args: list[str]) -> list[str]:
        return [self.mvn, "-q", "-B", *goal_args, *SKIP_FLAGS, *self.extra] + (["-o"] if self.offline else [])

    def run_test_class(self, module_dir: str | Path, class_name: str, project: str = "",
                       test_file: str | Path | None = None) -> dict:
        """{'compiled','passed','log'}; compiled=False means the test sources did not compile."""
        cmd = self._cmd(["test", f"-Dtest={class_name}", "-DfailIfNoTests=false",
                         "-Dsurefire.failIfNoSpecifiedTests=false"])
        try:
            p = subprocess.run(cmd, cwd=module_dir, capture_output=True, text=True, timeout=self.timeout,
                               env=self.env(project))
        except FileNotFoundError:
            return {"compiled": False, "passed": False, "log": f"maven not found: {self.mvn}"}
        except subprocess.TimeoutExpired:
            return {"compiled": False, "passed": False, "log": "TIMEOUT"}
        out = p.stdout + p.stderr
        compile_err = p.returncode != 0 and any(k in out for k in COMPILE_MARKERS)
        return {"compiled": not compile_err, "passed": p.returncode == 0, "log": _tail(out)}

    def check_baseline(self, module_dir: str | Path, class_name: str, project: str = "",
                       test_file: str | Path | None = None) -> tuple[bool, str]:
        r = self.run_test_class(module_dir, class_name, project, test_file)
        return bool(r["compiled"] and r["passed"]), r["log"]


def _tail(out: str, n: int = 40) -> str:
    """Keep the useful part of Maven output: the first n [ERROR] lines, else the last n lines."""
    errs = [l for l in out.splitlines() if "[ERROR]" in l and "[Help" not in l and l.strip() != "[ERROR]"]
    return "\n".join(errs[:n] if errs else out.splitlines()[-n:])
