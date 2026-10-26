"""JNose, the second smell detector (G2), method-level with the same isolation as tsDetect.

Each unit is the test class with every other test method removed (tools/tsdetect.keep_only), so both detectors
see identical input. JNose names its smells exactly like tsDetect's columns, so tsdetect.COLUMN_TO_SMELL maps both.
Setup: bash src/testdebt/team/hasan/get_jnose.sh   (jars into data/tools/jnose/; the Java wrapper compiles on first use)
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from ...tools.tsdetect import COLUMN_TO_SMELL, keep_only

WRAPPER = Path(__file__).parent / "jnose" / "JNoseMain.java"
JARS = ("jnose-core-0.9.0.jar", "javaparser-core-3.3.5.jar")


class JNose:
    def __init__(self, lib_dir: str | Path = "data/tools/jnose", java: str = "java", timeout: int = 600):
        self.lib, self.java, self.timeout = Path(lib_dir), java, timeout

    def available(self) -> bool:
        return all((self.lib / j).exists() for j in JARS)

    def _classpath(self) -> str:
        classes = self.lib / "classes"
        cp = ":".join(str((self.lib / j).resolve()) for j in JARS)
        if not (classes / "JNoseMain.class").exists() or WRAPPER.stat().st_mtime > (classes / "JNoseMain.class").stat().st_mtime:
            classes.mkdir(parents=True, exist_ok=True)
            p = subprocess.run(["javac", "-nowarn", "-cp", cp, "-d", str(classes), str(WRAPPER)],
                               capture_output=True, text=True, timeout=self.timeout)
            if p.returncode:
                raise RuntimeError("could not compile the JNose wrapper:\n" + p.stderr[-1500:])
        return cp + ":" + str(classes.resolve())

    def detect_units(self, units: list[dict]) -> dict[str, set[str]]:
        """units: [{'key', 'source', 'class_name', 'production_file'}] -> {key: set(smells)}, one JVM call."""
        if not units:
            return {}
        cp = self._classpath()
        with tempfile.TemporaryDirectory(prefix="jnose_") as tmp:
            lines, path_to_key = [], {}
            for i, u in enumerate(units):
                f = Path(tmp, str(i), f"{u['class_name']}.java")
                f.parent.mkdir()
                f.write_text(u["source"], encoding="utf-8")
                lines.append(f"{f.resolve()}\t{u.get('production_file', '')}")
                path_to_key[str(f.resolve())] = u["key"]
            Path(tmp, "input.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")
            try:
                p = subprocess.run([self.java, "-cp", cp, "JNoseMain", str(Path(tmp, "input.tsv"))],
                                   capture_output=True, text=True, timeout=self.timeout)
            except subprocess.TimeoutExpired:
                raise RuntimeError(f"JNose timed out after {self.timeout} s") from None
            if p.returncode:
                raise RuntimeError("JNose failed:\n" + (p.stdout + p.stderr)[-1500:])
            out: dict[str, set[str]] = {u["key"]: set() for u in units}
            for line in p.stdout.splitlines():
                parts = line.split("\t")
                if len(parts) == 3 and parts[0] in path_to_key:
                    if parts[1] == "ERROR":
                        raise RuntimeError(f"JNose could not parse {path_to_key[parts[0]]}: {parts[2][:300]}")
                    if parts[1] in COLUMN_TO_SMELL:
                        out[path_to_key[parts[0]]].add(COLUMN_TO_SMELL[parts[1]])
            return out

    def detect_source(self, source: str, class_name: str, keep: set[str], production_file: str = "") -> set[str]:
        return self.detect_units([{"key": "x", "source": keep_only(source, keep), "class_name": class_name,
                                   "production_file": production_file}])["x"]
