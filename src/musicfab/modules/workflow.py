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

With ``separate_stems=False`` only transcription + single score are produced
(no Demucs, much faster when stems are not needed).

Everything is local; only Demucs/Basic Pitch model weights are downloaded on
first use and cached afterwards.
"""
from __future__ import annotations

import json
from pathlib import Path


def _auto_tempo_info(src: Path) -> tuple[float, str, list[float] | None]:
    from .separate import shared_tempo_info

    info = shared_tempo_info(src)
    return info["tempo"], info["time_signature"], info["beats"]


def _render_score(project_path: Path, out: Path, stem: str, fmt: str) -> str:
    from .notation import convert

    fmt = (fmt or "pdf").lower()
    suffix = ".musicxml" if fmt in {"musicxml", "xml"} else f".{fmt}"
    return str(convert(project_path, output=out / f"{stem}{suffix}", fmt=fmt))


def _rip_transcribe_only(
    src: Path,
    out: Path,
    *,
    auto_tempo: bool,
    quantize_beats: int,
    make_score: bool,
    score_format: str,
) -> dict:
    from ..core.export import to_midi, to_musicxml
    from .transcribe import transcribe

    solo = out / "single"
    solo.mkdir(parents=True, exist_ok=True)
    stem = src.stem or "single"
    tempo, signature, beats = (120.0, "4/4", None)
    if auto_tempo:
        tempo, signature, beats = _auto_tempo_info(src)
    proj = transcribe(
        src,
        model="basicpitch",
        tempo=tempo,
        time_signature=signature,
        beats=beats,
        quantize_beats=int(quantize_beats) or None,
    )
    project_path = proj.save(solo / f"{stem}.mfproj.json")
    midi_path = to_midi(proj, solo / f"{stem}.mid")
    xml_path = to_musicxml(proj, solo / f"{stem}.musicxml", quantize_beats=int(quantize_beats) or None)

    result: dict = {
        "format": "musicfab-rip",
        "mode": "transcribe",
        "version": 1,
        "input": str(src),
        "output": str(out),
        "project": str(project_path),
        "midi": str(midi_path),
        "musicxml": str(xml_path),
        "notes": len(proj.notes),
        "tempo": proj.tempo,
        "score": None,
    }
    if make_score:
        try:
            result["score"] = _render_score(project_path, solo, stem, score_format)
        except Exception as exc:  # rendering optional (needs resvg/pymupdf)
            result["score_error"] = str(exc)
    (out / "rip.json").write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    return result


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
    separate_stems: bool = True,
) -> dict:
    """Run the full separation/transcription/DAW/score workflow."""
    from .daw import build_bundle
    from .separate import separate

    src = Path(audio)
    if not src.exists():
        raise FileNotFoundError(src)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    if not separate_stems:
        return _rip_transcribe_only(
            src, out, auto_tempo=auto_tempo, quantize_beats=int(quantize_beats),
            make_score=make_score, score_format=score_format,
        )

    stems_dir = out / "stems"
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
        "mode": "separate",
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
