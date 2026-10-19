"""Guitar tab import / conversion (Guitar Pro alternative).

Uses PyGuitarPro (LGPL-3, imported as a regular dependency) to read
``.gp3/.gp4/.gp5`` files and converts them to:

* a plain JSON structure (``--format json``),
* MIDI (``--format midi``),
* MusicXML (``--format musicxml``).

``.gpx`` files are not supported by PyGuitarPro; convert them with
TuxGuitar/MuseScore first (see docs/COMPAT.md).
"""
from __future__ import annotations

import json
from pathlib import Path

from ..core.project import Note, Project, Track

TICKS_PER_QUARTER = 960  # Guitar Pro file format constant
SUPPORTED = {".gp3", ".gp4", ".gp5"}


def _beat_ticks(duration) -> int:
    """Convert a Guitar Pro Duration into ticks (quarter = 960)."""
    value = int(getattr(duration, "value", 4) or 4)  # 1=whole, 2=half, 4=quarter ...
    ticks = TICKS_PER_QUARTER * 4 / value
    if getattr(duration, "isDotted", False):
        ticks *= 1.5
    tuplet = getattr(duration, "tuplet", None)
    if tuplet is not None:
        enters = max(1, int(getattr(tuplet, "enters", 1) or 1))
        times = max(1, int(getattr(tuplet, "times", 1) or 1))
        ticks = ticks * times / enters
    return int(round(ticks))


def parse_tab(path: str | Path) -> dict:
    """Parse a Guitar Pro file into a JSON-serialisable dict."""
    src = Path(path)
    if not src.exists():
        raise FileNotFoundError(src)
    if src.suffix.lower() not in SUPPORTED:
        raise ValueError(
            f"unsupported tab format {src.suffix!r}; supported: {sorted(SUPPORTED)} "
            "(for .gpx convert with TuxGuitar/MuseScore first)"
        )
    try:
        import guitarpro
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("PyGuitarPro is required for tab import: pip install pyguitarpro") from exc

    song = guitarpro.parse(str(src))
    tempo = float(getattr(song, "tempo", 120) or 120)
    sec_per_quarter = 60.0 / tempo

    tracks = []
    for track in song.tracks:
        strings = [int(s.value) for s in track.strings]  # 1-based, string 1 = highest
        track_notes = []
        for measure in track.measures:
            measure_start = int(getattr(measure.header, "start", 0))
            for voice in measure.voices:
                for beat in voice.beats:
                    start_tick = measure_start + int(getattr(beat, "start", 0))
                    dur_tick = _beat_ticks(beat.duration)
                    start_s = start_tick / TICKS_PER_QUARTER * sec_per_quarter
                    dur_s = dur_tick / TICKS_PER_QUARTER * sec_per_quarter
                    for note in beat.notes:
                        string_no = int(getattr(note, "string", 0) or 0)
                        fret = int(getattr(note, "value", 0) or 0)
                        try:
                            pitch = int(note.realValue)
                        except Exception:
                            tuning = strings[string_no - 1] if 0 < string_no <= len(strings) else 0
                            pitch = tuning + fret
                        track_notes.append(
                            {
                                "start": round(start_s, 4),
                                "duration": round(dur_s, 4),
                                "pitch": pitch,
                                "velocity": int(getattr(note, "velocity", 80) or 80),
                                "string": string_no,
                                "fret": fret,
                            }
                        )
        track_notes.sort(key=lambda n: (n["start"], n["pitch"]))
        tracks.append(
            {
                "name": track.name or f"track{track.number}",
                "strings": strings,
                "notes": track_notes,
            }
        )

    return {
        "title": song.title or "",
        "artist": song.artist or "",
        "album": song.album or "",
        "tempo": tempo,
        "tracks": tracks,
    }


def _to_project(data: dict) -> Project:
    tracks = []
    for t in data["tracks"]:
        notes = [
            Note(start=n["start"], end=n["start"] + n["duration"], pitch=n["pitch"], velocity=n["velocity"])
            for n in t["notes"]
        ]
        tracks.append(Track(name=t["name"], notes=notes))
    proj = Project(name=data.get("title") or "tab", tempo=data.get("tempo", 120.0), tracks=tracks)
    proj.meta.update({"artist": data.get("artist", ""), "album": data.get("album", "")})
    return proj


def import_tab(input_path: str | Path, *, output: str | Path, fmt: str = "json") -> Path:
    """Convert a Guitar Pro file to JSON/MIDI/MusicXML."""
    from ..core.export import to_midi, to_musicxml

    data = parse_tab(input_path)
    dst = Path(output)
    dst.parent.mkdir(parents=True, exist_ok=True)

    fmt = fmt.lower()
    if fmt == "json":
        dst.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
        return dst
    if fmt in {"midi", "musicxml"}:
        proj = _to_project(data)
        return to_midi(proj, dst) if fmt == "midi" else to_musicxml(proj, dst)
    if fmt in {"svg", "html"}:
        return render_tab(data, dst, fmt=fmt)
    raise ValueError(f"unsupported tab output format: {fmt!r} (json/midi/musicxml/svg/html)")


