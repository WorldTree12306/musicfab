"""Stem separation (RipX alternative).

Uses Demucs (MIT, Meta Research) with the ``htdemucs`` bag-of-models.  Weights
are downloaded on first use from ``dl.fbaipublicfiles.com`` and cached by
torch.hub; afterwards everything works fully offline.

The implementation deliberately avoids ``torchaudio`` (version coupling with
torch) and uses :mod:`musicfab.core.audio` for decoding/encoding instead.

Long files are processed in overlapping chunks with a triangular
overlap-add window and disk-backed ``numpy.memmap`` accumulators, so peak RAM
stays around one chunk instead of all four full-length stems.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ..core import audio as audio_io

AUTO_CHUNK_THRESHOLD_SECONDS = 240.0


def _as_stereo(data: np.ndarray) -> np.ndarray:
    if data.ndim == 1:
        return np.stack([data, data], axis=1)
    if data.shape[1] == 1:
        return np.repeat(data, 2, axis=1)
    return data


def _transition_weight(segment_length: int):
    """Triangular window (mirrors Demucs' internal split weighting)."""
    import torch

    half = segment_length // 2
    weight = torch.cat(
        [
            torch.arange(1, half + 1, dtype=torch.float32),
            torch.arange(segment_length - half, 0, -1, dtype=torch.float32),
        ]
    )
    return weight / weight.max()


def _separate_chunked(net, wav, sr: int, sources: list[str], out_dir: Path, overlap: float, chunk_seconds: float):
    """Overlap-add separation with disk-backed accumulators (low RAM)."""
    import torch
    from demucs.apply import apply_model

    channels = wav.shape[1]
    total = wav.shape[-1]
    segment_length = max(int(sr * 0.5), int(sr * float(chunk_seconds)))
    stride = max(1, int(segment_length * (1.0 - max(0.0, min(0.9, overlap)))))
    weight = _transition_weight(segment_length).numpy()

    tmp_dir = out_dir / ".chunked"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    paths = [tmp_dir / f"{name}.f32" for name in sources]
    accum = [np.memmap(p, dtype=np.float32, mode="w+", shape=(channels, total)) for p in paths]
    weight_sum = np.zeros(total, dtype=np.float32)

    try:
        for offset in range(0, total, stride):
            seg = wav[..., offset: offset + segment_length]
            actual = int(seg.shape[-1])
            if actual < segment_length:
                seg = torch.nn.functional.pad(seg, (0, segment_length - actual))
            with torch.no_grad():
                out = apply_model(
                    net,
                    seg,
                    device="cpu",
                    shifts=0,
                    split=False,
                    overlap=0.0,
                    progress=False,
                )
            w = weight[:actual]
            weight_sum[offset: offset + actual] += w
            for i in range(len(sources)):
                accum[i][:, offset: offset + actual] += out[0, i, :, :actual].numpy() * w

        weight_sum = np.maximum(weight_sum, 1e-8)
        for i in range(len(sources)):
            accum[i][...] = accum[i][...] / weight_sum
            accum[i].flush()
    finally:
        del accum
    return paths


def separate(
    audio: str | Path,
    *,
    model: str = "htdemucs",
    output_dir: str | Path,
    shifts: int = 0,
    overlap: float = 0.25,
    chunk_seconds: float = 0.0,
    transcribe_stems: bool = False,
    auto_tempo: bool = False,
    tempo: float = 120.0,
    time_signature: str = "4/4",
) -> dict:
    """Split ``audio`` into stems written as WAV files under ``output_dir``.

    ``chunk_seconds`` > 0 forces chunked processing; ``0`` enables it
    automatically for files longer than :data:`AUTO_CHUNK_THRESHOLD_SECONDS`.
    Chunked mode keeps memory bounded by writing overlap-add accumulators to
    temporary float32 files (removed after the stems are written).

    Returns a manifest dict ``{"model", "sample_rate", "stems": {name: path}}``.
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

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sources = list(net.sources)
    duration = wav.shape[-1] / sr

    effective_chunk = float(chunk_seconds)
    if effective_chunk <= 0 and duration > AUTO_CHUNK_THRESHOLD_SECONDS:
        effective_chunk = float(getattr(net, "segment", None) or 7.8)
    chunked = effective_chunk > 0

    if chunked:
        raw_paths = _separate_chunked(net, wav, sr, sources, out_dir, overlap, effective_chunk)
        stems: dict[str, str] = {}
        try:
            for name, path in zip(sources, raw_paths):
                arr = np.memmap(path, dtype=np.float32, mode="r", shape=(wav.shape[1], wav.shape[-1]))
                values = arr[...].astype(np.float32) * float(ref.std()) + float(ref.mean())
                del arr
                stem_path = out_dir / f"{name}.wav"
                audio_io.write(stem_path, values.T, sr)
                stems[name] = str(stem_path)
                del values
        finally:
            for path in raw_paths:
                Path(path).unlink(missing_ok=True)
            tmp_dir = out_dir / ".chunked"
            try:
                tmp_dir.rmdir()
            except OSError:
                pass
        del wav, ref
    else:
        with torch.no_grad():
            estimates = apply_model(
                net,
                wav,
                device="cpu",
                shifts=int(shifts),
                split=True,
                overlap=float(overlap),
                progress=False,
            )
        estimates = estimates * ref.std() + ref.mean()
        del wav, ref
        stems = {}
        for name, source in zip(sources, estimates[0]):
            stem_path = out_dir / f"{name}.wav"
            audio_io.write(stem_path, source.numpy().T.astype(np.float32), sr)
            stems[name] = str(stem_path)
            del source
        del estimates

    manifest: dict = {
        "input": str(src),
        "model": model,
        "sample_rate": sr,
        "chunked": chunked,
        "chunk_seconds": round(effective_chunk, 2) if chunked else None,
        "stems": stems,
    }

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
                from ..core.export import to_midi

                midi_path = to_midi(proj, out_dir / f"{name}.mid")
                entry = {"notes": len(proj.notes), "project": str(proj_path), "midi": str(midi_path)}
                if info:
                    entry["tempo"] = info["tempo"]
                transcriptions[name] = entry
            except Exception as exc:  # keep separation usable even if a stem is silent
                transcriptions[name] = {"error": str(exc)}
        manifest["transcriptions"] = transcriptions

    (out_dir / "stems.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    return manifest
