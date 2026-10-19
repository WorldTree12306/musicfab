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
AUDIO_EXTS = {".mid", ".midi", ".musicxml", ".xml", ".mxl", ".mei"}


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


def convert(input_path: str | Path, *, output: str | Path, fmt: str = "musicxml") -> Path:
    """Convert a score file.

    ``fmt``: ``musicxml`` | ``midi`` | ``svg`` | ``png`` | ``pdf``.
    """
    src = Path(input_path)
    dst = Path(output)
    if not src.exists():
        raise FileNotFoundError(src)
    if src.suffix.lower() not in AUDIO_EXTS:
        raise ValueError(f"unsupported score input: {src.suffix} (expected one of {sorted(AUDIO_EXTS)})")
    dst.parent.mkdir(parents=True, exist_ok=True)

    fmt = fmt.lower()
    if fmt == "musicxml":
        if src.suffix.lower() in {".musicxml", ".xml", ".mxl"}:
            return _to_musicxml(src, dst)
        return _to_musicxml(src, dst)
    if fmt == "midi":
        return _to_midi(src, dst)

    # rendering formats: prefer MuseScore, then Verovio SVG (and cairosvg for raster)
    if shutil.which("musescore4") or shutil.which("musescore") or find_musescore():
        try:
            return _render_with_musescore(src, dst)
        except RuntimeError:
            pass

    svg_path = dst.with_suffix(".svg") if fmt != "svg" else dst
    try:
        _render_svg_with_verovio(src, svg_path)
    except RuntimeError:
        # last resort: convert to musicxml first, then try MuseScore/Verovio again
        tmp_xml = dst.with_suffix(".tmp.musicxml")
        _to_musicxml(src, tmp_xml)
        try:
            return _render_with_musescore(tmp_xml, dst)
        except RuntimeError:
            _render_svg_with_verovio(tmp_xml, svg_path)
        finally:
            tmp_xml.unlink(missing_ok=True)

    if fmt == "svg":
        return svg_path
    try:
        import cairosvg
    except Exception as exc:  # pragma: no cover - platform dependent
        raise RuntimeError(
            f"rendered SVG to {svg_path}, but raster/PDF export needs MuseScore or cairosvg: {exc}"
        ) from exc
    if fmt == "png":
        cairosvg.svg2png(url=str(svg_path), write_to=str(dst))
    elif fmt == "pdf":
        cairosvg.svg2pdf(url=str(svg_path), write_to=str(dst))
    else:
        raise ValueError(f"unsupported render format: {fmt}")
    return dst