# ---------------------------------------------------------------------------
# ASCII-tab style SVG renderer (pure python, offline, deterministic)
# ---------------------------------------------------------------------------

_STRING_SPACING = 18
_BAR_WIDTH = 190
_LEFT = 70
_TOP = 70
_LINE_COLOR = "#222"


def _esc(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def render_tab(data: dict | str | Path, output: str | Path, *, fmt: str = "svg", max_bars: int = 16) -> Path:
    """Render a parsed tab (or a .gp3/.gp4/.gp5 path) as SVG/HTML.

    The renderer is intentionally minimal (frets on string lines, bar lines,
    title/tempo header) and needs no browser or external library.
    """
    if not isinstance(data, dict):
        data = parse_tab(data)
    dst = Path(output)
    dst.parent.mkdir(parents=True, exist_ok=True)
    svg = tab_to_svg(data, max_bars=max_bars)
    if fmt == "svg":
        dst.write_text(svg, encoding="utf-8")
    elif fmt == "html":
        title = _esc(data.get("title") or "tab")
        dst.write_text(
            "<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>{title}</title>"
            "<style>body{font-family:Segoe UI,Arial,sans-serif;margin:24px;background:#fafafa}"
            "svg{background:#fff;box-shadow:0 1px 4px #0002;max-width:100%;height:auto}</style>"
            f"</head><body><h2>{title}</h2>{svg}</body></html>",
            encoding="utf-8",
        )
    else:
        raise ValueError(f"unsupported tab render format: {fmt!r} (svg/html)")
    return dst


def tab_to_svg(data: dict, *, max_bars: int = 16) -> str:
    tempo = float(data.get("tempo") or 120.0)
    bar_seconds = 4 * 60.0 / tempo if tempo > 0 else 2.0
    width = _LEFT + max_bars * _BAR_WIDTH + 30
    lines_total = 0
    for track in data.get("tracks", []):
        lines_total += max(6, len(track.get("strings") or []) or 6)
    height = _TOP + 60 + max(1, len(data.get("tracks", []))) * (120 + 6 * _STRING_SPACING) + 20

    parts: list[str] = [
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' "
        f"viewBox='0 0 {width} {height}' font-family='Consolas,Menlo,monospace'>",
        "<rect width='100%' height='100%' fill='#ffffff'/>",
        f"<text x='{_LEFT}' y='30' font-size='18' font-weight='bold'>{_esc(data.get('title') or 'Tab')}</text>",
        f"<text x='{_LEFT}' y='50' font-size='12' fill='#555'>{_esc(data.get('artist') or '')}"
        f"   tempo {tempo:g} BPM</text>",
    ]

    y_cursor = _TOP + 40
    for track in data.get("tracks", []):
        strings = track.get("strings") or []
        n_strings = max(6, len(strings)) if not strings else len(strings)
        top = y_cursor
        parts.append(
            f"<text x='{_LEFT}' y='{top - 8}' font-size='12' fill='#333'>"
            f"{_esc(track.get('name') or 'track')} · {len(track.get('notes', []))} notes</text>"
        )
        grid_top = top + 10
        grid_bottom = grid_top + (n_strings - 1) * _STRING_SPACING
        # horizontal string lines + labels
        for i in range(n_strings):
            y = grid_top + i * _STRING_SPACING
            parts.append(
                f"<line x1='{_LEFT - 20}' y1='{y}' x2='{_LEFT + max_bars * _BAR_WIDTH}' y2='{y}' "
                f"stroke='{_LINE_COLOR}' stroke-width='1'/>"
            )
        # bar lines
        for b in range(max_bars + 1):
            x = _LEFT + b * _BAR_WIDTH
            parts.append(
                f"<line x1='{x}' y1='{grid_top - 6}' x2='{x}' y2='{grid_bottom + 6}' "
                f"stroke='#888' stroke-width='1'/>"
            )
        # fret numbers
        for note in track.get("notes", []):
            start = float(note.get("start", 0.0))
            bar = int(start // bar_seconds) if bar_seconds > 0 else 0
            if bar < 0 or bar >= max_bars:
                continue
            frac = (start - bar * bar_seconds) / bar_seconds if bar_seconds > 0 else 0.0
            x = _LEFT + bar * _BAR_WIDTH + 10 + frac * (_BAR_WIDTH - 24)
            string_no = int(note.get("string") or 1)
            # string 1 = highest pitch -> drawn on top line
            y = grid_top + (string_no - 1) * _STRING_SPACING
            fret = int(note.get("fret", 0))
            parts.append(
                f"<text x='{x:.1f}' y='{y - 3:.1f}' font-size='11' text-anchor='middle' "
                f"fill='#000'>{fret}</text>"
            )
        y_cursor = grid_bottom + 70

    parts.append("</svg>")
    return "\n".join(parts) + "\n"
