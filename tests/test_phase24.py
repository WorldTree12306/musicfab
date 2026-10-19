from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

FIX = Path(__file__).parent / "fixtures"


def _tone(dur: float = 2.0, sr: int = 22050, freq: float = 440.0) -> tuple[np.ndarray, int]:
    t = np.arange(int(sr * dur)) / sr
    env = np.minimum(1.0, t / 0.02) * np.minimum(1.0, (dur - t) / 0.05)
    y = (0.3 * np.sin(2 * np.pi * freq * t) * env).astype(np.float32)
    return y, sr


def _duration(path: Path) -> float:
    info = sf.info(str(path))
    return info.frames / info.samplerate


def test_practice_speed_and_loop(tmp_path: Path):
    from musicfab.modules.practice import practice

    y, sr = _tone(2.0)
    src = tmp_path / "in.wav"
    sf.write(src, y, sr)

    out = practice(src, tempo=0.5, output=tmp_path / "slow.wav")
    assert out.exists()
    # half speed -> about twice as long
    assert _duration(out) == pytest.approx(4.0, rel=0.25)
    meta = json.loads(Path(str(out) + ".practice.json").read_text(encoding="utf-8"))
    assert meta["tempo"] == 0.5
    assert meta["output_duration"] == pytest.approx(4.0, rel=0.25)

    looped = practice(src, loop=(0.5, 1.5), output=tmp_path / "loop.wav")
    assert _duration(looped) == pytest.approx(1.0, rel=0.1)


def test_pitch_shift_one_octave(tmp_path: Path):
    librosa = pytest.importorskip("librosa")
    from musicfab.modules.pitch import shift_audio

    y, sr = _tone(2.0, freq=220.0)
    src = tmp_path / "in.wav"
    sf.write(src, y, sr)

    out = shift_audio(src, semitones=12, output=tmp_path / "up.wav")
    assert out.exists()
    shifted, sr2 = sf.read(str(out), dtype="float32")
    assert sr2 == sr
    f0 = librosa.yin(shifted, fmin=80, fmax=1200, sr=sr)
    f0 = f0[np.isfinite(f0)]
    assert np.median(f0) == pytest.approx(440.0, rel=0.08)


def test_notation_midi_to_musicxml_and_svg(tmp_path: Path):
    from musicfab.core.export import to_midi
    from musicfab.core.project import Note, Project
    from musicfab.modules.notation import convert

    proj = Project.from_notes([Note(0.0, 0.5, 60), Note(0.5, 1.0, 64), Note(1.0, 1.6, 67)])
    midi = to_midi(proj, tmp_path / "x.mid")
    xml = convert(midi, output=tmp_path / "x.musicxml", fmt="musicxml")
    assert xml.exists() and xml.stat().st_size > 100

    from music21 import converter

    parsed = converter.parse(str(xml))
    assert len(parsed.flatten().notes) >= 2

    try:
        import verovio  # noqa: F401
    except ImportError:
        pytest.skip("verovio not installed")
    svg = convert(xml, output=tmp_path / "x.svg", fmt="svg")
    assert svg.exists() and "<svg" in svg.read_text(encoding="utf-8")[:2000]


@pytest.mark.parametrize("sample", ["Chords.gp5", "001_Funky_Guy.gp5"])
def test_tab_import_json_and_midi(tmp_path: Path, sample: str):
    pytest.importorskip("guitarpro")
    src = FIX / sample
    if not src.exists():
        pytest.skip(f"fixture {sample} not present (download from PyGuitarPro tests)")
    from musicfab.modules.tab import import_tab

    data_path = import_tab(src, output=tmp_path / "tab.json", fmt="json")
    data = json.loads(data_path.read_text(encoding="utf-8"))
    assert data["tracks"], "expected at least one track"
    assert any(t["notes"] for t in data["tracks"]), "expected notes"
    assert data["tempo"] > 0

    midi = import_tab(src, output=tmp_path / "tab.mid", fmt="midi")
    assert midi.exists() and midi.stat().st_size > 50
