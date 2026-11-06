"""`testdebt` CLI: subcommand dispatch and one real run of the no-LLM system on the demo project."""
import json

import pytest

from conftest import DEMO_TEST
from test_verify import GOOD
from testdebt import cli


@pytest.mark.parametrize("sub", ["run", "review"])
def test_help(sub, capsys):
    with pytest.raises(SystemExit) as e:
        cli.entry([sub, "--help"])
    assert e.value.code == 0 and "usage" in capsys.readouterr().out


def test_trace_usage_error():
    with pytest.raises(SystemExit, match="usage: testdebt trace"):
        cli.entry(["trace", "runs/x"])


def test_run_b0replay_without_subcommand_writes_a_report(demo, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    row = {"project": "demo", "module_dir": str(demo), "file": str(demo / DEMO_TEST), "class_name": "ShoppingCartTest",
           "method": "testTotals", "smells": ["AssertionRoulette"], "utr_refactored": GOOD}
    (tmp_path / "eval.jsonl").write_text(json.dumps(row) + "\n")
    cli.entry(["--system", "b0replay", "--eval", "eval.jsonl", "--skip-verify", "--run-id", "r1"])
    rep = json.loads((tmp_path / "runs/r1/report.json").read_text())
    assert rep["overall"]["tests"] == 1


def test_resume_with_other_settings_is_refused(tmp_path):
    d = tmp_path / "r"
    d.mkdir()
    (d / "state.jsonl").write_text("{}\n")
    (d / "config.json").write_text(json.dumps({"config": {"system": "s3"}, "split": "dev", "pit": False,
                                               "killset_gate": "on", "frozen": False}))
    cli.check_resume(d, "s3", "dev", False, "on", False)                 # same settings: resume is fine
    with pytest.raises(SystemExit, match="new --run-id"):
        cli.check_resume(d, "s3", "test", True, "on", True)
