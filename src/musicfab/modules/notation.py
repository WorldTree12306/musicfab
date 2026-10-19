"""Score conversion / engraving (Capella alternative).

Backends, in order of preference:
1. MuseScore CLI (``musescore4``/``musescore3``/``musescore``/``mscore``) for
   PDF/PNG/SVG and format conversion — called as a subprocess so the GPL
   licence stays isolated from this MIT project.
2. Verovio (python package) for SVG rendering of MusicXML/MEI.
3. music21 for MusicXML <-> MIDI conversion.

All processing is offline; nothing is uploaded.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

MUSESCORE_NAMES = ("musescore4", "musescore3", "musescore", "mscore", "MuseScore4", "MuseScore3")
AUDIO_EXTS = {".mid", ".midi", ".musicxml", ".xml", ".mxl", ".mei", ".mfproj.json"}


def find_musescore() -> str | None:
    for name in MUSESCORE_NAMES:
        exe = shutil.which(name)
        if exe:
            return exe
    # common Windows install locations
    for cand in (
        r"C:\Program Files\MuseScore 4\bin\MuseScore4.exe",
        r"C:\Program Files\MuseScore 3\bin\MuseScore3.exe",
        r"C:\Program Files (x86)\MuseScore 4\bin\MuseScore4.exe",
    ):
        if Path(cand).exists():
            return cand
    return None


def _parse(path: Path):
    from music21 import converter

    return converter.parse(str(path))


def _to_musicxml(src: Path, dst: Path) -> Path:
    _parse(src).write("musicxml", fp=str(dst))
    return dst


def _to_midi(src: Path, dst: Path) -> Path:
    _parse(src).write("midi", fp=str(dst))
    return dst


def _render_with_musescore(src: Path, dst: Path) -> Path:
    exe = find_musescore()
    if not exe:
        raise RuntimeError(
            "MuseScore CLI not found. Install MuseScore (GPL) and make sure "
            "'musescore4'/'musescore' is on PATH, or install a Python renderer."
        )
    proc = subprocess.run([exe, "-o", str(dst), str(src)], capture_output=True, text=True, timeout=300)
    if not dst.exists():
        raise RuntimeError(
            f"MuseScore failed (rc={proc.returncode}): {proc.stderr.strip()[:500] or proc.stdout.strip()[:500]}"
        )
    return dst


def _render_svg_with_verovio(src: Path, dst: Path) -> Path:
    try:
        import verovio
    except ImportError as exc:  # pragma: no cover - handled by caller
        raise RuntimeError("Verovio is not installed; run: pip install verovio") from exc
    tk = verovio.toolkit()
    tk.setOptions({"pageWidth": 2100, "pageHeight": 2970, "scale": 40})
    if not tk.loadFile(str(src)):
        raise RuntimeError(f"Verovio could not load {src.name} (MusicXML/MEI expected)")
    svg = tk.renderToSVG(1)
    if not svg:
        raise RuntimeError("Verovio produced empty SVG")
    dst.write_text(svg, encoding="utf-8")
    return dst


def convert(
    input_path: str | Path,
    *,
    output: str | Path,
    fmt: str = "musicxml",
    quantize_beats: int | None = None,
) -> Path:
    """Convert a score file.

    ``fmt``: ``musicxml`` | ``midi`` | ``svg`` | ``png`` | ``pdf``.
    """
    src = Path(input_path)
    dst = Path(output)
    if not src.exists():
        raise FileNotFoundError(src)
    is_project = src.name.endswith(".mfproj.json")
    if not is_project and src.suffix.lower() not in AUDIO_EXTS:
        raise ValueError(f"unsupported score input: {src.suffix} (expected one of {sorted(AUDIO_EXTS)})")
    dst.parent.mkdir(parents=True, exist_ok=True)

    fmt = fmt.lower()
    if src.name.endswith(".mfproj.json"):
        from ..core.export import to_midi, to_musicxml
        from ..core.project import Project

        project = Project.load(src)
        if fmt == "musicxml":
            return to_musicxml(project, dst, quantize_beats=quantize_beats)
        if fmt == "midi":
            return to_midi(project, dst)
        # render from a temporary MusicXML
        tmp = dst.with_suffix(".tmp.musicxml")
        try:
            to_musicxml(project, tmp, quantize_beats=quantize_beats)
            return convert(tmp, output=dst, fmt=fmt)
        finally:
            tmp.unlink(missing_ok=True)

    if fmt == "musicxml":
        if src.suffix.lower() in {".musicxml", ".xml", ".mxl"}:
            return _to_musicxml(src, dst)
        return _to_musicxml(src, dst)
    if fmt == "midi":
        return _to_midi(src, dst)

    # rendering formats: prefer MuseScore (best engraving), then Verovio SVG
    # + PyMuPDF (pure-python, no system libraries), then cairosvg.
    if shutil.which("musescore4") or shutil.which("musescore") or find_musescore():
        try:
            return _render_with_musescore(src, dst)
        except RuntimeError:
            pass

    svg_path = dst.with_suffix(".svg") if fmt != "svg" else dst
    try:
        _render_svg_with_verovio(src, svg_path)
    except RuntimeError:
        # last resort: convert to musicxml first, then try Verovio again
        tmp_xml = dst.with_suffix(".tmp.musicxml")
        _to_musicxml(src, tmp_xml)
        try:
            _render_svg_with_verovio(tmp_xml, svg_path)
        finally:
            tmp_xml.unlink(missing_ok=True)

    if fmt == "svg":
        return svg_path

    # PDF / PNG from the rendered SVG.  PyMuPDF is a self-contained wheel
    # (MuPDF) that handles Verovio SVG well and needs no system cairo.
    try:
        return _svg_to_raster_or_pdf(svg_path, dst, fmt)
    except RuntimeError:
        pass

    try:
        import cairosvg
    except Exception as exc:  # pragma: no cover - platform dependent
        raise RuntimeError(
            f"rendered SVG to {svg_path}, but PDF/PNG export needs PyMuPDF "
            f"(pip install pymupdf), MuseScore, or cairosvg: {exc}"
        ) from exc
    if fmt == "png":
        cairosvg.svg2png(url=str(svg_path), write_to=str(dst))
    elif fmt == "pdf":
        cairosvg.svg2pdf(url=str(svg_path), write_to=str(dst))
    else:
        raise ValueError(f"unsupported render format: {fmt}")
    return dst


def _svg_to_png_bytes(svg_path: Path, dpi: int = 200) -> bytes | None:
    """Rasterise an SVG with resvg (handles Verovio's <use> glyph refs)."""
    try:
        import resvg_py
    except ImportError:  # pragma: no cover - optional dependency
        return None
    zoom = max(0.5, dpi / 96.0)
    data = resvg_py.svg_to_bytes(
        svg_path=str(svg_path), background="#ffffff", zoom=zoom, skip_system_fonts=False
    )
    png = bytes(data)
    if not png.startswith(b"\x89PNG"):
        raise RuntimeError("resvg did not produce a PNG")
    return png


def _svg_to_raster_or_pdf(svg_path: Path, dst: Path, fmt: str, dpi: int = 200) -> Path:
    """Convert a Verovio SVG to PDF or PNG.

    Verovio references notation glyphs through ``<use xlink:href="#…">``;
    those references are not resolved by MuPDF's SVG parser, so resvg is used
    to rasterise the SVG first (PDF is then a high-DPI raster page, which is
    visually identical for scores).
    """
    if fmt not in {"pdf", "png"}:
        raise ValueError(f"unsupported render format: {fmt}")
    png = _svg_to_png_bytes(svg_path, dpi=dpi)
    if png is not None:
        if fmt == "png":
            dst.write_bytes(png)
            return dst
        try:
            import pymupdf
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("PyMuPDF not installed (pip install pymupdf)") from exc
        doc = pymupdf.open(stream=png, filetype="png")
        try:
            pdf_bytes = doc.convert_to_pdf()
        finally:
            doc.close()
        dst.write_bytes(pdf_bytes)
        return dst

    # Fallback: MuPDF's own SVG parser (works for SVGs without <use> refs).
    try:
        import pymupdf
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "PDF/PNG rendering needs resvg-py or PyMuPDF: pip install resvg-py pymupdf"
        ) from exc
    doc = pymupdf.open(str(svg_path))
    try:
        if fmt == "pdf":
            doc.save(str(dst))
        else:
            page = doc[0]
            zoom = dpi / 72.0
            pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
            pix.save(str(dst))
    finally:
        doc.close()
    return dst
