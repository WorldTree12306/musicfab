"""Stem separation (RipX alternative).

Uses Demucs (MIT, Meta Research) with the ``htdemucs`` bag-of-models.  Weights
are downloaded on first use from ``dl.fbaipublicfiles.com`` and cached by
torch.hub; afterwards everything works fully offline.

The implementation deliberately avoids ``torchaudio`` (version coupling with
torch) and uses :mod:`musicfab.core.audio` for decoding/encoding instead.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ..core import audio as audio_io


def _as_stereo(data: np.ndarray) -> np.ndarray:
    if data.ndim == 1:
        return np.stack([data, data], axis=1)
    if data.shape[1] == 1:
        return np.repeat(data, 2, axis=1)
    return data


def separate(
    audio: str | Path,
    *,
    model: str = "htdemucs",
    output_dir: str | Path,
    shifts: int = 0,
    overlap: float = 0.25,
    transcribe_stems: bool = False,
    auto_tempo: bool = False,
    tempo: float = 120.0,
    time_signature: str = "4/4",
) -> dict:
    """Split ``audio`` into stems written as WAV files under ``output_dir``.

    Returns a manifest dict ``{"model", "sample_rate", "stems": {name: path}}``.

    Memory note: Demucs processes the whole file and keeps all stems in memory
    (a 10-minute stereo track peaks around 1.5-2 GB).  For very long material
    split the input first, e.g. ``ffmpeg -f segment -segment_time 300``.
    """
    import torch
    from demucs.apply import apply_model
    from demucs.pretrained import get_model

    src = Path(audio)
    if not src.exists():
        raise FileNotFoundError(src)

    net = get_model(model)
    net.eval()
    sr = int(net.samplerate)

    data, _ = audio_io.load(src, sample_rate=sr, mono=False)
    data = _as_stereo(np.asarray(data, dtype=np.float32))

    wav = torch.from_numpy(data.T)[None]  # [1, channels, samples]
    del data
    ref = wav.mean(0)
    wav = (wav - ref.mean()) / (ref.std() + 1e-8)
    with torch.no_grad():
        sources = apply_model(
            net, wav, device="cpu", shifts=int(shifts), split=True, overlap=float(overlap), progress=False
        )
    del wav
    sources = sources * ref.std() + ref.mean()
    del ref

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stems: dict[str, str] = {}
    for name, source in zip(net.sources, sources[0]):
        stem_path = out_dir / f"{name}.wav"
        audio_io.write(stem_path, source.numpy().T.astype(np.float32), sr)
        stems[name] = str(stem_path)

    manifest: dict = {"input": str(src), "model": model, "sample_rate": sr, "stems": stems}

    if transcribe_stems:
        from .transcribe import transcribe

        transcriptions = {}
        for name, path in stems.items():
            try:
                info = None
                if auto_tempo:
                    from .beats import detect_beats

                    info = detect_beats(path)
                proj = transcribe(
                    path,
                    model="basicpitch",
                    tempo=info["tempo"] if info else tempo,
                    time_signature=info["time_signature"] if info else time_signature,
                    beats=info["beats"] if info else None,
                )
                proj_path = out_dir / f"{name}.mfproj.json"
                proj.save(proj_path)
                entry = {"notes": len(proj.notes), "project": str(proj_path)}
                if info:
                    entry["tempo"] = info["tempo"]
                transcriptions[name] = entry
            except Exception as exc:  # keep separation usable even if a stem is silent
                transcriptions[name] = {"error": str(exc)}
        manifest["transcriptions"] = transcriptions

    (out_dir / "stems.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    return manifest
