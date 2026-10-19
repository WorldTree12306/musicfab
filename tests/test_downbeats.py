from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

FIX = Path(__file__).parent / "fixtures"


def _pattern_with_backbeat(tmp_path: Path) -> Path:
    """4/4 pattern: strong low thump on beat 1, high click on all beats."""
    sr = 22050
    bpm = 120
    beat = 60.0 / bpm
    bars = 8
    duration = bars * 4 * beat
    y = np.zeros(int(sr * duration) + sr, dtype=np.float32)

    def add(t: float, freq: float, dur: float, amp: float) -> None:
        n = int(sr * dur)
        env = np.linspace(1.0, 0.0, n, dtype=np.float32) ** 2
        sig = (amp * np.sin(2 * np.pi * freq * np.arange(n) / sr) * env).astype(np.float32)
        i = int(t * sr)
        y[i: i + n] += sig[: max(0, min(n, len(y) - i))]

    for k in range(bars * 4):
        t = k * beat
        add(t, 1000.0, 0.05, 0.3)  # every beat: high click
        if k % 4 == 0:
            add(t, 60.0, 0.20, 0.9)  # bar start: low thump
    path = tmp_path / "backbeat.wav"
    sf.write(path, y, sr)
    return path


def test_downbeat_phase_follows_low_frequency(tmp_path: Path):
    pytest.importorskip("librosa")
    from musicfab.modules.beats import detect_beats

    src = _pattern_with_backbeat(tmp_path)
    info = detect_beats(src, start_bpm=120)
    beats = info["beats"]
    downbeats = info["downbeats"]
    assert len(beats) >= 16, f"expected >=16 beats, got {len(beats)}"
    assert downbeats, "expected downbeats"
    # every downbeat must also be a beat
    assert all(any(abs(d - b) < 1e-3 for b in beats) for d in downbeats)
    # downbeats should be spaced by ~4 beats
    if len(downbeats) >= 2:
        diffs = np.diff(downbeats)
        assert np.median(diffs) == pytest.approx(info["tempo"] and 4 * 60.0 / info["tempo"], rel=0.2)

    # low-frequency energy at downbeats must exceed the other beats
    import librosa

    y, sr = librosa.load(str(src), sr=22050, mono=True)
    stft = np.abs(librosa.stft(y, n_fft=1024, hop_length=512))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=1024)
    low = stft[freqs < 150].sum(axis=0)

    def low_at(t: float) -> float:
        i = int(round(t * sr / 512))
        return float(low[max(0, i - 2): i + 3].max()) if len(low) else 0.0

    down_vals = [low_at(d) for d in downbeats]
    down_set = {round(d, 3) for d in downbeats}
    other_vals = [low_at(b) for b in beats if round(b, 3) not in down_set]
    assert np.mean(down_vals) > 1.5 * np.mean(other_vals)
    assert info["downbeat_confidence"] > 1.0
