"""Multi-page notation rendering (Verovio pagination -> full PDF/SVG/PNG)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from musicfab.core.project import Note, Project

BARS = 96  # 96 bars of 4/4 eighths at 120 BPM; Verovio paginates this to >= 2 pages


def _long_project(tmp_path: Path) -> Path:
    count = BARS * 8  # one eighth per 0.5 s
    notes = [
        Note(round(i * 0.5, 3), round(i * 0.5 + 0.45, 3), 60 + (i % 13))
        for i in range(count)
    ]
    proj = Project.from_notes(
        notes,
        name="long",
        tempo=120.0,
        time_signature="4/4",
        beats=[round(i * 0.5, 4) for i in range(count + 2)],
    )
    return proj.save(tmp_path / "long.mfproj.json")


def _rasterisers_available() -> bool:
    return (
        importlib.util.find_spec("resvg_py") is not None
        or importlib.util.find_spec("pymupdf") is not None
    )


def test_multipage_pdf_contains_all_pages(tmp_path: Path):
    pytest.importorskip("verovio")
    pytest.importorskip("pymupdf")
    import pymupdf

    from musicfab.modules.notation import convert

    src = _long_project(tmp_path)
    pdf = convert(src, output=tmp_path / "long.pdf", fmt="pdf", quantize_beats=2)
    assert pdf.read_bytes()[:5] == b"%PDF-"

    doc = pymupdf.open(str(pdf))
    try:
        assert doc.page_count >= 2, f"expected a multi-page PDF, got {doc.page_count} page(s)"
        for page in doc:
            pix = page.get_pixmap(dpi=50)
            dark = sum(1 for i in range(0, len(pix.samples), 97) if pix.samples[i] < 240)
            assert dark > 5, f"score PDF page {page.number + 1} must not be blank"
    finally:
        doc.close()


def test_multipage_svg_writes_page_files(tmp_path: Path, capsys):
    pytest.importorskip("verovio")
    from musicfab.modules.notation import convert

    src = _long_project(tmp_path)
    out = convert(src, output=tmp_path / "long.svg", fmt="svg")
    assert out.exists()
    assert "<svg" in out.read_text(encoding="utf-8")[:2000]
    page2 = tmp_path / "long_p2.svg"
    assert page2.exists(), "page 2 SVG must be written next to page 1"
    assert "<svg" in page2.read_text(encoding="utf-8")[:2000]
    assert "pages" in capsys.readouterr().err


def test_multipage_png_writes_page_files(tmp_path: Path):
    pytest.importorskip("verovio")
    if not _rasterisers_available():
        pytest.skip("neither resvg-py nor pymupdf installed")
    from musicfab.modules.notation import convert

    src = _long_project(tmp_path)
    out = convert(src, output=tmp_path / "long.png", fmt="png")
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    page2 = tmp_path / "long_p2.png"
    assert page2.exists(), "page 2 PNG must be written next to page 1"
    assert page2.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
