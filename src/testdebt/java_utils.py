"""Text-level Java helpers: mask comments/strings, find JUnit test methods, replace a method, find the module pom."""
from __future__ import annotations

import re
from pathlib import Path


def mask(src: str) -> str:
    """Same length as src, with comments and string/char contents blanked (quotes and newlines kept)."""
    out, i, n = list(src), 0, len(src)
    while i < n:
        if src.startswith("//", i):
            j = src.find("\n", i)
            j = n if j < 0 else j
            for k in range(i, j):
                out[k] = " "
            i = j
        elif src.startswith("/*", i):
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            for k in range(i, j):
                if out[k] != "\n":
                    out[k] = " "
            i = j
        elif src.startswith('"""', i):  # Java text block
            j = src.find('"""', i + 3)
            j = n if j < 0 else j
            for k in range(i + 3, j):
                if out[k] != "\n":
                    out[k] = " "
            i = j + 3
        elif src[i] in "\"'":
            q, j = src[i], i + 1
            while j < n and src[j] != q and src[j] != "\n":
                j += 2 if src[j] == "\\" else 1
            for k in range(i + 1, min(j, n)):
                out[k] = " "
            i = j + 1
        else:
            i += 1
    return "".join(out)


def match_close(m: str, i: int, op: str, cl: str) -> int:
    depth = 0
    for k in range(i, len(m)):
        if m[k] == op:
            depth += 1
        elif m[k] == cl:
            depth -= 1
            if depth == 0:
                return k
    return -1


def split_args(text: str, m: str, a: int, b: int) -> list[tuple[str, str]]:
    """Top-level comma split of text[a:b]; returns [(original, masked)]."""
    parts, depth, last = [], 0, a
    for k in range(a, b):
        c = m[k]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == "," and depth == 0:
            parts.append((text[last:k].strip(), m[last:k].strip()))
            last = k + 1
    tail = (text[last:b].strip(), m[last:b].strip())
    if tail[0]:
        parts.append(tail)
    return parts


_TEST_ANN = re.compile(r"@(?:org\.junit\.(?:jupiter\.api\.)?)?(Test|ParameterizedTest|RepeatedTest)\b")
_VOID = re.compile(r"\bvoid\s+(\w+)\s*\(")
_ANN_LINE = re.compile(r"\s*(?:@[\w.]+\s*(?:\([^;]*\))?\s*)+")


def extract_test_methods(src: str) -> list[dict]:
    """[{'name','text','start','end'}] for every @Test/@ParameterizedTest/@RepeatedTest method (annotations included)."""
    m, out, seen = mask(src), [], set()
    for t in _TEST_ANN.finditer(m):
        mm = _VOID.search(m, t.end())
        if not mm or mm.start() in seen:
            continue
        pc = match_close(m, mm.end() - 1, "(", ")")
        bo = m.find("{", pc) if pc >= 0 else -1
        if bo < 0 or ";" in m[pc:bo]:      # abstract/interface method
            continue
        end = match_close(m, bo, "{", "}")
        if end < 0:
            continue
        seen.add(mm.start())
        start = src.rfind("\n", 0, t.start()) + 1
        while start > 1:                    # pull in annotation-only lines above (not a previous one-line method)
            pls = src.rfind("\n", 0, start - 1) + 1
            if _ANN_LINE.fullmatch(m[pls:start - 1]):
                start = pls
            else:
                break
        out.append({"name": mm.group(1), "text": src[start:end + 1], "start": start, "end": end + 1})
    return out


def find_method(src: str, name: str) -> dict | None:
    hits = [t for t in extract_test_methods(src) if t["name"] == name]
    return hits[0] if len(hits) == 1 else None


def replace_method(src: str, name: str, new_text: str) -> str | None:
    """Replace test method `name` (unique) with new_text, re-indented to the original indentation."""
    t = find_method(src, name)
    if t is None:
        return None
    indent = re.match(r"[ \t]*", src[t["start"]:]).group(0)
    lines = new_text.strip("\n").splitlines()
    base = min((len(l) - len(l.lstrip()) for l in lines if l.strip()), default=0)
    body = "\n".join((indent + l[base:]) if l.strip() else "" for l in lines)
    return src[:t["start"]] + body + src[t["end"]:]


def module_dir(test_file: str | Path) -> Path | None:
    """Nearest ancestor directory that contains a pom.xml (the Maven module that owns the test)."""
    p = Path(test_file).parent          # keep relative paths relative (portable eval files)
    for d in [p, *p.parents]:
        if (d / "pom.xml").exists():
            return d
    return None
