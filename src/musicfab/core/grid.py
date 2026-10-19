"""Beat-grid helpers shared by transcription and score export."""
from __future__ import annotations


def snap_to_beat_grid(t: float, beats: list[float], subdivisions: int, fallback_period: float) -> float:
    """Snap a time (seconds) to a beat grid with ``subdivisions`` per beat.

    Between detected beats the local beat period is used (so rubato is
    followed); before the first / after the last beat the nearest period is
    extrapolated.  With fewer than two beats a regular grid derived from
    ``fallback_period`` is used.
    """
    if subdivisions < 1:
        subdivisions = 1
    if len(beats) >= 2 and beats[-1] > beats[0]:
        import bisect

        idx = bisect.bisect_right(beats, t) - 1
        if idx < 0:
            idx = 0
        if idx >= len(beats) - 1:
            period = beats[-1] - beats[-2]
            step = period / subdivisions
            k = round((t - beats[-1]) / step)
            return beats[-1] + k * step
        period = beats[idx + 1] - beats[idx]
        step = period / subdivisions
        k = round((t - beats[idx]) / step)
        return beats[idx] + k * step
    step = max(1e-6, fallback_period / subdivisions)
    return round(t / step) * step
