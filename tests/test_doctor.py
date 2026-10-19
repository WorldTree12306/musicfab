from __future__ import annotations

import json
import subprocess
import sys

from musicfab.modules.doctor import collect


def test_doctor_reports_required_dependencies():
    report = collect()
    assert report["required_ok"] is True
    assert set(report["required"]) == {"numpy", "scipy", "soundfile"}
    assert all(item["available"] for item in report["required"].values())
    assert "features" in report and "transcribe" in report["features"]
    # this dev environment has the full stack; at minimum probe/transcribe work
    assert "probe" in report["ready"]
    assert report["python"].startswith("3.")


def test_doctor_cli_json():
    proc = subprocess.run(
        [sys.executable, "-m", "musicfab.cli", "doctor"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["required_ok"] is True
    assert "model_cache" in data and "dir" in data["model_cache"]
