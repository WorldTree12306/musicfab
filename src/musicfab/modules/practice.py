"""Speed / transpose / loop practice helper (Transcribe! alternative).

Everything is offline: librosa's phase-vocoder is used for both time stretching
and pitch shifting, so no external binaries are required.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ..core import audio as audio_io


def _slice(data: np.ndarray, sr: int, loop: tuple[float, float] | None) -> np.ndarray:
    if not loop:
        return data
    start, end = float(loop[0]), float(loop[1])
    if end <= start:
        raise ValueError(f"loop end ({end}) must be greater than start ({start})")
    i0 = max(0, int(start * sr))
    i1 = min(len(data), int(end * sr))
    if i1 <= i0:
        raise ValueError("loop range is outside the audio duration")
    return data[i0:i1].copy()


def practice(
    audio: str | Path,
    *,
    tempo: float = 1.0,
    semitones: float = 0.0,
    loop: tuple[float, float] | None = None,
    beat_loop: int | None = None,
    beat_start: int = 0,
    output: str | Path,
) -> Path:
    """Render a practice version of ``audio``.

    Parameters
    ----------
    tempo:
        Playback speed. ``0.5`` = half speed (longer), ``2.0`` = double speed.
    semitones:
        Pitch shift in semitones (float allowed).
    loop:
        Optional ``(start_seconds, end_seconds)`` excerpt.
    beat_loop / beat_start:
        Loop exactly ``beat_loop`` detected beats starting at beat index
        ``beat_start`` (ignored when ``loop`` is given).  The beat grid is
        detected automatically with :func:`musicfab.modules.beats.detect_beats`.
    """
    if tempo <= 0:
        raise ValueError("tempo must be positive")
    import librosa

    if beat_loop is not None:
        if int(beat_loop) < 1:
            raise ValueError("--loop-beats must be >= 1")
        if int(beat_start) < 0:
            raise ValueError("--beat-start must be >= 0")
    beat_loop_ignored = bool(beat_loop and loop)
    beat_meta = None
    if beat_loop and not loop:
        from .beats import detect_beats

        beats = detect_beats(audio)["beats"]
        if len(beats) < 2:
            raise ValueError("not enough beats detected for --loop-beats")
        start_idx = int(beat_start)
        end_idx = start_idx + int(beat_loop)
        if start_idx >= len(beats) - 1:
            raise ValueError(f"beat_start {start_idx} outside detected beats (0..{len(beats) - 2})")
        start = beats[start_idx]
        if end_idx < len(beats):
            end = beats[end_idx]
        else:  # extend the last interval, clamped to the audio below
            period = beats[-1] - beats[-2]
            end = beats[-1] + (end_idx - (len(beats) - 1)) * period
        loop = (start, end)
        beat_meta = {"beat_loop": int(beat_loop), "beat_start": start_idx}

    data, sr = audio_io.load(audio, mono=True)
    input_duration = len(data) / sr
    loop_clamped = False
    if loop:
        start, end = float(loop[0]), float(loop[1])
        if end > input_duration:
            end = input_duration
            loop = (start, end)
            loop_clamped = True
    data = _slice(data, sr, loop)

    if semitones:
        data = librosa.effects.pitch_shift(data, sr=sr, n_steps=float(semitones))
    if abs(tempo - 1.0) > 1e-9:
        data = librosa.effects.time_stretch(data, rate=float(tempo))

    out = Path(output)
    audio_io.write(out, data.astype(np.float32), sr)

    meta = {
        "input": str(audio),
        "output": str(out),
        "sample_rate": sr,
        "tempo": float(tempo),
        "semitones": float(semitones),
        "loop": list(loop) if loop else None,
        "loop_clamped": loop_clamped,
        "beat_loop_ignored": beat_loop_ignored,
        "beat_loop": beat_meta["beat_loop"] if beat_meta else None,
        "beat_start": beat_meta["beat_start"] if beat_meta else None,
        "input_duration": round(input_duration, 3),
        "output_duration": round(len(data) / sr, 3),
    }
    Path(str(out) + ".practice.json").write_text(
        json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    return out
