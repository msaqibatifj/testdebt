"""Optional: compile + run the demo with real javac/JUnit through the Verifier (no Maven needed).
Runs only when JUNIT_JAR and HAMCREST_JAR point at junit-4.13.x and hamcrest-core jars."""
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from conftest import DEMO_TEST
from test_verify import GOOD
from testdebt.contracts import TestRef
from testdebt.java_utils import find_method
from testdebt.verify import Verifier

J, H = os.environ.get("JUNIT_JAR"), os.environ.get("HAMCREST_JAR")


class JavacRunner:
    def run_test_class(self, module_dir, class_name, project="", test_file=None):
        out = tempfile.mkdtemp()
        srcs = [str(p) for p in Path(module_dir).rglob("*.java")]
        c = subprocess.run(["javac", "-cp", J, "-d", out, *srcs], capture_output=True, text=True)
        if c.returncode:
            return {"compiled": False, "passed": False, "log": c.stderr[-1500:]}
        r = subprocess.run(["java", "-cp", f"{J}:{H}:{out}", "org.junit.runner.JUnitCore", f"demo.{class_name}"],
                           capture_output=True, text=True)
        return {"compiled": True, "passed": r.returncode == 0, "log": r.stdout[-1500:]}


@pytest.mark.skipif(not (J and H), reason="set JUNIT_JAR and HAMCREST_JAR to run")
def test_real_compile_and_run(demo):
    f = demo / DEMO_TEST
    t = TestRef("demo", str(demo), str(f), "ShoppingCartTest", "testTotals")
    orig = find_method(f.read_text(), "testTotals")["text"]
    ok = Verifier(JavacRunner()).verify(t, orig, GOOD, [], ["AssertionRoulette"])
    assert ok.compiled and ok.passed
    broken = GOOD.replace("cart.total()", "cart.totl()", 1)
    bad = Verifier(JavacRunner()).verify(t, orig, broken, [], ["AssertionRoulette"])
    assert bad.compiled is False and "totl" in bad.problem
    wrong = GOOD.replace('"count", 3,', '"count", 4,')
    assert Verifier(JavacRunner()).verify(t, orig, wrong, [], []).passed is False


@pytest.mark.skipif(not (J and H), reason="set JUNIT_JAR and HAMCREST_JAR to run")
def test_fast_runner_javac_path(demo):
    """FastRunner per-test path (prepare() is replaced by a hand-built classpath)."""
    from testdebt.tools.fastrun import FastRunner
    classes, tclasses = demo / "target/classes", demo / "target/test-classes"
    subprocess.run(["javac", "-d", str(classes), *map(str, (demo / "src/main").rglob("*.java"))], check=True)
    subprocess.run(["javac", "-cp", f"{classes}:{J}", "-d", str(tclasses), *map(str, (demo / "src/test").rglob("*.java"))], check=True)
    fr = FastRunner()
    fr._prepared[str(demo.resolve())] = {"classes": str(classes), "test_classes": str(tclasses), "deps": f"{J}:{H}",
                                         "launcher": "", "vintage": [], "jupiter": False}
    f = demo / DEMO_TEST
    assert fr.check_baseline(demo, "ShoppingCartTest", "", f)[0]
    t = TestRef("demo", str(demo), str(f), "ShoppingCartTest", "testTotals")
    orig = find_method(f.read_text(), "testTotals")["text"]
    v = Verifier(fr)
    assert v.verify(t, orig, GOOD, [], []).passed is True
    bad = v.verify(t, orig, GOOD.replace("cart.total()", "cart.totl()", 1), [], [])
    assert bad.compiled is False and "totl" in bad.problem
    assert v.verify(t, orig, GOOD.replace('"count", 3,', '"count", 4,'), [], []).passed is False
