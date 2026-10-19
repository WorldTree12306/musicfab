from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

from musicfab.core.project import Note, Project, Track
from musicfab.core.audio import probe, load, resample


def test_probe_and_load(tmp_path: Path):
    p = tmp_path / "tone.wav"
    sr = 22050
    t = np.arange(sr) / sr
    sf.write(p, (0.3 * np.sin(2 * np.pi * 440 * t)).astype("float32"), sr)
    info = probe(p)
    assert info["sample_rate"] == sr
    assert info["duration"] and info["duration"] > 0.9
    data, sr2 = load(p)
    assert sr2 == sr and data.ndim == 1
    data2 = resample(data, sr, 44100)
    assert abs(len(data2) - 44100) <= 2


def test_project_roundtrip(tmp_path: Path):
    proj = Project.from_notes(
        [Note(0.0, 0.5, 60), Note(0.5, 1.0, 62)], name="demo", tempo=100
    )
    path = proj.save(tmp_path / "demo.mfproj.json")
    loaded = Project.load(path)
    assert loaded.summary()["notes"] == 2
    assert loaded.name == "demo"
    assert loaded.tracks[0].notes[1].pitch == 62


def test_cli_version():
    out = subprocess.run([sys.executable, "-m", "musicfab.cli", "version"],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert "musicfab" in out.stdout
