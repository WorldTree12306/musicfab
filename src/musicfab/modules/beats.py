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


def _downbeat_phase(y, sr: int, beats: list[float], beats_per_bar: int, hop: int = 512) -> tuple[int, float]:
    """Estimate the downbeat phase from low-frequency (bass/kick) onset energy.

    Returns ``(phase, confidence)`` where ``phase`` is the index (0..N-1) of
    the bar position that carries the strongest low-frequency onsets.
    """
    import librosa

    if len(beats) < beats_per_bar * 2 or beats_per_bar < 2:
        return 0, 0.0
    stft = np.abs(librosa.stft(y, n_fft=1024, hop_length=hop))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=1024)
    low_band = stft[freqs < 150.0].sum(axis=0)
    low_onset = np.maximum(0.0, np.diff(low_band, prepend=low_band[0]))
    values = []
    for t in beats:
        idx = int(round(float(t) * sr / hop))
        window = low_onset[max(0, idx - 2): idx + 3]
        values.append(float(window.max()) if window.size else 0.0)
    values = np.asarray(values, dtype=np.float64)
    if values.max() <= 0:
        return 0, 0.0
    best_phase, best_score = 0, -1.0
    for phase in range(beats_per_bar):
        inside = values[phase::beats_per_bar]
        if inside.size < 2:
            continue
        outside_mask = np.ones(len(values), dtype=bool)
        outside_mask[phase::beats_per_bar] = False
        outside = values[outside_mask]
        score = float(inside.mean() / (outside.mean() + 1e-9)) if outside.size else 0.0
        if score > best_score:
            best_phase, best_score = phase, score
    return best_phase, best_score


def detect_beats(
    audio: str | Path,
    *,
    start_bpm: float = 120.0,
    tightness: float = 100.0,
    beats_per_bar: int = 4,
    sample_rate: int = 22050,
) -> dict:
    """Return ``{"tempo", "beats", "downbeats", "time_signature", ...}``.

    Downbeats are estimated from low-frequency onset energy per bar position
    (kick/bass heuristic); ``downbeat_confidence`` is the ratio between the
    chosen phase and the other phases (1.0 = no preference).
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
    if not np.isfinite(tempo_value) or tempo_value <= 0:
        tempo_value = float(start_bpm)
    else:
        tempo_value = _fix_tempo_octave(y, sample_rate, tempo_value)
    beats = [round(float(t), 4) for t in np.atleast_1d(beat_times)]
    per_bar = max(1, int(beats_per_bar))
    phase, confidence = _downbeat_phase(y, sample_rate, beats, per_bar)
    downbeats = [b for i, b in enumerate(beats) if i % per_bar == phase]
    return {
        "tempo": round(tempo_value, 2),
        "beats": beats,
        "downbeats": downbeats,
        "downbeat_phase": phase,
        "downbeat_confidence": round(float(confidence), 3),
        "time_signature": f"{per_bar}/4",
    }


def beat_grid(tempo: float, duration: float, offset: float = 0.0) -> list[float]:
    """Generate a regular beat grid (seconds) when detection is not desired."""
    if tempo <= 0:
        raise ValueError("tempo must be positive")
    period = 60.0 / float(tempo)
    n = int(max(0.0, duration - offset) // period) + 1
    return [round(offset + i * period, 4) for i in range(n)]
