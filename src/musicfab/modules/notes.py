"""Note-level editing & resynthesis (Melodyne alternative).

Workflow
--------
1. ``detect_notes(audio)`` finds note objects with timing/pitch (Basic Pitch).
2. The user edits a JSON table (pitch in semitones, start shift, duration
   scale, velocity scale) for selected notes only.
3. ``apply_edits`` re-synthesises only the edited segments (phase vocoder) and
   leaves every other part of the original recording untouched.

This is a *melodyne-lite*: it works best on clearly separated notes
(monophonic or sparse polyphony). Dense chords may show phase-vocoder
artefacts; for those, prefer the stem separation + per-stem transcription flow.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..core import audio as audio_io
from ..core.project import Note

DEFAULT_EDIT = {
    "semitones": 0.0,
    "start_shift": 0.0,
    "duration_scale": 1.0,
    "velocity_scale": 1.0,
}


@dataclass
class NoteEdit:
    index: int
    semitones: float = 0.0
    start_shift: float = 0.0
    duration_scale: float = 1.0
    velocity_scale: float = 1.0

    @property
    def is_noop(self) -> bool:
        return (
            self.semitones == 0.0
            and self.start_shift == 0.0
            and self.duration_scale == 1.0
            and self.velocity_scale == 1.0
        )


def detect_notes(audio: str | Path, *, model: str = "basicpitch") -> list[Note]:
    """Detect note objects (start/end/pitch/velocity) in an audio file."""
    from .transcribe import transcribe

    proj = transcribe(audio, model=model)
    return proj.notes


def write_template(
    audio: str | Path,
    output: str | Path,
    *,
    model: str = "basicpitch",
) -> Path:
    """Detect notes and write an editable JSON table (all edits are no-ops)."""
    notes = detect_notes(audio, model=model)
    data = {
        "audio": str(audio),
        "model": model,
        "notes": [
            {
                "index": i,
                "start": round(n.start, 4),
                "end": round(n.end, 4),
                "pitch": n.pitch,
                "velocity": n.velocity,
            }
            for i, n in enumerate(notes)
        ],
        "edits": [{"index": i, **DEFAULT_EDIT} for i in range(len(notes))],
        "help": (
            "Edit the 'edits' entries you want to change, then run: "
            "musicfab notes <audio> --edits <this file> -o out.wav. "
            "semitones: pitch shift; start_shift: seconds; duration_scale: 1.0 = unchanged; "
            "velocity_scale: amplitude multiplier."
        ),
    }
    dst = Path(output)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    return dst


def _load_edits(path: str | Path) -> list[NoteEdit]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    entries = raw.get("edits", raw if isinstance(raw, list) else [])
    edits: list[NoteEdit] = []
    for e in entries:
        if "index" not in e:
            continue
        edits.append(
            NoteEdit(
                index=int(e["index"]),
                semitones=float(e.get("semitones", 0.0)),
                start_shift=float(e.get("start_shift", 0.0)),
                duration_scale=float(e.get("duration_scale", 1.0)),
                velocity_scale=float(e.get("velocity_scale", 1.0)),
            )
        )
    return edits


def _fade(n: int, fade: int) -> np.ndarray:
    env = np.ones(n, dtype=np.float32)
    if fade > 0 and n > 2 * fade:
        ramp = np.linspace(0.0, 1.0, fade, endpoint=False, dtype=np.float32)
        env[:fade] = ramp
        env[-fade:] = ramp[::-1]
    return env


def apply_edits(
    audio: str | Path,
    edits_path: str | Path,
    *,
    output: str | Path,
    notes: list[Note] | None = None,
    model: str = "basicpitch",
    margin: float = 0.02,
) -> dict:
    """Apply note edits and write the resynthesised audio.

    Unedited notes/regions are copied verbatim from the original file.
    """
    import librosa

    src = Path(audio)
    data, sr = audio_io.load(src, mono=True)
    if notes is None:
        notes = detect_notes(src, model=model)
    edits = _load_edits(edits_path)
    out = data.astype(np.float32).copy()
    applied = 0
    errors: list[str] = []

    for e in edits:
        if e.is_noop:
            continue
        if e.index < 0 or e.index >= len(notes):
            errors.append(f"index {e.index} out of range (0..{len(notes) - 1})")
            continue
        n = notes[e.index]
        s = max(0, int((n.start - margin) * sr))
        t = min(len(data), int((n.end + margin) * sr))
        if t - s < int(0.02 * sr):
            errors.append(f"note {e.index} too short to edit")
            continue
        seg = data[s:t].astype(np.float32)
        try:
            if e.semitones:
                seg = librosa.effects.pitch_shift(seg, sr=sr, n_steps=float(e.semitones))
            if e.duration_scale and abs(e.duration_scale - 1.0) > 1e-6:
                seg = librosa.effects.time_stretch(seg, rate=1.0 / float(e.duration_scale))
            if e.velocity_scale and abs(e.velocity_scale - 1.0) > 1e-6:
                seg = seg * float(e.velocity_scale)
        except Exception as exc:  # keep other edits usable
            errors.append(f"note {e.index}: {exc}")
            continue

        # mute the original region, then mix the transformed segment at its new spot
        out[s:t] *= 0.0
        new_start = int(max(0, (n.start + margin + e.start_shift) * sr))
        new_end = new_start + len(seg)
        if new_end > len(out):
            out = np.pad(out, (0, new_end - len(out)))
        env = _fade(len(seg), max(1, int(0.01 * sr)))
        out[new_start:new_end] += seg * env
        applied += 1

    peak = float(np.max(np.abs(out))) if len(out) else 0.0
    if peak > 1.0:
        out = out / peak
    dst = Path(output)
    audio_io.write(dst, out.astype(np.float32), sr)

    return {
        "input": str(src),
        "output": str(dst),
        "sample_rate": sr,
        "notes_detected": len(notes),
        "edits_applied": applied,
        "errors": errors,
        "peak": round(peak, 4),
    }
