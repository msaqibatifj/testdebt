from conftest import DEMO, DEMO_TEST
from testdebt.java_utils import extract_test_methods
from testdebt.smells import analyze_method, has_message


def test_demo_smells():
    got = {t["name"]: analyze_method(t["text"]) for t in extract_test_methods((DEMO / DEMO_TEST).read_text())}
    assert got["testTotals"] == {"AssertionRoulette", "DuplicateAssert", "MagicNumberTest"}
    assert got["testDiscounts"] == {"ConditionalTestLogic", "MagicNumberTest"}
    assert got["testEverything"] == {"EagerTest"}
    assert got["testSlowSync"] == {"SleepyTest", "RedundantPrint"}
    assert got["testLegacyPricing"] == {"IgnoredTest", "UnknownTest"}
    assert got["testEmptyCartIsEmpty"] == set()


def test_junit5_message_last_is_a_message_but_delta_is_not():
    arg = lambda s: (s, s)
    assert has_message("assertEquals", [arg("1"), arg("x"), arg('"msg"')])          # JUnit 5
    assert has_message("assertEquals", [arg('"msg"'), arg("1"), arg("x")])          # JUnit 4
    assert not has_message("assertEquals", [arg("1.0"), arg("x"), arg("0.01")])     # delta
    assert not has_message("assertTrue", [arg("x")])


def test_junit5_messages_remove_roulette():
    m = '@Test\nvoid t() {\n  assertTrue(a(), "a");\n  assertNull(b(), () -> "b");\n}'
    assert "AssertionRoulette" not in analyze_method(m)
