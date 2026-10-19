"""Beat / tempo estimation (rhythm layer for transcription & practice).

Uses librosa's onset-envelope + dynamic-programming beat tracker.  Fully
offline, no extra models.  The detected tempo and beat grid are attached to
:class:`musicfab.core.project.Project` and written into MIDI/MusicXML.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np




def _fix_tempo_octave(y, sr: int, tempo: float, hop: int = 512) -> float:
    """Correct common half/double tempo errors using onset autocorrelation."""
    import librosa

    if tempo <= 0:
        return tempo
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    if onset_env.size < 8:
        return tempo

    def score(bpm: float) -> float:
        lag = int(round(60.0 / bpm * sr / hop))
        if lag < 1 or lag >= onset_env.size:
            return -1.0
        ac = librosa.autocorrelate(onset_env, max_size=lag + 1)
        return float(ac[lag] / (ac[0] + 1e-9))

    candidates = [c for c in (tempo * 0.5, tempo, tempo * 2.0) if 50.0 <= c <= 220.0]
    if not candidates:
        return tempo
    base = score(tempo)
    best = max(candidates, key=score)
    if best != tempo and score(best) > base * 1.2:
        return float(best)
    return float(tempo)


def detect_beats(
    audio: str | Path,
    *,
    start_bpm: float = 120.0,
    tightness: float = 100.0,
    beats_per_bar: int = 4,
    sample_rate: int = 22050,
) -> dict:
    """Return ``{"tempo", "beats", "downbeats", "time_signature"}``.

    ``downbeats`` is a simple every-``beats_per_bar`` heuristic (no downbeat
    model is used); treat it as a starting point for editing.
    """
    import librosa

    src = Path(audio)
    if not src.exists():
        raise FileNotFoundError(src)
    y, _ = librosa.load(str(src), sr=sample_rate, mono=True)
    tempo, beat_times = librosa.beat.beat_track(
        y=y, sr=sample_rate, start_bpm=float(start_bpm), tightness=float(tightness), units="time"
    )
    tempo_value = float(np.atleast_1d(tempo)[0])
    tempo_value = _fix_tempo_octave(y, sample_rate, tempo_value)
    beats = [round(float(t), 4) for t in np.atleast_1d(beat_times)]
    downbeats = [b for i, b in enumerate(beats) if i % max(1, int(beats_per_bar)) == 0]
    return {
        "tempo": round(tempo_value, 2),
        "beats": beats,
        "downbeats": downbeats,
        "time_signature": f"{int(beats_per_bar)}/4",
    }


def beat_grid(tempo: float, duration: float, offset: float = 0.0) -> list[float]:
    """Generate a regular beat grid (seconds) when detection is not desired."""
    if tempo <= 0:
        raise ValueError("tempo must be positive")
    period = 60.0 / float(tempo)
    n = int(max(0.0, duration - offset) // period) + 1
    return [round(offset + i * period, 4) for i in range(n)]
