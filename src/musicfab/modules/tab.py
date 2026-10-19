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

import html
import json
from pathlib import Path

from ..core.project import Note, Project, Track

TICKS_PER_QUARTER = 960  # Guitar Pro file format constant
SUPPORTED = {".gp3", ".gp4", ".gp5"}

def _time_signature_values(ts) -> tuple[int, int]:
    """Return (numerator, denominator) from a PyGuitarPro TimeSignature."""
    if ts is None:
        return 4, 4
    try:
        num = int(getattr(ts, "numerator", 4) or 4)
    except Exception:
        num = 4
    raw_den = getattr(ts, "denominator", 4)
    try:
        den = int(getattr(raw_den, "value", raw_den))
    except Exception:
        den = 4
    if num <= 0 or den not in (1, 2, 4, 8, 16, 32):
        return 4, 4
    return num, den




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

    headers = list(getattr(song, "measureHeaders", []) or [])
    measures: list[dict] = []
    for i, h in enumerate(headers):
        ts = getattr(h, "timeSignature", None)
        num, den = _time_signature_values(ts)
        start_tick = int(getattr(h, "start", 0))
        if i + 1 < len(headers):
            end_tick = int(getattr(headers[i + 1], "start", start_tick))
        else:
            end_tick = start_tick + int(num * TICKS_PER_QUARTER * 4 / max(1, den))
        measures.append(
            {
                "index": i,
                "start": round(start_tick / TICKS_PER_QUARTER * sec_per_quarter, 4),
                "duration": round((end_tick - start_tick) / TICKS_PER_QUARTER * sec_per_quarter, 4),
                "time_signature": f"{num}/{den}",
            }
        )
    time_signature = measures[0]["time_signature"] if measures else "4/4"

    tracks = []
    for track in song.tracks:
        strings = [int(s.value) for s in track.strings]  # 1-based, string 1 = highest
        track_notes = []
        for measure_index, measure in enumerate(track.measures):
            header = measure.header
            measure_start = int(getattr(header, "start", 0))
            ts = getattr(header, "timeSignature", None)
            num, den = _time_signature_values(ts)
            measure_len = max(1, int(num * TICKS_PER_QUARTER * 4 / max(1, den)))
            for voice in measure.voices:
                for beat in voice.beats:
                    start_tick = measure_start + int(getattr(beat, "start", 0))
                    dur_tick = _beat_ticks(beat.duration)
                    start_s = start_tick / TICKS_PER_QUARTER * sec_per_quarter
                    dur_s = dur_tick / TICKS_PER_QUARTER * sec_per_quarter
                    bar_pos = min(1.0, max(0.0, (start_tick - measure_start) / measure_len))
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
                                "bar": measure_index,
                                "bar_pos": round(bar_pos, 5),
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
        "time_signature": time_signature,
        "measures": measures,
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
    if fmt in {"svg", "html", "pdf", "png"}:
        return render_tab(data, dst, fmt=fmt)
    raise ValueError(f"unsupported tab output format: {fmt!r} (json/midi/musicxml/svg/html)")


# ---------------------------------------------------------------------------
# ASCII-tab style SVG renderer (pure python, offline, deterministic)
# ---------------------------------------------------------------------------

_STRING_SPACING = 18
_BAR_WIDTH = 150
_LEFT = 70
_TOP = 70
_LINE_COLOR = "#222"


def _esc(text: str) -> str:
    return html.escape(str(text), quote=True)


def _measure_grid(data: dict) -> list[dict]:
    """Return measure list with start/duration seconds (synthesise 4/4 if absent)."""
    measures = list(data.get("measures") or [])
    if measures:
        return measures
    tempo = float(data.get("tempo") or 120.0)
    bar_seconds = 4 * 60.0 / tempo if tempo > 0 else 2.0
    end = 0.0
    for track in data.get("tracks", []):
        for n in track.get("notes", []):
            end = max(end, float(n.get("start", 0.0)) + float(n.get("duration", 0.0)))
    count = max(1, int(end / bar_seconds) + 1) if bar_seconds > 0 else 1
    return [
        {"index": i, "start": round(i * bar_seconds, 4), "duration": round(bar_seconds, 4), "time_signature": "4/4"}
        for i in range(count)
    ]


def _bar_of(note: dict, measures: list[dict]) -> tuple[int, float]:
    """Locate (measure index, fraction within measure) for a note."""
    if "bar" in note:
        bar = int(note["bar"])
        frac = float(note.get("bar_pos", 0.0))
        if 0 <= bar < len(measures):
            return bar, min(1.0, max(0.0, frac))
    start = float(note.get("start", 0.0))
    lo, hi = 0, len(measures) - 1
    bar = 0
    while lo <= hi:
        mid = (lo + hi) // 2
        if measures[mid]["start"] <= start:
            bar = mid
            lo = mid + 1
        else:
            hi = mid - 1
    duration = float(measures[bar].get("duration") or 0.0)
    frac = (start - float(measures[bar]["start"])) / duration if duration > 0 else 0.0
    return bar, min(1.0, max(0.0, frac))


