from __future__ import annotations

import json
from pathlib import Path

import pytest


def _write_stem(root: Path, name: str, pitches, tempo=100):
    from musicfab.core.project import Note, Project

    notes = [Note(round(i * 0.5, 3), round(i * 0.5 + 0.4, 3), p) for i, p in enumerate(pitches)]
    proj = Project.from_notes(notes, name=name, tempo=tempo)
    proj.beats = [round(i * 0.6, 4) for i in range(20)]
    return proj.save(root / f"{name}.mfproj.json")


def test_build_multipart_score(tmp_path: Path):
    from music21 import converter

    from musicfab.modules.score import build_score

    src = tmp_path / "stems"
    src.mkdir()
    _write_stem(src, "bass", [40, 43, 45])
    _write_stem(src, "melody", [72, 74, 76, 77])

    out = build_score(src, output=tmp_path / "full.musicxml")
    assert out.exists() and out.stat().st_size > 200

    score = converter.parse(str(out))
    parts = list(score.parts)
    assert len(parts) >= 2, f"expected multi-part score, got {len(parts)} parts"
    note_counts = [len(p.flatten().notes) for p in parts]
    assert sum(note_counts) >= 7
    assert all(c > 0 for c in note_counts)


def test_build_score_pdf(tmp_path: Path):
    pytest.importorskip("pymupdf")
    from musicfab.modules.score import build_score

    src = tmp_path / "stems"
    src.mkdir()
    _write_stem(src, "bass", [40, 43])
    _write_stem(src, "melody", [72, 74])

    pdf = build_score(src, output=tmp_path / "full.pdf", fmt="pdf", quantize_beats=1)
    assert pdf.exists() and pdf.read_bytes()[:5] == b"%PDF-"
    import pymupdf

    doc = pymupdf.open(str(pdf))
    pix = doc[0].get_pixmap(dpi=50)
    dark = sum(1 for i in range(0, len(pix.samples), 97) if pix.samples[i] < 240)
    assert dark > 5, "score PDF must not be blank"
    doc.close()
