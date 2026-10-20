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
import shutil
from pathlib import Path

import numpy as np

from ..core import audio as audio_io

AUTO_CHUNK_THRESHOLD_SECONDS = 240.0


def shared_tempo_info(
    src: str | Path,
    *,
    fallback_tempo: float = 120.0,
    fallback_signature: str = "4/4",
) -> dict:
    """Detect tempo/beats **once on the mixture** and share across all stems.

    Returns ``{"tempo", "time_signature", "beats"}``; ``beats`` is ``None``
    when detection failed and callers should fall back to a fixed tempo.
    """
    try:
        from .beats import detect_beats

        info = detect_beats(src)
        return {
            "tempo": float(info["tempo"]),
            "time_signature": str(info["time_signature"]),
            "beats": list(info["beats"]),
        }
    except Exception:  # noqa: BLE001 - beat detection is best-effort
        return {
            "tempo": float(fallback_tempo),
            "time_signature": str(fallback_signature),
            "beats": None,
        }


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


def _separate_chunked(
    net, wav, sr: int, sources: list[str], out_dir: Path, overlap: float, chunk_seconds: float
) -> tuple[list[Path], int]:
    """Overlap-add separation with disk-backed accumulators (low RAM).

    Returns ``(memmap_paths, pad)``.  The input is reflect-padded by half a
    segment on both sides so the first/last chunks see full context (matching
    Demucs' own split behaviour); the caller reads the result back from
    ``[pad : pad + original_length]``.
    """
    import torch
    from demucs.apply import apply_model

    channels = wav.shape[1]
    total = wav.shape[-1]
    segment_length = max(int(sr * 0.5), int(sr * float(chunk_seconds)))
    stride = max(1, int(segment_length * (1.0 - max(0.0, min(0.9, overlap)))))
    weight = _transition_weight(segment_length).numpy()
    # reflect padding needs pad <= len - 1; degenerate inputs skip padding
    pad = min(segment_length // 2, max(0, total - 1))
    if pad > 0:
        wav = torch.nn.functional.pad(wav, (pad, pad), mode="reflect")
    padded_total = wav.shape[-1]

    tmp_dir = out_dir / ".chunked"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    paths = [tmp_dir / f"{name}.f32" for name in sources]
    accum = [np.memmap(p, dtype=np.float32, mode="w+", shape=(channels, padded_total)) for p in paths]
    weight_sum = np.zeros(padded_total, dtype=np.float32)

    try:
        for offset in range(0, padded_total, stride):
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
            accum[i][:, :] /= weight_sum  # in-place broadcast; no full-track temp array
            accum[i].flush()
    finally:
        del accum  # close memmap handles before any cleanup path
    return paths, pad


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
    quantize_beats: int = 0,
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
        tmp_dir = out_dir / ".chunked"
        stems: dict[str, str] = {}
        try:
            raw_paths, pad = _separate_chunked(net, wav, sr, sources, out_dir, overlap, effective_chunk)
            padded_total = wav.shape[-1] + 2 * pad
            import soundfile as sf

            block_frames = 1_000_000  # stream blocks; never materialise a full stem
            for name, path in zip(sources, raw_paths):
                arr = np.memmap(path, dtype=np.float32, mode="r", shape=(wav.shape[1], padded_total))
                try:
                    stem_path = out_dir / f"{name}.wav"
                    with sf.SoundFile(
                        str(stem_path), mode="w", samplerate=sr, channels=wav.shape[1], subtype="FLOAT"
                    ) as fout:
                        std, mean = float(ref.std()), float(ref.mean())
                        for start in range(pad, pad + wav.shape[-1], block_frames):
                            stop = min(start + block_frames, pad + wav.shape[-1])
                            block = arr[:, start:stop].astype(np.float32)
                            block *= std
                            block += mean
                            fout.write(block.T)
                    stems[name] = str(stem_path)
                finally:
                    del arr  # release the memmap handle (Windows rmtree below)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
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

        # detect tempo once on the mixture and share it with every stem:
        # faster than per-stem detection and keeps all parts on one beat grid
        shared = (
            shared_tempo_info(src, fallback_tempo=tempo, fallback_signature=time_signature)
            if auto_tempo
            else None
        )
        stem_tempo = shared["tempo"] if shared else float(tempo)
        stem_signature = shared["time_signature"] if shared else time_signature
        stem_beats = shared["beats"] if shared else None

        transcriptions = {}
        for name, path in stems.items():
            try:
                proj = transcribe(
                    path,
                    model="basicpitch",
                    tempo=stem_tempo,
                    time_signature=stem_signature,
                    beats=stem_beats,
                    quantize_beats=int(quantize_beats) or None,
                )
                proj_path = out_dir / f"{name}.mfproj.json"
                proj.save(proj_path)
                from ..core.export import to_midi

                midi_path = to_midi(proj, out_dir / f"{name}.mid")
                entry = {"notes": len(proj.notes), "project": str(proj_path), "midi": str(midi_path)}
                if shared:
                    entry["tempo"] = shared["tempo"]
                transcriptions[name] = entry
            except Exception as exc:  # keep separation usable even if a stem is silent
                transcriptions[name] = {"error": str(exc)}
        manifest["transcriptions"] = transcriptions

    (out_dir / "stems.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    return manifest
