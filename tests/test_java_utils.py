from testdebt.java_utils import extract_test_methods, find_method, mask, module_dir, replace_method

SRC = '''class T {
    // @Test void commented() {}
    String s = "@Test void inString() {";

    @Test
    @DisplayName("x")
    public void a() { assertEquals(1, f()); }

    @ParameterizedTest
    @ValueSource(ints = {1, 2})
    void b(int x) {
        if (x > 0) { assertTrue(x > 0); }
    }
}
'''


def test_mask_keeps_length_and_hides_strings_comments():
    m = mask(SRC)
    assert len(m) == len(SRC) and "commented" not in m and "inString" not in m


def test_extract_includes_annotations_and_parameterized():
    ts = extract_test_methods(SRC)
    assert [t["name"] for t in ts] == ["a", "b"]
    assert ts[0]["text"].lstrip().startswith("@Test") and "@DisplayName" in ts[0]["text"]
    assert ts[1]["text"].rstrip().endswith("}") and "@ValueSource" in ts[1]["text"]


def test_replace_method_reindents():
    out = replace_method(SRC, "a", "@Test\npublic void a() {\n  assertEquals(\"m\", 1, f());\n}")
    assert '    public void a() {\n      assertEquals("m", 1, f());' in out
    assert find_method(out, "b") is not None


def test_module_dir(demo):
    assert module_dir(demo / "src/test/java/demo/ShoppingCartTest.java") == demo
