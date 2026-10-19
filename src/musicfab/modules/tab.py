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
    raise ValueError(f"unsupported tab output format: {fmt!r} (json/midi/musicxml)")
