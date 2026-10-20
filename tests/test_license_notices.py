"""Tests for scripts/collect_licenses.py (third-party notices generation)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "collect_licenses.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("collect_licenses", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_collect_licenses_writes_notices(tmp_path: Path):
    module = _load_module()
    out = tmp_path / "N.md"
    assert module.main(["-o", str(out)]) == 0
    text = out.read_text(encoding="utf-8")

    # core content markers
    assert "basic-pitch" in text
    assert "Demucs" in text
    assert "MIT" in text

    # markdown table: header + separator + one row per known package
    rows = [line for line in text.splitlines() if line.startswith("| ")]
    assert len(rows) > 10, f"expected a full package table, got {len(rows)} rows"

    # basic-pitch is installed in dev/CI: its row must carry a real version
    row = next(line for line in rows if line.startswith("| basic-pitch"))
    assert "not installed" not in row
    assert row.count("|") == 5  # | name | version | license | url |


def test_collect_licenses_tolerates_missing_packages(tmp_path: Path, monkeypatch):
    module = _load_module()

    def _missing(name):
        import importlib.metadata as metadata

        raise metadata.PackageNotFoundError(name)

    monkeypatch.setattr("importlib.metadata.version", _missing)
    out = tmp_path / "N2.md"
    assert module.main(["-o", str(out)]) == 0
    text = out.read_text(encoding="utf-8")

    # every package still listed, marked not installed, no exception raised
    assert "not installed" in text
    assert "basic-pitch" in text
    rows = [line for line in text.splitlines() if line.startswith("| ")]
    assert len(rows) > 10
