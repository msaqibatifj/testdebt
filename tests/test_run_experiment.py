from experiments.run_experiment import _argv


def test_gap_mapping():
    full = _argv({"system": "s3", "split": "dev"}, {"gap1", "gap2", "gap6"}, 1, "r")
    assert "--pit" in full and "consensus" in full and "--policy" not in full
    abl = _argv({"system": "s3"}, {"gap1"}, 1, "r")
    assert "tsdetect" in abl and "fixed" in abl and "off" in abl
    assert "--detector" not in _argv({"system": "b1"}, {"gap2"}, 1, "r")


def test_summarize(tmp_path, monkeypatch):
    import json
    from experiments import run_all
    monkeypatch.setattr(run_all, "R", tmp_path)
    (tmp_path / "E3").mkdir()
    run_all.summarize("E3", {"s3": [{"a": 1, "x": "t"}, {"a": 3, "x": "t"}]})
    assert json.loads((tmp_path / "E3/summary.json").read_text())["s3"]["a"] == [2, 1.41]
