from __future__ import annotations

from pathlib import Path

import pytest


def test_basicpitch_transcribes_monophonic_melody(tmp_path: Path):
    pytest.importorskip("basic_pitch")
    from musicfab.modules.transcribe import transcribe

    audio = Path(__file__).parent / "fixtures" / "melody.wav"
    if not audio.exists():
        pytest.skip("fixture melody.wav missing (run scripts/gen_test_audio.py)")

    midi = tmp_path / "melody.mid"
    proj = transcribe(audio, model="basicpitch", output_midi=midi)
    notes = proj.notes
    assert len(notes) >= 8, f"expected >=8 notes, got {len(notes)}"
    pitches = [n.pitch for n in notes]
    # C major scale melody (60..72) — allow a couple of octave/neighbour errors
    assert pitches[0] == pytest.approx(60, abs=1)
    assert max(pitches) >= 71
    for n in notes:
        assert n.end > n.start
        assert 21 <= n.pitch <= 108
    assert midi.exists() and midi.stat().st_size > 100
    assert proj.summary()["notes"] == len(notes)


def test_quantize_snaps_notes(tmp_path: Path):
    pytest.importorskip("basic_pitch")
    from musicfab.modules.transcribe import transcribe

    audio = Path(__file__).parent / "fixtures" / "melody.wav"
    if not audio.exists():
        pytest.skip("fixture melody.wav missing")
    proj = transcribe(audio, model="basicpitch", quantize=0.25)
    for n in proj.notes:
        assert abs(n.start / 0.25 - round(n.start / 0.25)) < 1e-6
