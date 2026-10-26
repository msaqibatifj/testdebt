"""Reference check for the paper (guidelines 5.1): run on the Overleaf export before the freeze.

  python3 -m testdebt.team.hasan.check_refs paper/refs.bib paper/*.tex [--offline]

Fails (exit 1) unless: there are at least 25 entries; every entry has a DOI, or a URL when the work has no DOI
(arXiv and the like); every DOI resolves at https://doi.org (skipped with --offline); every cited key is in the
.bib; every .bib entry is cited.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

MIN_REFS = 25
CITE = re.compile(r"\\(?:no)?cite[a-zA-Z]*\*?(?:\[[^\]]*\]){0,2}\{([^}]*)\}")
ENTRY = re.compile(r"@(\w+)\s*\{\s*([^,\s]+)\s*,(.*?)\n\}", re.S)


def field(body: str, name: str) -> str:
    m = re.search(rf"\b{name}\s*=\s*[{{\"](.+?)[}}\"]\s*,?\s*$", body, re.M | re.I)
    return m.group(1).strip() if m else ""


def parse_bib(text: str) -> dict[str, dict]:
    return {key: {"type": typ.lower(), "doi": field(body, "doi"), "url": field(body, "url")}
            for typ, key, body in ENTRY.findall(text) if typ.lower() not in ("comment", "string", "preamble")}


def cited(tex: str) -> set[str]:
    tex = re.sub(r"(?<!\\)%.*", "", tex)                   # commented-out citations do not count
    return {k.strip() for group in CITE.findall(tex) for k in group.split(",") if k.strip()}


def doi_resolves(doi: str) -> bool:
    import requests
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi)
    try:
        r = requests.head(f"https://doi.org/{doi}", allow_redirects=False, timeout=20)
    except requests.RequestException:
        return False
    return r.status_code in (200, 301, 302, 303, 307, 308)


def check(bib: str, texts: list[str], resolve=doi_resolves) -> list[str]:
    entries, keys = parse_bib(bib), set().union(*(cited(t) for t in texts)) if texts else set()
    problems = []
    if len(entries) < MIN_REFS:
        problems.append(f"{len(entries)} references; the guidelines ask for at least {MIN_REFS}")
    for k, e in sorted(entries.items()):
        if not e["doi"] and not e["url"]:
            problems.append(f"{k}: no doi and no url")
        elif e["doi"] and resolve and not resolve(e["doi"]):
            problems.append(f"{k}: doi {e['doi']} does not resolve")
    problems += [f"{k}: cited but not in the .bib" for k in sorted(keys - entries.keys())]
    problems += [f"{k}: in the .bib but never cited" for k in sorted(entries.keys() - keys)]
    return problems


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("bib")
    ap.add_argument("tex", nargs="+")
    ap.add_argument("--offline", action="store_true", help="do not resolve DOIs over the network")
    a = ap.parse_args()
    problems = check(Path(a.bib).read_text(encoding="utf-8"), [Path(t).read_text(encoding="utf-8") for t in a.tex],
                     resolve=None if a.offline else doi_resolves)
    print("\n".join(problems) if problems else f"references ok ({len(parse_bib(Path(a.bib).read_text()))} entries)")
    raise SystemExit(1 if problems else 0)


if __name__ == "__main__":
    main()
