"""Extra paired comparisons for the paper (post-run, no LLM): matched-target G6 and G2 comparisons.

s3 targets the consensus smells (G2 on), b1/b2 target all tsDetect smells, so `s3 vs b1` mixes G2 and G6.
These pairs separate them. Writes results/E4/paired_extra.json.   python3 scripts/paired_extra.py
"""
import json
from pathlib import Path

from testdebt.team.gulsher.experiments import _paired
from testdebt.team.hasan.stats import holm

PAIRS = {  # name: (system A runs, system B runs, flag)
    "G6 matched targets: s3-G2 vs b1 (accepted and safe)": (["E5_s3-G2_s1"], ["E2_b1_s1"], "safe"),
    "G6 matched targets: s3-G2 vs b2 (accepted and safe)": (["E5_s3-G2_s1"], ["E2_b2_s1"], "safe"),
    "G6 inside S3: s3 vs s3-G6 (accepted and safe)": (["E3_s3_s1"], ["E5_s3-G6_s1"], "safe"),
    "G2 inside S3: s3 vs s3-G2 (accepted and safe)": (["E3_s3_s1"], ["E5_s3-G2_s1"], "safe"),
    "G2 inside S3: s3 vs s3-G2 (accepted)": (["E3_s3_s1"], ["E5_s3-G2_s1"], "accepted"),
}
out = {k: _paired(a, b, f) for k, (a, b, f) in PAIRS.items()}
ps = holm([v["mcnemar"]["p"] for v in out.values()])
for (k, v), p in zip(out.items(), ps):
    v["p_holm"] = round(p, 5)
Path("results/E4/paired_extra.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
