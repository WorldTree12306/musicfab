"""Environment diagnostics (``musicfab doctor``).

Checks required and optional dependencies, model caches and external tools so
users can see what each feature needs before running a long job.
"""
from __future__ import annotations

import importlib
import json
import shutil
import sys
from pathlib import Path

REQUIRED = ["numpy", "scipy", "soundfile"]
OPTIONAL = {
    "mido": "MIDI export",
    "music21": "MusicXML export/engraving",
    "librosa": "practice/shift/beats/notes",
    "pretty_midi": "MIDI helpers",
    "basic_pitch": "transcription backend (ONNX)",
    "torch": "demucs separation / optional PTI",
    "demucs": "stem separation",
    "verovio": "score SVG rendering",
    "pymupdf": "PDF/PNG export",
    "resvg_py": "Verovio SVG rasterisation",
    "guitarpro": "Guitar Pro import",
    "PySide6": "GUI (musicfab gui)",
    "resampy": "basic-pitch dependency",
}


def _version(mod) -> str | None:
    for attr in ("__version__", "version"):
        value = getattr(mod, attr, None)
        if isinstance(value, str):
            return value
    try:
        import importlib.metadata as md

        return md.version(mod.__name__)
    except Exception:
        return None


def _check(name: str) -> dict:
    try:
        mod = importlib.import_module(name)
        return {"available": True, "version": _version(mod)}
    except Exception as exc:  # noqa: BLE001 - report, never raise
        return {"available": False, "error": f"{type(exc).__name__}: {exc}"}


def _model_cache() -> dict:
    cache = Path.home() / ".cache" / "torch" / "hub" / "checkpoints"
    files = []
    if cache.exists():
        files = sorted(p.name for p in cache.glob("*") if p.is_file())
    return {"dir": str(cache), "files": files[:10], "count": len(files)}


def _ffmpeg() -> str | None:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _collect_impl() -> dict:
    required = {name: _check(name) for name in REQUIRED}
    optional = {name: {**_check(name), "purpose": purpose} for name, purpose in OPTIONAL.items()}
    report = {
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "platform": sys.platform,
        "required": required,
        "required_ok": all(item["available"] for item in required.values()),
        "optional": optional,
        "ffmpeg": _ffmpeg(),
        "model_cache": _model_cache(),
    }
    features = {
        "probe": required["soundfile"]["available"],
        "transcribe": optional["basic_pitch"]["available"] or optional["torch"]["available"],
        "practice": optional["librosa"]["available"],
        "shift": optional["librosa"]["available"],
        "notes": optional["basic_pitch"]["available"] and optional["librosa"]["available"],
        "beats": optional["librosa"]["available"],
        "separate": optional["torch"]["available"] and optional["demucs"]["available"],
        "notation": optional["music21"]["available"],
        "pdf": optional["verovio"]["available"] and optional["resvg_py"]["available"] and optional["pymupdf"]["available"],
        "tab": optional["guitarpro"]["available"],
        "gui": optional["PySide6"]["available"],
    }
    report["features"] = features
    report["ready"] = [k for k, v in features.items() if v]
    report["missing"] = [k for k, v in features.items() if not v]
    return report


def collect() -> dict:
    """Return a machine-readable environment report (imports are quieted)."""
    import logging
    import warnings

    previous = logging.root.manager.disable
    logging.disable(logging.WARNING)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return _collect_impl()
    finally:
        logging.disable(previous)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    strict = "--strict" in args
    report = collect()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if strict and not report["required_ok"]:
        print("required dependencies are missing", file=sys.stderr)
        return 2
    return 0
