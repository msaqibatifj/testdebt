"""PIT mutation testing: per-test kill sets (gap G1).

We never edit the project's pom.xml. We write pom.pit.xml next to it with the PIT plugin (+ JUnit 5 support)
added, and run `mvn -f pom.pit.xml ...`. fullMutationMatrix=true makes PIT record EVERY test that kills each
mutant, so K(T) = mutants whose killingTests contain test method T.
Kill-set preserved  <=>  K(T) is a subset of the union of K(t) over the refactored methods t (handles splits).
"""
from __future__ import annotations

import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from .maven import SKIP_FLAGS

PIT_VERSION = "1.17.4"            # check https://pitest.org for the latest 1.x before the main run
JUNIT5_PLUGIN_VERSION = "1.2.1"
PIT_FILE = "pom.pit.xml"

PLUGIN_XML = f"""
      <plugin>
        <groupId>org.pitest</groupId>
        <artifactId>pitest-maven</artifactId>
        <version>{PIT_VERSION}</version>
        <dependencies>
          <dependency>
            <groupId>org.pitest</groupId>
            <artifactId>pitest-junit5-plugin</artifactId>
            <version>{JUNIT5_PLUGIN_VERSION}</version>
          </dependency>
        </dependencies>
      </plugin>
"""

Mutant = tuple[str, str, str, str, str]   # class, method, line, mutator, index


def _span(xml: str, tag: str) -> list[tuple[int, int]]:
    return [(m.start(), xml.find(f"</{tag}>", m.start())) for m in re.finditer(f"<{tag}>", xml)]


def add_pit_plugin(pom_xml: str) -> str:
    """Insert the PIT plugin into the project's top-level <build><plugins> (not pluginManagement/profiles/reporting)."""
    if "pitest-maven" in pom_xml:
        return pom_xml
    excluded = _span(pom_xml, "pluginManagement") + _span(pom_xml, "profiles") + _span(pom_xml, "reporting")
    build = next(((s, e) for s, e in _span(pom_xml, "build") if not any(a <= s <= b for a, b in excluded)), None)
    if build is None:   # no top-level <build>: add one before </project>
        i = pom_xml.rfind("</project>")
        return pom_xml[:i] + f"  <build>\n    <plugins>{PLUGIN_XML}    </plugins>\n  </build>\n" + pom_xml[i:]
    for s, _ in _span(pom_xml, "plugins"):
        if build[0] < s < build[1] and not any(a <= s <= b for a, b in excluded):
            j = s + len("<plugins>")
            return pom_xml[:j] + PLUGIN_XML + pom_xml[j:]
    i = pom_xml.find("</build>", build[0])
    return pom_xml[:i] + f"  <plugins>{PLUGIN_XML}    </plugins>\n  " + pom_xml[i:]


def test_method_name(killing: str) -> str:
    """'pkg.FooTest.[engine:junit-jupiter]/[class:pkg.FooTest]/[method:testX()]' or 'pkg.FooTest.testX(pkg.FooTest)' -> testX"""
    m = re.search(r"\[(?:method|test-template):(\w+)\(", killing) or re.search(r"\.(\w+)\([^()]*\)\s*$", killing)
    return m.group(1) if m else killing


def parse_kill_matrix(xml_path: str | Path) -> dict[str, set[Mutant]]:
    """{test method name: set of mutants it kills} from PIT's mutations.xml (fullMutationMatrix=true)."""
    out: dict[str, set[Mutant]] = {}
    for m in ET.parse(xml_path).getroot().iter("mutation"):
        if m.get("status") != "KILLED":
            continue
        g = lambda t: (m.findtext(t) or "").strip()
        mutant = (g("mutatedClass"), g("mutatedMethod"), g("lineNumber"), g("mutator"), g("index"))
        tests = g("killingTests") or g("killingTest")
        for t in filter(None, tests.split("|")):
            out.setdefault(test_method_name(t), set()).add(mutant)
    return out


def kill_set(matrix: dict[str, set[Mutant]], methods: list[str] | set[str]) -> set[Mutant]:
    s: set[Mutant] = set()
    for name in methods:
        s |= matrix.get(name, set())
    return s


def compare(before: set[Mutant], after: set[Mutant]) -> dict:
    lost = before - after
    return {"killed_before": len(before), "killed_after": len(after), "lost": len(lost), "preserved": not lost,
            "lost_mutants": sorted(lost)[:20]}


class PitRunner:
    def __init__(self, mvn: str = "mvn", timeout: int = 3600, threads: int = 2, env=None):
        self.mvn, self.timeout, self.threads = mvn, timeout, threads
        self.env = env or (lambda project: None)     # MavenRunner.env, to reuse per-project JAVA_HOME

    def run(self, module_dir: str | Path, test_class_fqn: str, target_classes: str,
            project: str = "") -> dict[str, set[Mutant]]:
        """Run PIT for one test class against `target_classes` (glob, e.g. 'org.apache.commons.cli.*')."""
        module_dir = Path(module_dir)
        pit_pom = module_dir / PIT_FILE
        pit_pom.write_text(add_pit_plugin((module_dir / "pom.xml").read_text(encoding="utf-8")), encoding="utf-8")
        report = module_dir / "target/pit-reports/mutations.xml"
        report.unlink(missing_ok=True)
        cmd = [self.mvn, "-q", "-B", "-f", PIT_FILE, "test-compile", f"org.pitest:pitest-maven:{PIT_VERSION}:mutationCoverage",
               f"-DtargetTests={test_class_fqn}", f"-DtargetClasses={target_classes}", "-DoutputFormats=XML",
               "-DtimestampedReports=false", "-DfullMutationMatrix=true", f"-Dthreads={self.threads}",
               "-DwithHistory=false", *SKIP_FLAGS]
        p = subprocess.run(cmd, cwd=module_dir, capture_output=True, text=True, timeout=self.timeout,
                           env=self.env(project))
        if not report.exists():
            raise RuntimeError("PIT produced no mutations.xml:\n" + (p.stdout + p.stderr)[-2000:])
        return parse_kill_matrix(report)


def package_of(java_src: str) -> str:
    m = re.search(r"^\s*package\s+([\w.]+)\s*;", java_src, re.M)
    return m.group(1) if m else ""
