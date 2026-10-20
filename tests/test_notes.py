from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

FIX = Path(__file__).parent / "fixtures"


def _melody(tmp_path: Path) -> Path:
    src = FIX / "melody.wav"
    if src.exists():
        return src
    sr = 22050
    notes = [60, 62, 64, 65]
    chunks = []
    for p in notes:
        f = 440.0 * 2 ** ((p - 69) / 12)
        t = np.arange(int(sr * 0.5)) / sr
        env = np.minimum(1, t / 0.01) * np.minimum(1, (0.5 - t) / 0.05)
        chunks.append((0.3 * np.sin(2 * np.pi * f * t) * env).astype(np.float32))
        chunks.append(np.zeros(int(sr * 0.05), dtype=np.float32))
    path = tmp_path / "melody.wav"
    sf.write(path, np.concatenate(chunks), sr)
    return path


def test_detect_notes_and_template(tmp_path: Path):
    pytest.importorskip("basic_pitch")
    from musicfab.modules.notes import detect_notes, write_template

    src = _melody(tmp_path)
    notes = detect_notes(src)
    assert len(notes) >= 4
    tpl, detected = write_template(src, tmp_path / "edits.json")
    data = json.loads(tpl.read_text(encoding="utf-8"))
    assert len(data["notes"]) >= 4
    assert len(data["edits"]) == len(data["notes"])
    assert all(e["semitones"] == 0 for e in data["edits"])
    assert len(detected) == len(data["notes"])


def test_apply_pitch_edit_moves_only_that_note(tmp_path: Path):
    librosa = pytest.importorskip("librosa")
    pytest.importorskip("basic_pitch")
    from musicfab.modules.notes import apply_edits, detect_notes

    src = _melody(tmp_path)
    notes = detect_notes(src)
    assert len(notes) >= 2
    # shift the first note up an octave
    edits = tmp_path / "edits.json"
    edits.write_text(
        json.dumps({"edits": [{"index": 0, "semitones": 12}]}), encoding="utf-8"
    )
    out = tmp_path / "edited.wav"
    stats = apply_edits(src, edits, output=out, notes=notes)
    assert out.exists() and stats["edits_applied"] == 1

    y, sr = sf.read(str(out), dtype="float32")
    n0 = notes[0]
    seg = y[int(0.1 * sr): int(max(0.2, n0.end - 0.05) * sr)]
    f0 = librosa.yin(seg, fmin=100, fmax=1200, sr=sr)
    f0 = f0[np.isfinite(f0)]
    expected = notes[0].pitch + 12
    target = 440.0 * 2 ** ((expected - 69) / 12)
    assert np.median(f0) == pytest.approx(target, rel=0.10)


def test_duration_and_velocity_edits(tmp_path: Path):
    pytest.importorskip("basic_pitch")
    from musicfab.modules.notes import apply_edits, detect_notes

    src = _melody(tmp_path)
    notes = detect_notes(src)
    edits = tmp_path / "edits.json"
    edits.write_text(
        json.dumps(
            {"edits": [{"index": 0, "duration_scale": 1.5, "velocity_scale": 0.5, "start_shift": 0.05}]}
        ),
        encoding="utf-8",
    )
    out = tmp_path / "edited.wav"
    stats = apply_edits(src, edits, output=out, notes=notes)
    assert stats["edits_applied"] == 1
    info = sf.info(str(out))
    assert info.frames / info.samplerate >= 0.45
