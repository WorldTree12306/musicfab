"""Project -> MIDI / MusicXML exporters."""
from __future__ import annotations

import warnings
from fractions import Fraction
from pathlib import Path

from .grid import snap_to_beat_grid
from .project import Project


def _parse_time_signature(value: str) -> tuple[int, int]:
    """Parse ``"4/4"`` style signatures, falling back to 4/4."""
    try:
        num_s, den_s = str(value).split("/")
        num, den = int(num_s), int(den_s)
        if num > 0 and den in (1, 2, 4, 8, 16, 32):
            return num, den
    except Exception:  # noqa: BLE001 - tolerate user input
        pass
    return 4, 4


def to_midi(project: Project, path: str | Path, ticks_per_beat: int = 480) -> Path:
    """Write a Standard MIDI File (type 1)."""
    import mido

    mid = mido.MidiFile(type=1, ticks_per_beat=ticks_per_beat)
    tempo = mido.bpm2tempo(project.tempo or 120.0)
    numerator, denominator = _parse_time_signature(getattr(project, "time_signature", "4/4"))
    for i, track in enumerate(project.tracks or []):
        mt = mido.MidiTrack()
        mid.tracks.append(mt)
        mt.append(mido.MetaMessage("track_name", name=track.name or f"track{i}", time=0))
        if i == 0:
            mt.append(mido.MetaMessage("set_tempo", tempo=tempo, time=0))
            mt.append(
                mido.MetaMessage(
                    "time_signature", numerator=numerator, denominator=denominator, time=0
                )
            )
        events = []
        for n in track.notes:
            start = round(n.start * (project.tempo or 120) / 60 * ticks_per_beat)
            end = round(n.end * (project.tempo or 120) / 60 * ticks_per_beat)
            events.append((start, 1, mido.Message("note_on", note=n.pitch, velocity=n.velocity,
                                                  channel=min(i, 15), time=0)))
            events.append((end, 0, mido.Message("note_off", note=n.pitch, velocity=0,
                                                channel=min(i, 15), time=0)))
        events.sort(key=lambda e: (e[0], e[1]))
        last = 0
        for tick, _, msg in events:
            msg.time = max(0, tick - last)
            last = tick
            mt.append(msg)
        mt.append(mido.MetaMessage("end_of_track", time=0))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mid.save(str(path))
    return path


_BINARY_UNITS = (192, 96, 48, 24, 12, 6, 3)  # quarters in 1/48 units: 4, 2, 1, 1/2, 1/4, 1/8, 1/16
_SIXTEENTH = Fraction(1, 16)


