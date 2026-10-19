from __future__ import annotations

import json
from pathlib import Path

import pytest

FIX = Path(__file__).parent / "fixtures"


@pytest.mark.slow
def test_rip_workflow_end_to_end(tmp_path: Path):
    pytest.importorskip("demucs")
    pytest.importorskip("basic_pitch")
    audio = FIX / "chords.wav"
    if not audio.exists():
        pytest.skip("fixture chords.wav missing")

    from musicfab.modules.workflow import rip

    out = tmp_path / "rip"
    result = rip(audio, out, auto_tempo=True, quantize_beats=1)
    assert result["format"] == "musicfab-rip"
    assert set(result["stems"]) == {"drums", "bass", "other", "vocals"}
    assert result["daw_manifest"]["tracks"]
    assert (out / "daw" / "grid.json").exists() or (out / "daw" / "tracks.json").exists()
    assert (out / "rip.json").exists()

    # every stem should have a project + MIDI
    for name in result["stems"]:
        assert (out / "stems" / f"{name}.mfproj.json").exists()
        assert (out / "stems" / f"{name}.mid").exists()

    if result.get("score"):
        path = Path(result["score"])
        assert path.exists()
        if path.suffix == ".pdf":
            assert path.read_bytes()[:5] == b"%PDF-"


def test_rip_transcribe_only(tmp_path: Path):
    pytest.importorskip("basic_pitch")
    audio = FIX / "melody.wav"
    if not audio.exists():
        pytest.skip("fixture melody.wav missing")
    from musicfab.modules.workflow import rip

    out = tmp_path / "lite"
    result = rip(audio, out, separate_stems=False, auto_tempo=False, quantize_beats=1)
    assert result["mode"] == "transcribe"
    assert Path(result["project"]).exists()
    assert Path(result["midi"]).exists()
    assert Path(result["musicxml"]).exists()
    assert result["notes"] >= 8
    assert (out / "rip.json").exists()
