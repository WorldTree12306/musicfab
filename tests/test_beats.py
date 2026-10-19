from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

FIX = Path(__file__).parent / "fixtures"


def test_beat_grid_regular():
    from musicfab.modules.beats import beat_grid

    grid = beat_grid(120.0, 2.0)
    assert len(grid) == 5
    assert grid[:3] == [0.0, 0.5, 1.0]


def test_detect_beats_on_click_track(tmp_path: Path):
    pytest.importorskip("librosa")
    from musicfab.modules.beats import detect_beats

    sr = 22050
    bpm = 120
    period = 60.0 / bpm
    duration = 4.0
    y = np.zeros(int(sr * duration), dtype=np.float32)
    click = (0.8 * np.sin(2 * np.pi * 1000 * np.arange(int(sr * 0.02)) / sr)).astype(np.float32)
    for t in np.arange(0, duration - 0.05, period):
        i = int(t * sr)
        y[i: i + len(click)] += click
    src = tmp_path / "clicks.wav"
    sf.write(src, y, sr)

    info = detect_beats(src, start_bpm=bpm)
    assert 60 <= info["tempo"] <= 240
    assert len(info["beats"]) >= 4
    assert all(0 <= b <= duration for b in info["beats"])
    assert info["time_signature"] == "4/4"
    # beats should be roughly one period apart
    diffs = np.diff(info["beats"])
    assert np.median(diffs) == pytest.approx(period, rel=0.25)


def test_transcribe_auto_tempo_cli(tmp_path: Path):
    pytest.importorskip("basic_pitch")
    src = FIX / "melody.wav"
    if not src.exists():
        pytest.skip("fixture melody.wav missing")
    out = tmp_path / "auto.mfproj.json"
    proc = subprocess.run(
        [sys.executable, "-m", "musicfab.cli", "transcribe", str(src), "--auto-tempo", "--save", str(out)],
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["tempo"] > 0
    assert data["beats"], "auto tempo should populate beats"
    assert data["time_signature"].endswith("/4")


def test_practice_loop_beats(tmp_path):
    pytest.importorskip("librosa")
    src = FIX / "drums.wav"
    if not src.exists():
        pytest.skip("fixture drums.wav missing")
    from musicfab.modules.practice import practice

    out = practice(src, beat_loop=2, output=tmp_path / "loop.wav")
    assert out.exists()
    info = sf.info(str(out))
    assert 0.3 < info.frames / info.samplerate < 8.0
    meta = json.loads(Path(str(out) + ".practice.json").read_text(encoding="utf-8"))
    assert meta["beat_loop"] == 2
    assert meta["loop"] and meta["loop"][1] > meta["loop"][0]


def test_detect_beats_silence_falls_back(tmp_path):
    from musicfab.modules.beats import detect_beats

    sr = 22050
    src = tmp_path / "silence.wav"
    sf.write(src, np.zeros(sr * 2, dtype=np.float32), sr)
    info = detect_beats(src, start_bpm=100)
    assert info["tempo"] == 100.0
    assert info["beats"] == []


def test_transcribe_quantize_beats_snaps_to_grid():
    pytest.importorskip("basic_pitch")
    src = FIX / "melody.wav"
    if not src.exists():
        pytest.skip("fixture melody.wav missing")
    from musicfab.modules.transcribe import transcribe

    beats = [round(i * 0.5, 4) for i in range(40)]  # 120 BPM grid
    proj = transcribe(src, model="basicpitch", tempo=120, beats=beats, quantize_beats=1)
    assert proj.notes
    for note in proj.notes:
        assert abs(note.start / 0.5 - round(note.start / 0.5)) < 1e-3, f"{note.start} not on grid"


def test_practice_loop_bars(tmp_path):
    pytest.importorskip("librosa")
    src = FIX / "drums.wav"
    if not src.exists():
        pytest.skip("fixture drums.wav missing")
    from musicfab.modules.practice import practice

    out = practice(src, bar_loop=1, output=tmp_path / "bar.wav")
    assert out.exists()
    info = sf.info(str(out))
    duration = info.frames / info.samplerate
    assert 0.5 < duration < 8.0
    meta = json.loads(Path(str(out) + ".practice.json").read_text(encoding="utf-8"))
    assert meta["bar_loop"] == 1
    assert meta["beats_per_bar"] == 4
