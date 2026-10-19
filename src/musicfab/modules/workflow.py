"""One-command RipX-style workflow: audio -> stems -> transcriptions -> DAW/score.

Pipeline::

    audio
      └─ separate (Demucs htdemucs, chunked overlap-add for long files)
           ├─ <stem>.wav
           ├─ <stem>.mfproj.json   (Basic Pitch transcription, auto tempo)
           ├─ <stem>.mid
           └─ stem.mid
      └─ daw/      multi-track MIDI + grid.json + README
      └─ score      multi-part MusicXML/PDF (optional)

Everything is local; only Demucs/Basic Pitch model weights are downloaded on
first use and cached afterwards.
"""
from __future__ import annotations

import json
from pathlib import Path


def rip(
    audio: str | Path,
    output_dir: str | Path,
    *,
    model: str = "htdemucs",
    auto_tempo: bool = True,
    quantize_beats: int = 0,
    chunk_seconds: float = 0.0,
    make_score: bool = True,
    score_format: str = "pdf",
) -> dict:
    """Run the full separation/transcription/DAW/score workflow."""
    from .daw import build_bundle
    from .separate import separate

    src = Path(audio)
    if not src.exists():
        raise FileNotFoundError(src)
    out = Path(output_dir)
    stems_dir = out / "stems"
    out.mkdir(parents=True, exist_ok=True)

    separation = separate(
        src,
        model=model,
        output_dir=stems_dir,
        transcribe_stems=True,
        auto_tempo=auto_tempo,
        quantize_beats=int(quantize_beats) if quantize_beats else 0,
        chunk_seconds=chunk_seconds,
    )

    bundle = build_bundle(stems_dir, output_dir=out / "daw", name=src.stem or out.name)

    result: dict = {
        "format": "musicfab-rip",
        "version": 1,
        "input": str(src),
        "output": str(out),
        "stems": separation["stems"],
        "transcriptions": separation.get("transcriptions", {}),
        "daw": str(out / "daw"),
        "daw_manifest": bundle,
        "score": None,
    }

    if make_score:
        from .score import build_score

        fmt = (score_format or "pdf").lower()
        suffix = ".musicxml" if fmt in {"musicxml", "xml"} else f".{fmt}"
        score_path = out / f"{src.stem or 'full'}{suffix}"
        try:
            result["score"] = str(
                build_score(stems_dir, output=score_path, fmt=fmt, quantize_beats=int(quantize_beats) or None)
            )
        except Exception as exc:  # score rendering is optional (needs resvg/pymupdf)
            result["score_error"] = str(exc)

    (out / "rip.json").write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    return result