def _expressible_quarter_lengths(ql) -> list[Fraction]:
    """Split an arbitrary positive quarterLength into notation-safe values.

    Durations live on a 1/48 grid: binary note values (whole ... 16th) via
    greedy decomposition — e.g. ``3/16 -> [1/8, 1/16]`` — and plain triplet
    eighths (``1/3``) for durations that are an exact number of them (``2/3 ->
    [1/3, 1/3]``).  Anything below a 16th collapses to a single 16th.
    """
    ql = float(ql)
    if ql <= 0:
        return [_SIXTEENTH]
    units = int(round(ql * 48))
    if units >= 16 and units % 16 == 0 and units % 3 != 0:
        return [Fraction(1, 3)] * (units // 16)
    units = max(3, 3 * max(1, round(units / 3.0)))  # snap to the 1/16 grid
    parts_units: list[int] = []
    remaining = units
    while remaining >= 3:
        for size in _BINARY_UNITS:
            if size <= remaining:
                parts_units.append(size)
                remaining -= size
                break
    if remaining and parts_units:
        parts_units[-1] += remaining
    elif remaining:
        parts_units.append(3)
    return [Fraction(u, 48) for u in parts_units]


def _to_musicxml_direct(project: Project, path: Path, *, quantize_beats: int | None = None) -> Path:
    """Build the MusicXML score with music21 objects directly (no MIDI file)."""
    import copy as _copy

    from music21 import meter, note as m21note, stream, tempo as m21tempo, tie as m21tie

    tempo_bpm = float(project.tempo or 120.0)
    sec_to_ql = tempo_bpm / 60.0
    beats = [float(b) for b in (getattr(project, "beats", []) or [])]
    fallback_period = 60.0 / max(1e-6, tempo_bpm)
    subdiv = int(quantize_beats) if quantize_beats and int(quantize_beats) >= 1 else 0

    def _snap_time(t: float) -> Fraction:
        if subdiv:
            # snap_to_beat_grid works in seconds; convert to quarterLength
            v_seconds = snap_to_beat_grid(float(t), beats, subdiv, fallback_period)
            v_ql = max(0.0, float(v_seconds) * sec_to_ql)
        else:
            v_ql = max(0.0, float(t) * sec_to_ql)
        # MusicXML cannot notate arbitrary fractions; use a 16th-note grid
        # (same effective granularity as the old MIDI round-trip).  This also
        # prevents makeNotation() from creating unrepresentable slivers when a
        # note lands just before a barline.
        v_ql = max(0.0, round(v_ql * 16) / 16)
        return Fraction(int(round(v_ql * 16)), 16)

    score = stream.Score()
    for idx, track in enumerate(project.tracks or []):
        part = stream.Part(id=f"P{idx + 1}")
        part.partName = track.name or f"track{idx}"
        part.insert(0, m21tempo.MetronomeMark(number=tempo_bpm))
        num, den = _parse_time_signature(project.time_signature)
        part.insert(0, meter.TimeSignature(f"{num}/{den}"))

        # work on copies: the caller's project must stay untouched
        notes = sorted((_copy.copy(n) for n in track.notes), key=lambda n: n.start)
        for n in notes:
            start_ql = _snap_time(n.start)
            end_ql = _snap_time(n.end)
            dur = end_ql - start_ql
            if dur <= 0:
                dur = _SIXTEENTH
            pieces = _expressible_quarter_lengths(float(dur))
            cursor = start_ql
            for k, piece in enumerate(pieces):
                m21n = m21note.Note(int(n.pitch), quarterLength=piece)
                m21n.volume.velocity = max(1, min(127, int(n.velocity)))
                if len(pieces) > 1:
                    m21n.tie = m21tie.Tie(
                        "start" if k == 0 else "stop" if k == len(pieces) - 1 else "continue"
                    )
                part.insert(cursor, m21n)
                cursor += piece
        score.insert(0, part)

    try:
        score.makeNotation(inPlace=True)
    except Exception:  # noqa: BLE001 - write the raw stream if notation fails
        pass
    score.write("musicxml", fp=str(path))
    return path


def _to_musicxml_via_midi(project: Project, path: Path, *, quantize_beats: int | None = None) -> Path:
    """Historical path: write a MIDI file and re-parse it with music21.

    music21's MIDI importer quantizes durations to 16th/triplet eighths and
    drops track names; kept only as a fallback for exotic inputs.
    """
    import copy as _copy
    import tempfile

    from music21 import converter

    proj = _copy.deepcopy(project)  # never mutate the caller's project
    if quantize_beats and int(quantize_beats) >= 1:
        beats = list(getattr(proj, "beats", []) or [])
        fallback = 60.0 / max(1e-6, float(proj.tempo or 120.0))
        for note in proj.notes:
            note.start = round(snap_to_beat_grid(note.start, beats, int(quantize_beats), fallback), 4)
            note.end = round(snap_to_beat_grid(note.end, beats, int(quantize_beats), fallback), 4)
            if note.end <= note.start:
                note.end = round(note.start + fallback / int(quantize_beats), 4)

    with tempfile.TemporaryDirectory() as tmp:
        midi_path = Path(tmp) / "score.mid"
        to_midi(proj, midi_path)
        score = converter.parse(str(midi_path))
        score.write("musicxml", fp=str(path))
    return path


def to_musicxml(project: Project, path: str | Path, *, quantize_beats: int | None = None) -> Path:
    """Write a MusicXML score via direct music21 construction.

    One ``stream.Part`` per track (part names, tempo and time signature are
    preserved); seconds are converted to quarterLengths and inexpressible
    durations split into tied chains of notation-safe values.  When
    ``quantize_beats`` is given, note boundaries snap to the project's beat
    grid (or a tempo-derived grid) on **copies** — the input project is never
    modified.  Without ``quantize_beats`` boundaries snap to a 16th-note grid,
    which is what the previous MIDI round-trip did implicitly.  If direct
    construction fails, the old MIDI round-trip runs as a fallback (warning).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        return _to_musicxml_direct(project, path, quantize_beats=quantize_beats)
    except Exception as exc:  # noqa: BLE001 - keep export working
        warnings.warn(
            f"direct MusicXML construction failed ({exc}); falling back to MIDI round-trip"
        )
        return _to_musicxml_via_midi(project, path, quantize_beats=quantize_beats)

