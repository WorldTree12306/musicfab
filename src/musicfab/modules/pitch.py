"""Note-level pitch shifting (Melodyne alternative).

Uses a phase-vocoder pitch shifter (librosa) so it works fully offline.  For
formant-preserving / note-object editing see ``musicfab.notes`` (Phase 2b).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from ..core import audio as audio_io


def shift_audio(audio: str | Path, *, semitones: float, output: str | Path) -> Path:
    """Shift the whole audio by ``semitones`` while keeping its duration."""
    import librosa

    data, sr = audio_io.load(audio, mono=True)
    shifted = librosa.effects.pitch_shift(data, sr=sr, n_steps=float(semitones))
    out = Path(output)
    audio_io.write(out, shifted.astype(np.float32), sr)
    return out


def shift_notes(notes, semitones: float):
    """Shift a list of note objects (score-level, no audio resynthesis)."""
    import copy

    out = []
    for n in notes:
        clone = copy.copy(n)
        clone.pitch = int(round(n.pitch + semitones))
        out.append(clone)
    return out
