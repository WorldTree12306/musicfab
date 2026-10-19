"""Generate deterministic test audio (scales, chords, click track)."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import soundfile as sf


def tone(freq: float, dur: float, sr: int, harmonics=(1.0, 0.4, 0.2)) -> np.ndarray:
    t = np.arange(int(sr * dur)) / sr
    env = np.minimum(1.0, t / 0.01) * np.minimum(1.0, (dur - t) / 0.05)
    sig = sum(a * np.sin(2 * np.pi * freq * h * t) for h, a in enumerate(harmonics, start=1))
    return (sig * env * 0.25).astype(np.float32)


def melody(sr: int, bpm: float = 100) -> np.ndarray:
    beat = 60.0 / bpm
    notes = [60, 62, 64, 65, 67, 69, 71, 72, 71, 69, 67, 64]
    chunks = []
    for p in notes:
        f = 440.0 * 2 ** ((p - 69) / 12)
        chunks.append(tone(f, beat * 0.9, sr))
        chunks.append(np.zeros(int(sr * beat * 0.1), dtype=np.float32))
    return np.concatenate(chunks)


def chord_progression(sr: int, bpm: float = 90) -> np.ndarray:
    beat = 60.0 / bpm
    roots = [60, 57, 53, 55]  # C Am F G
    out = []
    for r in roots:
        seg = np.zeros(int(sr * beat * 2), dtype=np.float32)
        for p in (r, r + 4, r + 7):
            f = 440.0 * 2 ** ((p - 69) / 12)
            seg += tone(f, beat * 2, sr) / 3
        out.append(seg)
    return np.concatenate(out)


def drums(sr: int, bpm: float = 120) -> np.ndarray:
    beat = 60.0 / bpm
    out = []
    rng = np.random.default_rng(42)
    for i in range(8):
        seg = np.zeros(int(sr * beat), dtype=np.float32)
        if i % 4 == 0:  # kick
            seg[: int(sr * 0.12)] = np.sin(2 * np.pi * 60 * np.arange(int(sr * 0.12)) / sr) * np.linspace(1, 0, int(sr * 0.12))
        if i % 4 == 2:  # snare
            n = rng.standard_normal(int(sr * 0.08)).astype(np.float32)
            seg[int(sr * 0.05): int(sr * 0.05) + len(n)] += n * 0.4
        out.append(seg)
    return np.concatenate(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out-dir", default="tests/fixtures")
    ap.add_argument("--sr", type=int, default=44100)
    args = ap.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    sf.write(out / "melody.wav", melody(args.sr), args.sr)
    sf.write(out / "chords.wav", chord_progression(args.sr), args.sr)
    sf.write(out / "drums.wav", drums(args.sr), args.sr)
    print(f"wrote: {[p.name for p in sorted(out.glob('*.wav'))]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
