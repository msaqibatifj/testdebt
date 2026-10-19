from conftest import DEMO_TEST, FakeMaven
from testdebt.contracts import TestRef
from testdebt.java_utils import find_method
from testdebt.verify import Verifier, add_imports, patch_source, static_checks

GOOD = ('@Test\npublic void testTotals() {\n    ShoppingCart cart = new ShoppingCart();\n'
        '    cart.add(new Item("pen", 250), 3);\n    final int expectedTotal = 750;\n'
        '    assertEquals("total", expectedTotal, cart.total());\n    assertEquals("count", 3, cart.itemCount());\n'
        '    assertEquals("total again", expectedTotal, cart.total());\n    assertTrue("has pen", cart.hasItem("pen"));\n}')


def ref(demo):
    return TestRef("demo", str(demo), str(demo / DEMO_TEST), "ShoppingCartTest", "testTotals")


def test_static_checks():
    orig = "@Test\nvoid t() { assertTrue(a); assertTrue(b); }"
    assert static_checks(orig, "@Test\nvoid t() { assertTrue(a, \"x\"); assertTrue(b, \"y\"); }")[0]
    ok, why, _ = static_checks(orig, "@Test\nvoid t() { assertTrue(a, \"x\"); }")
    assert not ok and "assertions dropped" in why
    assert not static_checks(orig, "@Test\nvoid t() { assertTrue(a);")[0]


def test_patch_and_imports(demo):
    src = (demo / DEMO_TEST).read_text()
    out = patch_source(src, "testTotals", GOOD, ["import java.util.List;"])
    assert "expectedTotal" in out and "import java.util.List;" in out
    assert find_method(out, "testDiscounts") is not None
    assert add_imports(out, ["import java.util.List;"]) == out           # no duplicates


def test_verifier_restores_file_even_when_build_fails(demo):
    f = demo / DEMO_TEST
    before = f.read_text()
    mvn = FakeMaven([{"compiled": False, "passed": False, "log": "[ERROR] cannot find symbol"}], test_file=f)
    t = ref(demo)
    orig = find_method(before, "testTotals")["text"]
    rep = Verifier(mvn).verify(t, orig, GOOD, [], ["AssertionRoulette"])
    assert rep.sane and rep.compiled is False and "compilation failed" in rep.problem
    assert "expectedTotal" in mvn.seen[0]          # Maven saw the patched file
    assert f.read_text() == before                  # and the project is restored


def test_verifier_smells_after_with_rules_fallback(demo):
    f = demo / DEMO_TEST
    t = ref(demo)
    orig = find_method(f.read_text(), "testTotals")["text"]
    rep = Verifier(FakeMaven()).verify(t, orig, GOOD, [], ["AssertionRoulette"])
    assert rep.ok and "AssertionRoulette" not in rep.smells_after


def test_missing_assert_imports():
    from testdebt.verify import missing_assert_imports
    j5 = "import static org.junit.jupiter.api.Assertions.assertTrue;\nclass A {}"
    blk = "@Test void t() { assertDoesNotThrow(() -> x()); assertTrue(y); }"
    assert missing_assert_imports(j5, blk) == ["import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;"]
    j4 = "import static org.junit.Assert.assertTrue;\nclass A {}"
    assert missing_assert_imports(j4, blk) == []                     # JUnit 4 has no assertDoesNotThrow
    assert missing_assert_imports(j4, "@Test void t() { assertEquals(1, x); }") == ["import static org.junit.Assert.assertEquals;"]
    assert missing_assert_imports("import static org.junit.Assert.*;", blk) == []


def test_parameterized_rewrite_is_not_assertion_loss():
    from testdebt.verify import missing_param_imports
    orig = "@Test\nvoid t() { assertEquals(1, f(1)); assertEquals(2, f(2)); }"
    new = "@ParameterizedTest\n@CsvSource({\"1,1\", \"2,2\"})\nvoid t(int a, int b) { assertEquals(b, f(a), \"f\"); }"
    assert static_checks(orig, new)[0]
    imps = missing_param_imports("import org.junit.jupiter.api.Test;", new)
    assert "import org.junit.jupiter.params.ParameterizedTest;" in imps
    assert "import org.junit.jupiter.params.provider.CsvSource;" in imps
