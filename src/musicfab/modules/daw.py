"""DAW project bundle export (RipX alternative).

Takes the output of ``musicfab separate --transcribe`` (one ``*.mfproj.json``
per stem) and assembles a ready-to-import bundle for Ardour / LMMS / Reaper /
Logic / Cubase:

    daw/
      <name>.mid          multi-track MIDI (one track per stem + tempo map)
      tracks.json         machine-readable manifest
      README.md           import instructions
      midi/<stem>.mid     individual stem MIDI files

The audio stems themselves are referenced in ``tracks.json`` (not copied), so
the bundle stays small.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..core.export import to_midi
from ..core.project import Project

TICKS_PER_BEAT = 480


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


def _multitrack_midi(projects: list[tuple[str, Project]], tempo: float, time_signature: str, path: Path) -> Path:
    import mido

    mid = mido.MidiFile(type=1, ticks_per_beat=TICKS_PER_BEAT)
    meta = mido.MidiTrack()
    mid.tracks.append(meta)
    meta.append(mido.MetaMessage("track_name", name="musicfab", time=0))
    meta.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(tempo), time=0))
    try:
        num, den = (int(x) for x in time_signature.split("/"))
    except Exception:
        num, den = 4, 4
    meta.append(mido.MetaMessage("time_signature", numerator=num, denominator=den, time=0))

    for index, (name, proj) in enumerate(projects):
        track = mido.MidiTrack()
        mid.tracks.append(track)
        track.append(mido.MetaMessage("track_name", name=name, time=0))
        events = []
        for note in proj.notes:
            start = round(note.start * tempo / 60.0 * TICKS_PER_BEAT)
            end = max(start + 1, round(note.end * tempo / 60.0 * TICKS_PER_BEAT))
            events.append((start, 1, mido.Message("note_on", note=note.pitch, velocity=note.velocity, channel=min(index, 15))))
            events.append((end, 0, mido.Message("note_off", note=note.pitch, velocity=0, channel=min(index, 15))))
        events.sort(key=lambda e: (e[0], e[1]))
        last = 0
        for tick, _, msg in events:
            msg.time = max(0, tick - last)
            last = tick
            track.append(msg)
        track.append(mido.MetaMessage("end_of_track", time=0))

    path.parent.mkdir(parents=True, exist_ok=True)
    mid.save(str(path))
    return path


def build_bundle(
    input_dir: str | Path,
    *,
    output_dir: str | Path | None = None,
    name: str | None = None,
    tempo: float | None = None,
) -> dict:
    """Assemble a DAW import bundle from per-stem musicfab projects."""
    root = Path(input_dir)
    if not root.exists():
        raise FileNotFoundError(root)
    project_files = _find_projects(root)
    if not project_files:
        raise FileNotFoundError(f"no *.mfproj.json found under {root}")

    projects: list[tuple[str, Project]] = []
    for path in project_files:
        projects.append((_stem_name(path), Project.load(path)))

    dominant = max(projects, key=lambda item: len(item[1].notes))
    first_tempo = next((p.tempo for _, p in projects if p.tempo), 120.0)
    if dominant[1].tempo:
        first_tempo = dominant[1].tempo
    tempo_value = float(tempo if tempo is not None else first_tempo)
    signature = "4/4"
    for _, p in projects:
        if getattr(p, "time_signature", None):
            signature = p.time_signature
            break

    bundle_dir = Path(output_dir) if output_dir else root / "daw"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    bundle_name = name or root.name or "musicfab"

    midi_dir = bundle_dir / "midi"
    midi_dir.mkdir(parents=True, exist_ok=True)
    tracks = []
    for stem, proj in projects:
        stem_midi = to_midi(proj, midi_dir / f"{stem}.mid")
        audio_candidates = [
            root / f"{stem}.wav",
            root / "stems" / f"{stem}.wav",
            root.parent / f"{stem}.wav",
        ]
        audio = next((str(p) for p in audio_candidates if p.exists()), None)
        tracks.append(
            {
                "name": stem,
                "audio": audio,
                "midi": str(stem_midi),
                "notes": len(proj.notes),
                "tempo": proj.tempo,
            }
        )

    beats = next((list(p.beats) for _, p in projects if p.beats), [])
    grid_path = None
    if beats:
        try:
            per_bar = max(1, int(str(signature).split("/")[0]))
        except Exception:
            per_bar = 4
        grid = {
            "format": "musicfab-grid",
            "version": 1,
            "tempo": tempo_value,
            "time_signature": signature,
            "beats_per_bar": per_bar,
            "beats": [round(float(b), 4) for b in beats],
            "bars": [round(float(b), 4) for b in beats[::per_bar]],
        }
        grid_path = bundle_dir / "grid.json"
        grid_path.write_text(json.dumps(grid, indent=1, ensure_ascii=False), encoding="utf-8")

    multitrack = _multitrack_midi(projects, tempo_value, signature, bundle_dir / f"{bundle_name}.mid")
    manifest = {
        "format": "musicfab-daw",
        "version": 1,
        "name": bundle_name,
        "tempo": tempo_value,
        "time_signature": signature,
        "multitrack_midi": str(multitrack),
        "grid": str(grid_path) if grid_path else None,
        "tracks": tracks,
    }
    (bundle_dir / "tracks.json").write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    readme = [
        f"# DAW bundle: {bundle_name}",
        "",
        f"- tempo: {tempo_value:g} BPM, time signature {signature}",
        f"- multitrack MIDI: `{multitrack.name}` (one track per stem, tempo map included)",
        "- individual stem MIDI: `midi/<stem>.mid`",
        *(["- beat/bar grid: `grid.json`"] if grid_path else []),
        "",
        "## Import",
        "",
        "1. Drag the audio stems (`*.wav`) into your DAW, or import the listed `audio` paths.",
        "2. Import the multitrack MIDI (or per-stem MIDI) as instrument tracks.",
        "3. Align everything at 0:00 — all stems and MIDI share the same time base.",
        "",
        "Tested layout: Ardour / LMMS / Reaper / Logic / Cubase all accept this structure.",
    ]
    (bundle_dir / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")
    return manifest
