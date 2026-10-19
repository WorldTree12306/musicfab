from __future__ import annotations

import json
from pathlib import Path

import pytest

FIX = Path(__file__).parent / "fixtures"


@pytest.mark.slow
def test_demucs_separates_into_four_stems(tmp_path: Path):
    pytest.importorskip("demucs")
    audio = FIX / "chords.wav"
    if not audio.exists():
        pytest.skip("fixture chords.wav missing (run scripts/gen_test_audio.py)")
    from musicfab.modules.separate import separate

    manifest = separate(audio, model="htdemucs", output_dir=tmp_path / "stems")
    stems = manifest["stems"]
    assert set(stems) == {"drums", "bass", "other", "vocals"}
    for name, path in stems.items():
        p = Path(path)
        assert p.exists() and p.stat().st_size > 1000, f"empty stem {name}"
    saved = json.loads((tmp_path / "stems" / "stems.json").read_text(encoding="utf-8"))
    assert saved["sample_rate"] == 44100
