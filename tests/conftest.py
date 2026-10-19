import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "data/samples/demo"
DEMO_TEST = "src/test/java/demo/ShoppingCartTest.java"


@pytest.fixture
def demo(tmp_path):
    """A throw-away copy of the demo Maven project."""
    d = tmp_path / "demo"
    shutil.copytree(DEMO, d)
    return d


class FakeLLM:
    """Returns canned replies in order; records prompts."""
    model = "fake"

    def __init__(self, replies):
        self.replies, self.prompts = list(replies), []

    def chat(self, messages, **kw):
        self.prompts.append(messages[-1]["content"])
        return {"text": self.replies.pop(0), "usage": {"total_tokens": 100}, "latency_s": 0.01, "cached": False}


class FakeMaven:
    """Pretends to run Maven: returns scripted results; records the file content it saw."""

    def __init__(self, results=None, test_file=None):
        self.results, self.seen, self.test_file = list(results or []), [], test_file

    def run_test_class(self, module_dir, class_name, project="", test_file=None):
        if self.test_file:
            self.seen.append(Path(self.test_file).read_text())
        return self.results.pop(0) if self.results else {"compiled": True, "passed": True, "log": ""}