def render_tab(data: dict | str | Path, output: str | Path, *, fmt: str = "svg", max_bars: int = 16) -> Path:
    """Render a parsed tab (or a .gp3/.gp4/.gp5 path) as SVG/HTML/PDF/PNG.

    The renderer is intentionally minimal (frets on string lines, bar lines,
    title/tempo header) and needs no browser or external library.  Measures use
    the time signatures from the Guitar Pro file; notes beyond ``max_bars`` are
    reported (not silently dropped).
    """
    if not isinstance(data, dict):
        data = parse_tab(data)
    if max_bars < 1:
        raise ValueError("max_bars must be >= 1")
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
    elif fmt in {"pdf", "png"}:
        import tempfile

        from .notation import _svg_to_raster_or_pdf

        with tempfile.TemporaryDirectory() as tmp:
            svg_path = Path(tmp) / "tab.svg"
            svg_path.write_text(svg, encoding="utf-8")
            _svg_to_raster_or_pdf(svg_path, dst, fmt)
    else:
        raise ValueError(f"unsupported tab render format: {fmt!r} (svg/html/pdf/png)")
    return dst


def tab_to_svg(data: dict, *, max_bars: int = 16) -> str:
    tempo = float(data.get("tempo") or 120.0)
    measures = _measure_grid(data)
    shown = min(int(max_bars), len(measures))
    width = _LEFT + shown * _BAR_WIDTH + 40

    tracks = list(data.get("tracks", []))
    track_heights = [40 + (max(6, len(t.get("strings") or [])) - 1) * _STRING_SPACING + 70 for t in tracks]
    height = _TOP + 30 + sum(track_heights) + 30

    parts: list[str] = [
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' "
        f"viewBox='0 0 {width} {height}' font-family='Consolas,Menlo,monospace'>",
        "<rect width='100%' height='100%' fill='#ffffff'/>",
        f"<text x='{_LEFT}' y='30' font-size='18' font-weight='bold'>{_esc(data.get('title') or 'Tab')}</text>",
        f"<text x='{_LEFT}' y='50' font-size='12' fill='#555'>{_esc(data.get('artist') or '')}"
        f"   tempo {tempo:g} BPM · {_esc(data.get('time_signature') or measures[0]['time_signature'])}</text>",
    ]

    y_cursor = _TOP + 40
    dropped_total = 0
    for track, block_height in zip(tracks, track_heights):
        strings = track.get("strings") or []
        n_strings = max(6, len(strings))
        top = y_cursor
        grid_top = top + 10
        grid_bottom = grid_top + (n_strings - 1) * _STRING_SPACING
        dropped = 0
        parts.append(
            f"<text x='{_LEFT}' y='{top - 8}' font-size='12' fill='#333'>"
            f"{_esc(track.get('name') or 'track')} · {len(track.get('notes', []))} notes</text>"
        )
        # horizontal strings
        for i in range(n_strings):
            y = grid_top + i * _STRING_SPACING
            parts.append(
                f"<line x1='{_LEFT - 20}' y1='{y}' x2='{_LEFT + shown * _BAR_WIDTH}' y2='{y}' "
                f"stroke='{_LINE_COLOR}' stroke-width='1'/>"
            )
        # bar lines (respect per-measure width)
        for b in range(shown + 1):
            x = _LEFT + b * _BAR_WIDTH
            parts.append(
                f"<line x1='{x}' y1='{grid_top - 6}' x2='{x}' y2='{grid_bottom + 6}' "
                f"stroke='#888' stroke-width='1'/>"
            )
        # fret numbers
        for note in track.get("notes", []):
            bar, frac = _bar_of(note, measures)
            if frac > 0.995 and bar + 1 < len(measures):
                bar, frac = bar + 1, 0.0
            if bar < 0 or bar >= shown:
                dropped += 1
                continue
            string_no = int(note.get("string") or 1)
            if string_no < 1 or string_no > n_strings:
                dropped += 1
                continue
            x = _LEFT + bar * _BAR_WIDTH + 8 + frac * (_BAR_WIDTH - 16)
            y = grid_top + (string_no - 1) * _STRING_SPACING
            fret = int(note.get("fret", 0))
            parts.append(
                f"<text x='{x:.1f}' y='{y - 3:.1f}' font-size='11' text-anchor='middle' "
                f"fill='#000'>{fret}</text>"
            )
            # sustain line when the note lasts past the current measure
            duration = float(note.get("duration", 0.0))
            bar_end = float(measures[bar].get("start", 0.0)) + float(measures[bar].get("duration", 0.0))
            if duration > 0 and float(note.get("start", 0.0)) + duration > bar_end + 1e-6:
                x_end = _LEFT + (bar + 1) * _BAR_WIDTH - 4
                parts.append(
                    f"<line x1='{x + 5:.1f}' y1='{y - 4:.1f}' x2='{x_end:.1f}' y2='{y - 4:.1f}' "
                    f"stroke='#000' stroke-width='1' class='tie'/>"
                )
        dropped_total += dropped
        y_cursor += block_height

    hidden_bars = len(measures) - shown
    notes_line = f"+{hidden_bars} bars not shown" if hidden_bars > 0 else ""
    if dropped_total:
        notes_line += ("   " if notes_line else "") + f"{dropped_total} notes skipped (out of range/string)"
    if notes_line:
        parts.append(
            f"<text x='{_LEFT}' y='{height - 12}' font-size='11' fill='#666'>{_esc(notes_line)}</text>"
        )

    parts.append("</svg>")
    return "\n".join(parts) + "\n"
