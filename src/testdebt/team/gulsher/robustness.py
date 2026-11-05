"""Run safety: the project checkouts must be left as found, and no secret may reach a trace file."""
from __future__ import annotations

import os
import re
import subprocess

_KEY_PATTERNS = [r"Bearer\s+[\w.\-]+", r"\bcsk-[\w]{8,}", r"\bsk-[\w\-]{16,}", r"\bgh[pousr]_[\w]{20,}"]


def redact(text: str) -> str:
    """Strip API keys and Authorization values; also any value of a *_KEY / *_TOKEN environment variable."""
    for v in (v for k, v in os.environ.items() if re.search(r"(KEY|TOKEN|SECRET)$", k) and len(v) >= 8):
        text = text.replace(v, "[REDACTED]")
    for p in _KEY_PATTERNS:
        text = re.sub(p, "[REDACTED]", text)
    return text


class RestoreCheck:
    """After every test, each project checkout must have the same tracked-file state as before the run.

    The Verifier always restores the test file; this catches anything else (a crash between patch and
    restore, a tool writing into tracked files). Compares against the first snapshot, so a checkout that
    already had local changes is not reported."""

    def __init__(self):
        self.first: dict[str, str] = {}

    @staticmethod
    def _status(directory: str) -> str:
        return subprocess.run(["git", "-C", directory, "status", "--porcelain", "--untracked-files=no"],
                              capture_output=True, text=True).stdout

    def check(self, module_dir: str) -> None:
        now = self._status(module_dir)
        before = self.first.setdefault(module_dir, now)
        if now != before:
            raise SystemExit(f"STOP: {module_dir} was left modified after a test (git status changed):\n{now}"
                             "Restore it (git -C <dir> checkout -- .) before resuming the run.")
