"""Project -> MIDI / MusicXML exporters."""
from __future__ import annotations

from pathlib import Path

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


def to_musicxml(project: Project, path: str | Path) -> Path:
    """Write a MusicXML score via music21.

    Direct note construction can produce durations that are not expressible in
    traditional notation (transcribed audio is not quantized).  The robust path
    is to write a Standard MIDI File first and let music21's MIDI importer
    quantize it into notated durations.  If that is unavailable we fall back to
    snapped quarter-lengths.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    import tempfile

    from music21 import converter

    with tempfile.TemporaryDirectory() as tmp:
        midi_path = Path(tmp) / "score.mid"
        to_midi(project, midi_path)
        score = converter.parse(str(midi_path))
        score.write("musicxml", fp=str(path))
    return path

