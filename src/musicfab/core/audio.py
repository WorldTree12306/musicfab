"""Audio decoding/probing helpers (offline-capable)."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np

try:  # soundfile is a hard dependency
    import soundfile as sf
except Exception:  # pragma: no cover
    sf = None


def _ffmpeg() -> str | None:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:  # imageio-ffmpeg ships a static ffmpeg binary
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def probe(path: str | Path) -> dict:
    """Return basic audio metadata without fully decoding if possible."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    info: dict = {"path": str(path), "bytes": path.stat().st_size}
    if sf is not None:
        try:
            meta = sf.info(str(path))
            info.update(
                format=meta.format,
                subtype=meta.subtype,
                sample_rate=meta.samplerate,
                channels=meta.channels,
                frames=meta.frames,
                duration=round(meta.frames / meta.samplerate, 3) if meta.samplerate else None,
            )
            return info
        except Exception as exc:  # fall back to ffprobe/ffmpeg
            info["soundfile_error"] = str(exc)
    exe = _ffmpeg()
    if exe:
        try:
            out = subprocess.run(
                [exe, "-hide_banner", "-i", str(path)], capture_output=True, text=True, timeout=60
            ).stderr
            for line in out.splitlines():
                if "Duration:" in line:
                    info["duration_text"] = line.split("Duration:")[1].split(",")[0].strip()
                if "Audio:" in line:
                    info["audio_stream"] = line.split("Audio:")[1].strip()
            info["ffmpeg"] = exe
        except Exception as exc:  # pragma: no cover
            info["ffmpeg_error"] = str(exc)
    return info


def _ensure_finite(data: np.ndarray, path: str | Path) -> None:
    """Reject NaN/Inf samples early instead of producing garbage downstream."""
    if not bool(np.isfinite(data).all()):
        raise ValueError(f"{path}: audio contains NaN/Inf")


def load(path: str | Path, sample_rate: int | None = None, mono: bool = True) -> tuple[np.ndarray, int]:
    """Load audio as float32 [frames, channels] (or [frames] when mono)."""
    path = Path(path)
    data = None
    sr = 0
    if sf is not None:
        try:
            data, sr = sf.read(str(path), dtype="float32", always_2d=True)
            if sample_rate and sr != sample_rate:
                data = resample(data, sr, sample_rate)
                sr = sample_rate
            if mono:
                data = data.mean(axis=1)
        except Exception:
            data = None  # fall back to ffmpeg decoding below
    if data is not None:
        _ensure_finite(data, path)
        return data, sr
    exe = _ffmpeg()
    if not exe:
        raise RuntimeError("cannot decode audio: install soundfile or ffmpeg/imageio-ffmpeg")
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "decoded.wav"
        cmd = [exe, "-y", "-hide_banner", "-loglevel", "error", "-i", str(path)]
        if mono:
            cmd += ["-ac", "1"]
        if sample_rate:
            cmd += ["-ar", str(sample_rate)]
        cmd += [str(wav)]
        subprocess.run(cmd, check=True, timeout=600)
        data, sr = sf.read(str(wav), dtype="float32", always_2d=False)
        _ensure_finite(data, path)
        return data, sr


def write(path: str | Path, data: np.ndarray, sample_rate: int) -> None:
    if sf is None:
        raise RuntimeError("soundfile is required to write audio")
    _ensure_finite(np.asarray(data), path)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), data, sample_rate)


def resample(data: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    if src_sr == dst_sr:
        return data
    from math import gcd

    from scipy.signal import resample_poly

    g = gcd(int(src_sr), int(dst_sr))
    up, down = int(dst_sr) // g, int(src_sr) // g
    return resample_poly(data, up, down, axis=0).astype(np.float32)


def rms(data: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(data), dtype=np.float64)))
