"""Emit pytest failure details as GitHub Actions annotations.

Public repositories' job logs need authentication to download, but check-run
annotations are readable anonymously.  This helper parses a pytest log and
prints ``::error`` workflow commands so the failing test names, assertions and
dependency context become visible through the Checks API.

Usage: python scripts/ci_annotate.py pytest.log
"""
from __future__ import annotations

import sys
from pathlib import Path


def _emit(kind: str, title: str, message: str) -> None:
    # GitHub workflow command: escape %, CR, LF
    safe = message.replace("%", "%25").replace("\r", "").replace("\n", "%0A")
    print(f"::{kind} title={title}::{safe[:900]}")


def main(argv: list[str]) -> int:
    path = Path(argv[0]) if argv else Path("pytest.log")
    if not path.exists():
        _emit("error", "annotate", f"{path} not found")
        return 1
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()

    for line in lines:
        if line.startswith(("FAILED ", "ERROR ")):
            _emit("error", "test-failure", line.strip())

    interesting = [
        line.strip()
        for line in lines
        if line.startswith(("E ", "E   "))
        or "Error" in line
        or "assert" in line
        or "UserWarning" in line
    ]
    for i, line in enumerate(interesting[-20:]):
        _emit("error", f"error-{i}", line)

    # last lines of the summary section, for context (workers/collection errors)
    tail = [line for line in lines if line.strip()][-15:]
    for i, line in enumerate(tail):
        _emit("notice", f"tail-{i}", line)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
