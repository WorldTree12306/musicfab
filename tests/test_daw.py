from __future__ import annotations

import json
from pathlib import Path

import pytest

FIX = Path(__file__).parent / "fixtures"


def test_daw_bundle_from_projects(tmp_path: Path):
    import mido

    from musicfab.core.project import Note, Project
    from musicfab.modules.daw import build_bundle

    src = tmp_path / "stems"
    src.mkdir()
    for name, pitch in (("drums", 36), ("bass", 40)):
        proj = Project.from_notes(
            [Note(0.0, 0.4, pitch), Note(0.5, 0.9, pitch + 2)], name=name, tempo=100
        )
        proj.beats = [0.0, 0.6, 1.2, 1.8]
        proj.save(src / f"{name}.mfproj.json")
    (src / "drums.wav").write_bytes(b"RIFF0000")
    (src / "bass.wav").write_bytes(b"RIFF0000")

    manifest = build_bundle(src, name="demo", tempo=100)
    bundle = src / "daw"
    assert (bundle / "demo.mid").exists()
    assert (bundle / "tracks.json").exists()
    assert (bundle / "README.md").exists()
    assert manifest["tempo"] == 100
    assert len(manifest["tracks"]) == 2
    assert all(t["notes"] == 2 for t in manifest["tracks"])
    assert manifest["tracks"][0]["audio"] and manifest["tracks"][0]["audio"].endswith(".wav")
    grid = json.loads(Path(manifest["grid"]).read_text(encoding="utf-8"))
    assert grid["beats"] == [0.0, 0.6, 1.2, 1.8]
    assert grid["beats_per_bar"] == 4
    assert grid["bars"] == [0.0]

    mid = mido.MidiFile(str(bundle / "demo.mid"))
    assert len(mid.tracks) == 3  # meta + 2 stem tracks
    names = [m.name for t in mid.tracks for m in t if m.type == "track_name"]
    assert "drums" in names and "bass" in names

    tempo_msgs = [m for t in mid.tracks for m in t if m.type == "set_tempo"]
    assert tempo_msgs and mido.tempo2bpm(tempo_msgs[0].tempo) == pytest.approx(100, rel=1e-3)


def test_daw_bundle_missing_projects(tmp_path: Path):
    from musicfab.modules.daw import build_bundle

    with pytest.raises(FileNotFoundError):
        build_bundle(tmp_path)
