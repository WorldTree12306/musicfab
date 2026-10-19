"""Regression tests for issues found in the GLM code review."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

FIX = Path(__file__).parent / "fixtures"


def _melody(tmp_path: Path, notes=(60, 62, 64, 65), sr: int = 22050) -> Path:
    src = FIX / "melody.wav"
    if src.exists():
        return src
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


def test_project_tempo_and_time_signature_roundtrip(tmp_path: Path):
    import mido

    from musicfab.core.export import to_midi
    from musicfab.core.project import Note, Project

    proj = Project.from_notes([Note(0.0, 0.5, 60)], name="t", tempo=90, time_signature="3/4")
    assert proj.tempo == 90.0 and proj.time_signature == "3/4"
    saved = proj.save(tmp_path / "p.mfproj.json")
    loaded = Project.load(saved)
    assert loaded.tempo == 90.0
    assert loaded.time_signature == "3/4"

    midi = to_midi(proj, tmp_path / "p.mid")
    mid = mido.MidiFile(str(midi))
    messages = [msg for track in mid.tracks for msg in track]
    tempos = [m for m in messages if m.type == "set_tempo"]
    sigs = [m for m in messages if m.type == "time_signature"]
    assert tempos and mido.tempo2bpm(tempos[0].tempo) == pytest.approx(90.0, rel=1e-3)
    assert sigs and (sigs[0].numerator, sigs[0].denominator) == (3, 4)


def test_merge_same_pitch_keeps_reattack():
    from musicfab.core.project import Note
    from musicfab.modules.transcribe import _merge_same_pitch

    notes = [Note(0.0, 0.10, 60), Note(0.13, 0.23, 60)]
    merged = _merge_same_pitch(notes)
    assert len(merged) == 2, "separate re-articulations must not be merged"

    overlapping = [Note(0.0, 0.10, 60), Note(0.05, 0.20, 60)]
    assert len(_merge_same_pitch(overlapping)) == 1


def test_notes_json_array_form_and_duration_validation(tmp_path: Path):
    pytest.importorskip("basic_pitch")
    from musicfab.modules.notes import apply_edits, detect_notes

    src = _melody(tmp_path)
    notes = detect_notes(src)
    # plain JSON array (no wrapper object) must work
    edits = tmp_path / "edits.json"
    edits.write_text(json.dumps([{"index": 0, "semitones": 2}]), encoding="utf-8")
    stats = apply_edits(src, edits, output=tmp_path / "o1.wav", notes=notes)
    assert stats["edits_applied"] == 1

    # out-of-range duration_scale must be reported, not silently applied
    edits.write_text(json.dumps({"edits": [{"index": 1, "duration_scale": 0.0}]}), encoding="utf-8")
    stats = apply_edits(src, edits, output=tmp_path / "o2.wav", notes=notes)
    assert stats["edits_applied"] == 0
    assert any("duration_scale" in e for e in stats["errors"])


def test_note_edit_preserves_original_start_time(tmp_path: Path):
    pytest.importorskip("basic_pitch")
    from musicfab.modules.notes import apply_edits, detect_notes

    src = _melody(tmp_path)
    notes = detect_notes(src)
    assert notes
    edits = tmp_path / "edits.json"
    edits.write_text(json.dumps({"edits": [{"index": 0, "semitones": 12}]}), encoding="utf-8")
    out = apply_edits(src, edits, output=tmp_path / "shifted.wav", notes=notes)
    assert out["edits_applied"] == 1

    y0, sr = sf.read(str(src), dtype="float32")
    y1, sr1 = sf.read(str(Path(out["output"])), dtype="float32")
    assert sr1 == sr

    def rms(seg):
        return float(np.sqrt(np.mean(np.square(seg), dtype=np.float64))) if len(seg) else 0.0

    a = notes[0].start
    win0 = y0[int(a * sr): int((a + 0.06) * sr)]
    win1 = y1[int(a * sr): int((a + 0.06) * sr)]
    assert rms(win1) > 0.3 * rms(win0), "edited note must still start at its original time"


def test_practice_beat_loop_validation(tmp_path: Path):
    pytest.importorskip("librosa")
    from musicfab.modules.practice import practice

    src = _melody(tmp_path)
    with pytest.raises(ValueError):
        practice(src, beat_loop=0, output=tmp_path / "x.wav")
    with pytest.raises(ValueError):
        practice(src, beat_loop=2, beat_start=-1, output=tmp_path / "x.wav")


def test_tab_renderer_reports_clamped_strings_and_bars():
    from musicfab.modules.tab import tab_to_svg

    data = {
        "title": "synthetic",
        "tempo": 120,
        "time_signature": "4/4",
        "measures": [
            {"index": 0, "start": 0.0, "duration": 2.0, "time_signature": "4/4"},
            {"index": 1, "start": 2.0, "duration": 2.0, "time_signature": "4/4"},
        ],
        "tracks": [
            {
                "name": "gtr",
                "strings": [64, 59, 55, 50, 45, 40],
                "notes": [
                    {"start": 0.0, "duration": 0.25, "pitch": 64, "string": 1, "fret": 0,
                     "bar": 0, "bar_pos": 0.0},
                    {"start": 2.5, "duration": 0.25, "pitch": 40, "string": 99, "fret": 5,
                     "bar": 1, "bar_pos": 0.25},  # out-of-range string
                    {"start": 2.75, "duration": 0.25, "pitch": 40, "string": 6, "fret": 3,
                     "bar": 1, "bar_pos": 0.375},
                ],
            }
        ],
    }
    svg = tab_to_svg(data, max_bars=1)
    assert "skipped" in svg and "bars not shown" in svg
    # only one measure is shown -> 2 vertical bar lines
    assert svg.count("stroke='#888'") == 2


def test_detect_beats_octave_not_doubled(tmp_path: Path):
    pytest.importorskip("librosa")
    from musicfab.modules.beats import detect_beats

    sr = 22050
    bpm = 60
    period = 60.0 / bpm
    dur = 8.0
    y = np.zeros(int(sr * dur), dtype=np.float32)
    click = (0.8 * np.sin(2 * np.pi * 900 * np.arange(int(sr * 0.03)) / sr)).astype(np.float32)
    for t in np.arange(0, dur - 0.1, period):
        i = int(t * sr)
        y[i: i + len(click)] += click
    src = tmp_path / "slow.wav"
    sf.write(src, y, sr)
    info = detect_beats(src, start_bpm=120)
    assert 45 <= info["tempo"] <= 80, f"expected ~60 BPM, got {info['tempo']}"


def test_tab_sustain_line_across_measure():
    from musicfab.modules.tab import tab_to_svg

    data = {
        "tempo": 120,
        "time_signature": "4/4",
        "measures": [
            {"index": 0, "start": 0.0, "duration": 2.0, "time_signature": "4/4"},
            {"index": 1, "start": 2.0, "duration": 2.0, "time_signature": "4/4"},
        ],
        "tracks": [
            {
                "name": "gtr",
                "strings": [64, 59, 55, 50, 45, 40],
                "notes": [
                    {"start": 1.0, "duration": 2.0, "pitch": 64, "string": 1, "fret": 3,
                     "bar": 0, "bar_pos": 0.5},
                ],
            }
        ],
    }
    svg = tab_to_svg(data, max_bars=2)
    assert "class='tie'" in svg
