import subprocess

import pytest

from testdebt.team.gulsher.robustness import RestoreCheck, redact
from testdebt.trace import Trace


def test_redact_keys_and_env_values(monkeypatch):
    monkeypatch.setenv("CEREBRAS_API_KEY", "abc123secretvalue")
    s = redact("Authorization: Bearer xyz.789 key=csk-abcdefgh12345678 raw abc123secretvalue ok")
    assert "xyz" not in s and "csk-" not in s and "abc123" not in s and s.endswith("ok")


def test_no_key_reaches_a_trace_file(tmp_path, monkeypatch):
    monkeypatch.setenv("CEREBRAS_API_KEY", "csk-thisisnotarealkey99")
    tr = Trace(tmp_path, "p:C#m")
    tr.event("refactor", "llm_call", input={"headers": {"Authorization": "Bearer csk-thisisnotarealkey99"}},
             output="x" * 5000 + "csk-thisisnotarealkey99")
    text = "".join(p.read_text() for p in tmp_path.rglob("*") if p.is_file())
    assert "thisisnotarealkey" not in text


def test_restore_check_stops_on_a_modified_checkout(tmp_path):
    git = lambda *a: subprocess.run(["git", "-C", str(tmp_path), *a], capture_output=True, check=True)
    git("init", "-q"); (tmp_path / "A.java").write_text("a")
    git("add", "."); git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "x")
    rc = RestoreCheck()
    rc.check(str(tmp_path))
    (tmp_path / "new.txt").write_text("untracked files are fine")
    rc.check(str(tmp_path))
    (tmp_path / "A.java").write_text("b")
    with pytest.raises(SystemExit, match="left modified"):
        rc.check(str(tmp_path))


def test_dirty_lists_checkouts_with_tracked_changes(tmp_path):
    git = lambda *a: subprocess.run(["git", "-C", str(tmp_path), *a], capture_output=True, check=True)
    git("init", "-q"); (tmp_path / "A.java").write_text("a")
    git("add", "."); git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "x")
    assert RestoreCheck.dirty([str(tmp_path)]) == []
    (tmp_path / "A.java").write_text("patched by a killed run")
    assert RestoreCheck.dirty([str(tmp_path), str(tmp_path)]) == [str(tmp_path)]
