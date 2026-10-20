"""Regression tests for the second review batch (fixes B-G)."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf


# ---- B: Project.from_notes keeps audio/beats as top-level fields --------

def test_from_notes_keeps_audio_and_beats(tmp_path: Path):
    from musicfab.core.project import Note, Project

    proj = Project.from_notes(
        [Note(0.0, 0.5, 60)],
        name="x",
        tempo=100.0,
        audio={"path": "song.wav"},
        beats=[0.0, 0.6],
    )
    assert proj.audio == {"path": "song.wav"}
    assert proj.beats == [0.0, 0.6]

    saved = proj.save(tmp_path / "x.mfproj.json")
    loaded = Project.load(saved)
    assert loaded.audio["path"] == "song.wav"
    assert loaded.beats == [0.0, 0.6]
    assert "audio" not in loaded.meta and "beats" not in loaded.meta


def test_load_old_project_without_audio_field(tmp_path: Path):
    from musicfab.core.project import Project

    raw = {
        "format": "musicfab-project",
        "version": 1,
        "name": "legacy",
        "tempo": 90.0,
        "time_signature": "4/4",
        "beats": [0.0, 0.66],
        "tracks": [
            {
                "name": "main",
                "instrument": 0,
                "notes": [{"start": 0.0, "end": 0.5, "pitch": 60, "velocity": 80, "instrument": 0}],
            }
        ],
        "meta": {"backend": "basicpitch"},
    }
    path = tmp_path / "legacy.mfproj.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    proj = Project.load(path)
    assert proj.audio == {}  # legacy projects have no top-level audio
    assert proj.notes[0].pitch == 60


# ---- C: input robustness -------------------------------------------------

def test_load_rejects_nan_audio(tmp_path: Path):
    from musicfab.core.audio import load

    sr = 22050
    path = tmp_path / "nan.wav"
    sf.write(path, np.full(sr // 2, np.nan, dtype=np.float32), sr, subtype="FLOAT")
    with pytest.raises(ValueError, match="NaN/Inf"):
        load(path)


def test_write_rejects_nan(tmp_path: Path):
    from musicfab.core.audio import write

    with pytest.raises(ValueError, match="NaN/Inf"):
        write(tmp_path / "x.wav", np.array([np.nan, 0.5], dtype=np.float32), 22050)
    assert not (tmp_path / "x.wav").exists()


def test_load_project_note_error_mentions_path(tmp_path: Path):
    from musicfab.core.project import Project

    raw = {
        "format": "musicfab-project",
        "version": 1,
        "tempo": 120.0,
        "tracks": [
            {"name": "t", "notes": [{"start": 0.0, "end": 1.0, "pitch": 60, "bogus": 1}]}
        ],
    }
    path = tmp_path / "bad.mfproj.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match=r"bad\.mfproj\.json: track 0 note 0"):
        Project.load(path)


def test_load_project_rejects_bad_tempo_and_beats(tmp_path: Path):
    from musicfab.core.project import Project

    def _write(name: str, **overrides):
        raw = {
            "format": "musicfab-project",
            "version": 1,
            "tempo": 120.0,
            "tracks": [{"name": "t", "notes": []}],
        }
        raw.update(overrides)
        p = tmp_path / name
        p.write_text(json.dumps(raw), encoding="utf-8")
        return p

    with pytest.raises(ValueError, match="tempo must be positive"):
        Project.load(_write("t1.mfproj.json", tempo=0))
    with pytest.raises(ValueError, match=r"t2\.mfproj\.json.*strictly increasing"):
        Project.load(_write("t2.mfproj.json", beats=[0.0, 1.0, 0.5]))


# ---- D: CLI --speed alias + doctor feature mapping -----------------------

def test_practice_speed_alias_parses():
    from musicfab.cli import build_parser

    parser = build_parser()
    via_speed = parser.parse_args(["practice", "x.wav", "--speed", "0.5", "-o", "o.wav"])
    via_tempo = parser.parse_args(["practice", "x.wav", "--tempo", "0.5", "-o", "o.wav"])
    assert via_speed.tempo == via_tempo.tempo == 0.5


def test_doctor_features_match_backends():
    from musicfab.modules.doctor import collect

    features = collect()["features"]
    expected = {
        "probe", "transcribe", "pti", "practice", "shift", "notes",
        "beats", "separate", "notation", "pdf", "tab", "gui",
    }
    assert expected <= set(features), f"missing feature keys: {expected - set(features)}"
    # transcription requires the backend *and* its ONNX runtime
    assert features["transcribe"] == (
        importlib.util.find_spec("basic_pitch") is not None
        and importlib.util.find_spec("onnxruntime") is not None
    )
    assert features["pti"] == (importlib.util.find_spec("piano_transcription_inference") is not None)
    assert features["separate"] == (
        importlib.util.find_spec("torch") is not None and importlib.util.find_spec("demucs") is not None
    )


# ---- E: notes template detects once --------------------------------------

def test_notes_template_detects_once(tmp_path: Path, monkeypatch):
    import musicfab.modules.notes as notes_mod
    from musicfab.cli import build_parser, cmd_notes
    from musicfab.core.project import Note

    calls = {"n": 0}

    def fake_detect(audio, *, model="basicpitch"):
        calls["n"] += 1
        return [Note(0.0, 0.5, 60), Note(0.5, 1.0, 62)]

    monkeypatch.setattr(notes_mod, "detect_notes", fake_detect)

    args = build_parser().parse_args(["notes", str(tmp_path / "x.wav")])
    assert cmd_notes(args) == 0
    assert calls["n"] == 1, "template generation must run detection exactly once"
    assert (tmp_path / "x.edits.json").exists()


# ---- F: merge before quantization ----------------------------------------

def _fake_transcribe(monkeypatch, tmp_path: Path, fake_notes):
    import musicfab.modules.transcribe as tr

    audio = tmp_path / "x.wav"
    sf.write(audio, np.zeros(22050, dtype=np.float32), 22050)
    monkeypatch.setattr(tr, "_basicpitch_notes", fake_notes)
    return audio


def test_transcribe_merges_tail_before_sec_quantize(tmp_path: Path, monkeypatch):
    import musicfab.modules.transcribe as tr
    from musicfab.core.project import Note

    audio = _fake_transcribe(
        monkeypatch,
        tmp_path,
        lambda path, **kw: [Note(0.30, 0.452, 60), Note(0.461, 0.521, 60)],
    )
    # raw-domain merge (0.06 s tail) must happen before the 0.1 s grid snap;
    # snapping first would turn the tail into a 0.1 s "note" that no longer
    # qualifies as a release tail and stays separate
    proj = tr.transcribe(audio, model="basicpitch", quantize=0.1)
    notes = proj.notes
    assert len(notes) == 1, f"main+tail must merge into one note, got {[(n.start, n.end) for n in notes]}"
    assert notes[0].start == pytest.approx(0.3)
    assert notes[0].end == pytest.approx(0.5)


def test_transcribe_quantize_beats_merges_tail_and_keeps_reattack(tmp_path: Path, monkeypatch):
    import musicfab.modules.transcribe as tr
    from musicfab.core.project import Note

    beats = [round(i * 0.5, 4) for i in range(8)]

    audio = _fake_transcribe(
        monkeypatch,
        tmp_path,
        lambda path, **kw: [Note(0.40, 0.46, 60), Note(0.47, 0.52, 60)],
    )
    merged = tr.transcribe(audio, model="basicpitch", quantize_beats=1, beats=beats)
    assert len(merged.notes) == 1, "main note + short release tail must become one note"

    audio = _fake_transcribe(
        monkeypatch,
        tmp_path,
        lambda path, **kw: [Note(0.0, 0.2, 60), Note(0.25, 0.45, 60)],
    )
    reattack = tr.transcribe(audio, model="basicpitch", quantize_beats=1, beats=beats)
    assert len(reattack.notes) == 2, "fast same-pitch re-articulation must stay two notes"
    for n in reattack.notes:
        assert n.end > n.start
