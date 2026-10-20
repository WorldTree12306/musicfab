"""Regression tests for review batch 2.

#3 Basic Pitch model cache + shared mixture tempo
#2 to_musicxml direct music21 construction (no MIDI round-trip)
#4 chunked separation: reflect padding, in-place division, tmp-dir cleanup
"""
from __future__ import annotations

from pathlib import Path

import pytest

FIX = Path(__file__).parent / "fixtures"


# ---- #3: Basic Pitch model cache ------------------------------------------

def test_basicpitch_model_is_cached_and_reused():
    pytest.importorskip("basic_pitch")
    import musicfab.modules.transcribe as tr

    tr._basicpitch_model.cache_clear()
    try:
        first = tr._basicpitch_model()
        second = tr._basicpitch_model()
        assert first is second, "predict() must reuse a single ONNX session"
        assert tr.basicpitch_model_cached() is True
    finally:
        tr._basicpitch_model.cache_clear()


# ---- #3: shared tempo on the mixture ---------------------------------------

def test_shared_tempo_info_on_fixture():
    pytest.importorskip("librosa")
    from musicfab.modules.separate import shared_tempo_info

    src = FIX / "melody.wav"
    if not src.exists():
        pytest.skip("fixture melody.wav missing (run scripts/gen_test_audio.py)")
    info = shared_tempo_info(src, fallback_tempo=99.0)
    assert set(info) == {"tempo", "time_signature", "beats"}
    assert isinstance(info["tempo"], float) and info["tempo"] > 0
    assert "/" in info["time_signature"]
    if info["beats"] is not None:
        assert isinstance(info["beats"], list)
        assert all(b2 > b1 for b1, b2 in zip(info["beats"], info["beats"][1:]))


def test_shared_tempo_info_falls_back_on_missing_file(tmp_path: Path):
    from musicfab.modules.separate import shared_tempo_info

    info = shared_tempo_info(tmp_path / "nope.wav", fallback_tempo=88.0, fallback_signature="3/4")
    assert info == {"tempo": 88.0, "time_signature": "3/4", "beats": None}


# ---- #2: direct MusicXML construction --------------------------------------

def test_to_musicxml_direct_construction(tmp_path: Path):
    pytest.importorskip("music21")
    from music21 import converter, meter, tempo as m21tempo

    from musicfab.core.export import to_musicxml
    from musicfab.core.project import Note, Project, Track

    proj = Project(
        name="multi",
        tempo=90.0,
        time_signature="3/4",
        tracks=[
            Track(name="bass", notes=[Note(0.0, 0.66, 40), Note(0.71, 1.4, 43)]),
            Track(
                name="melody",
                notes=[Note(0.13, 0.71, 72), Note(0.71, 1.29, 74), Note(1.29, 2.1, 76)],
            ),
        ],
    )
    snapshot = [(n.start, n.end, n.pitch) for n in proj.notes]

    out = to_musicxml(proj, tmp_path / "m.musicxml")
    assert out.exists() and out.stat().st_size > 200

    # the caller's project must not be mutated by export
    assert [(n.start, n.end, n.pitch) for n in proj.notes] == snapshot

    score = converter.parse(str(out))
    assert len(score.parts) >= 2
    names = [p.partName for p in score.parts]
    assert "bass" in names and "melody" in names, f"part names lost: {names}"

    marks = list(score.recurse().getElementsByClass(m21tempo.MetronomeMark))
    assert marks and marks[0].number == pytest.approx(90.0)
    signatures = list(score.recurse().getElementsByClass(meter.TimeSignature))
    assert signatures and signatures[0].ratioString == "3/4"

    # irregular durations (0.13 s / 0.71 s starts) must not raise and tie
    # splitting can only add notated notes
    assert len(score.flatten().notes) >= 5


def test_expressible_quarter_lengths_splits_and_collapses():
    from musicfab.core.export import _expressible_quarter_lengths
    from fractions import Fraction

    assert _expressible_quarter_lengths(3 / 16) == [Fraction(1, 8), Fraction(1, 16)]
    assert _expressible_quarter_lengths(2 / 3) == [Fraction(1, 3), Fraction(1, 3)]
    assert _expressible_quarter_lengths(1 / 3) == [Fraction(1, 3)]
    assert _expressible_quarter_lengths(1.0) == [Fraction(1, 1)]
    assert _expressible_quarter_lengths(0) == [Fraction(1, 16)]  # degenerate -> 16th
    assert _expressible_quarter_lengths(0.01) == [Fraction(1, 16)]
    for ql in (0.19, 0.5, 0.87, 1.0625, 2.5, 4.0):
        pieces = _expressible_quarter_lengths(ql)
        assert sum(pieces) > 0
        assert all(p >= Fraction(1, 16) for p in pieces)


# ---- #4: chunked separation robustness (no real Demucs run) ----------------

def test_chunked_separate_cleans_tmp_dir_on_error(tmp_path: Path, monkeypatch):
    pytest.importorskip("demucs")
    pytest.importorskip("torch")
    src = FIX / "melody.wav"
    if not src.exists():
        pytest.skip("fixture melody.wav missing")

    class _FakeNet:
        samplerate = 44100
        sources = ["drums", "bass", "other", "vocals"]
        segment = 7.8

        def eval(self):
            return self

    def _boom(*args, **kwargs):
        raise RuntimeError("apply_model boom")

    monkeypatch.setattr("demucs.pretrained.get_model", lambda name: _FakeNet())
    monkeypatch.setattr("demucs.apply.apply_model", _boom)

    from musicfab.modules.separate import separate

    out = tmp_path / "stems"
    with pytest.raises(RuntimeError, match="apply_model boom"):
        separate(src, output_dir=out, chunk_seconds=1.0)
    assert not (out / ".chunked").exists(), "temp memmap dir must be removed on failure"


def test_chunked_separate_reflect_pads_and_streams(tmp_path: Path, monkeypatch):
    """End-to-end chunked path with a stubbed Demucs model (no real inference).

    The stub returns a deterministic mix; the test verifies stem length,
    reflect padding bookkeeping and tmp-dir cleanup.
    """
    pytest.importorskip("demucs")
    pytest.importorskip("torch")
    src = FIX / "melody.wav"
    if not src.exists():
        pytest.skip("fixture melody.wav missing")
    import numpy as np
    import soundfile as sf
    import torch

    class _FakeNet:
        samplerate = 44100
        sources = ["drums", "bass", "other", "vocals"]
        segment = 7.8

        def eval(self):
            return self

    calls = {"n": 0}

    def _fake_apply(net, seg, **kwargs):
        calls["n"] += 1
        x = seg.detach().cpu()
        return torch.stack([x] * len(net.sources), dim=1)  # [1, sources, ch, t]

    monkeypatch.setattr("demucs.pretrained.get_model", lambda name: _FakeNet())
    monkeypatch.setattr("demucs.apply.apply_model", _fake_apply)

    from musicfab.modules.separate import separate

    out = tmp_path / "stems"
    manifest = separate(src, output_dir=out, chunk_seconds=1.0)
    assert manifest["chunked"] is True
    assert calls["n"] >= 2, "short file must still be split into chunks"
    info = sf.info(str(out / "drums.wav"))
    expected_frames = sf.info(str(src)).frames * 44100 / sf.info(str(src)).samplerate
    assert abs(info.frames - expected_frames) < 100, "stem length must match the input"
    assert info.channels == 2
    assert not (out / ".chunked").exists()
