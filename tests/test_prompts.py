from testdebt.prompts import KnowledgeBase, build_context, parse_reply, utr_prompt


def test_parse_reply_strips_wrapper_and_collects_imports():
    reply = ("Here you go\n```java\npackage x;\nimport static org.junit.Assert.assertEquals;\n"
             "public class FooTest {\n  @Test\n  public void t() { assertEquals(\"m\", 1, 1); }\n}\n```")
    code, imports = parse_reply(reply)
    assert imports == ["import static org.junit.Assert.assertEquals;"]
    assert "class FooTest" not in code and "public void t()" in code and "package" not in code


def test_kb_lookup_and_utr_prompt(tmp_path):
    root = tmp_path / "refactoring/prompt_generation"
    for folder, text in [("smelltype", "DESC"), ("refactor_rules", "RULE"), ("checkpoints", "CHECK")]:
        (root / folder).mkdir(parents=True)
        (root / folder / "Assertion_Roulette.txt").write_text(text)
    kb = KnowledgeBase(tmp_path)
    assert kb.available() and kb.rule("AssertionRoulette") == "RULE"
    p = utr_prompt(kb, "@Test void t(){}", "ctx", ["AssertionRoulette"])
    assert "Assertion_Roulette" in p and "DESC" in p and "RULE" in p and "CHECK" in p and "Chain-of-Thought" in p


def test_context_removes_other_tests():
    src = "package p;\nclass A {\n  int f;\n  @Test void x() {}\n  @Test void y() {}\n  void helper() {}\n}"
    ctx = build_context(src, "A")
    assert "void x" not in ctx and "helper" in ctx and "int f" in ctx
