import argparse

import pytest

from experiments.run_experiment import _argv
from testdebt import cli


def _ns(system):
    return argparse.Namespace(system=system, pit=False, killset_gate="on", detector=None, policy=None, memory=None)


def test_argv_passes_gaps():
    assert _argv({"system": "s3"}, {"gap1", "gap2"}, 1, "r")[-2:] == ["--gaps", "gap1,gap2"]
    assert _argv({"system": "s3"}, set(), 1, "r")[-2:] == ["--gaps", "none"]


def test_gap_mapping():
    full = _ns("s3"); cli.apply_gaps(full, {"gap1", "gap2", "gap6"})
    assert (full.pit, full.killset_gate, full.detector, full.policy) == (True, "on", "consensus", None)
    g1_off = _ns("s3"); cli.apply_gaps(g1_off, {"gap2", "gap6"})
    assert g1_off.pit and g1_off.killset_gate == "off"      # PIT still measures: the loss can be reported
    abl = _ns("s3"); cli.apply_gaps(abl, {"gap1"})
    assert (abl.detector, abl.policy, abl.memory) == ("tsdetect", "fixed", "off")
    b1 = _ns("b1"); cli.apply_gaps(b1, {"gap2"})
    assert b1.detector is None and b1.policy is None         # G2 and G6 only exist in s3


def test_unknown_gap():
    with pytest.raises(SystemExit):
        cli.apply_gaps(_ns("s3"), {"gap9"})
