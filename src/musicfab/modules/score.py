"""Combine per-stem transcriptions into one multi-part score (Capella/RipX).

Takes the output directory of ``musicfab separate --transcribe`` (one
``*.mfproj.json`` per stem) and writes a single MusicXML score with one part
per stem — or PDF/PNG/SVG via the notation pipeline.

Example::

    musicfab separate song.wav --transcribe --auto-tempo -o stems/
    musicfab score stems/ -o full.musicxml
    musicfab score stems/ -o full.pdf --quantize-beats 2
"""
from __future__ import annotations

from pathlib import Path

from ..core.export import to_musicxml
from ..core.project import Project, Track


def _find_projects(root: Path) -> list[Path]:
    files = sorted(root.glob("*.mfproj.json"))
    if not files:
        files = sorted(root.rglob("*.mfproj.json"))
    return files


def _stem_name(path: Path) -> str:
    name = path.name
    for suffix in (".mfproj.json", ".mfproj"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return path.stem


def build_score(
    input_dir: str | Path,
    *,
    output: str | Path,
    fmt: str = "musicxml",
    quantize_beats: int | None = None,
    name: str | None = None,
) -> Path:
    """Build a multi-part score from per-stem musicfab projects."""
    root = Path(input_dir)
    if not root.exists():
        raise FileNotFoundError(root)
    files = _find_projects(root)
    if not files:
        raise FileNotFoundError(f"no *.mfproj.json found under {root}")

    projects = [( _stem_name(p), Project.load(p)) for p in files]
    first = projects[0][1]
    tempo = float(first.tempo or 120.0)
    signature = getattr(first, "time_signature", "4/4") or "4/4"
    beats = list(first.beats or [])

    combined = Project(
        name=name or root.name or "score",
        tempo=tempo,
        time_signature=signature,
        beats=beats,
        tracks=[Track(name=stem, notes=list(proj.notes)) for stem, proj in projects],
    )

    dst = Path(output)
    dst.parent.mkdir(parents=True, exist_ok=True)
    fmt = (fmt or "musicxml").lower()
    if fmt == "musicxml":
        return to_musicxml(combined, dst, quantize_beats=quantize_beats)
    if fmt == "midi":
        from ..core.export import to_midi

        return to_midi(combined, dst)

    from .notation import convert

    tmp = dst.with_suffix(".tmp.musicxml")
    try:
        to_musicxml(combined, tmp, quantize_beats=quantize_beats)
        return convert(tmp, output=dst, fmt=fmt)
    finally:
        tmp.unlink(missing_ok=True)
