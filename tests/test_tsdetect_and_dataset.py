import shutil

import pytest

from conftest import DEMO, DEMO_TEST, ROOT
from testdebt.eval.utr_dataset import read_reports
from testdebt.tools.tsdetect import TsDetect, keep_only, focal_class_file

JAR = ROOT / "data/utrefactor/detection/v3/TestSmellDetector.jar"


def test_keep_only_and_focal_file():
    src = (DEMO / DEMO_TEST).read_text()
    one = keep_only(src, {"testTotals"})
    assert "testTotals" in one and "testDiscounts" not in one and "class ShoppingCartTest" in one
    assert focal_class_file(DEMO / DEMO_TEST).endswith("ShoppingCart.java")


@pytest.mark.skipif(not JAR.exists() or not shutil.which("java"), reason="needs Java + UTRefactor clone")
def test_tsdetect_method_level_on_demo():
    res = TsDetect(JAR).detect_methods(DEMO / DEMO_TEST)
    assert "AssertionRoulette" in res["testTotals"] and "SleepyTest" in res["testSlowSync"]
    assert "AssertionRoulette" not in res["testEmptyCartIsEmpty"]


def test_read_utr_reports(tmp_path):
    d = tmp_path / "datasets/refactoring/exp/result/cli"
    d.mkdir(parents=True)
    (d / "7-1_FooTest_refactoring_report.txt").write_text(
        "File#1\n\nInput#1\n @Test\n public void testA() {\n  assertTrue(x);\n  assertTrue(y);\n }\n"
        "Smell List: ['Assertion_Roulette', 'Exception_Catching_Throwing']\n\nRefactor#1\n\nInput#2\n"
        " @Test\n public void testB() { }\nSmell List: ['Eager_Test']\n")
    items = read_reports(tmp_path, "cli")
    assert [(i["class_name"], i["method"]) for i in items] == [("FooTest", "testA"), ("FooTest", "testB")]
    assert items[0]["smells"] == ["AssertionRoulette", "ExceptionHandling"]
    assert "Refactor#" not in items[1]["original"]
