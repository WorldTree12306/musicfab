"""End-to-end demo: transcribe -> practice -> shift -> separate -> notation.

Writes all artefacts under ``build/demo/`` and a short Markdown report.
Run with:  python examples/demo.py
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "demo"


def make_demo_audio(path: Path, sr: int = 44100) -> float:
    """A short C-major melody used as demo input."""
    notes = [60, 62, 64, 65, 67, 69, 71, 72]
    dur = 0.45
    chunks = []
    for p in notes:
        f = 440.0 * 2 ** ((p - 69) / 12)
        t = np.arange(int(sr * dur)) / sr
        env = np.minimum(1.0, t / 0.01) * np.minimum(1.0, (dur - t) / 0.03)
        sig = (np.sin(2 * np.pi * f * t) + 0.12 * np.sin(4 * np.pi * f * t)) * env * 0.3
        chunks.append(sig.astype(np.float32))
        chunks.append(np.zeros(int(sr * 0.05), dtype=np.float32))
    y = np.concatenate(chunks)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, y, sr)
    return len(y) / sr


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    src = OUT / "demo_input.wav"
    duration = make_demo_audio(src)
    report = [f"# musicfab demo\n", f"- input: `{src.name}` ({duration:.2f}s)\n"]
    timings = {}

    # 1) transcription (AnthemScore alternative)
    t0 = time.time()
    from musicfab.modules.transcribe import transcribe

    proj = transcribe(src, model="basicpitch", output_midi=OUT / "demo.mid",
                      output_musicxml=OUT / "demo.musicxml")
    timings["transcribe"] = time.time() - t0
    report.append(f"- transcribe: {len(proj.notes)} notes, pitches={[n.pitch for n in proj.notes]}\n")
    proj.save(OUT / "demo.mfproj.json")

    # 2) practice (Transcribe! alternative)
    t0 = time.time()
    from musicfab.modules.practice import practice

    practice(src, tempo=0.5, semitones=-2, output=OUT / "demo_practice.wav")
    timings["practice"] = time.time() - t0

    # 3) pitch shift (Melodyne alternative)
    t0 = time.time()
    from musicfab.modules.pitch import shift_audio

    shift_audio(src, semitones=3, output=OUT / "demo_shift_up.wav")
    timings["shift"] = time.time() - t0

    # 4) stem separation (RipX alternative)
    t0 = time.time()
    from musicfab.modules.separate import separate

    manifest = separate(src, output_dir=OUT / "stems")
    timings["separate"] = time.time() - t0
    report.append(f"- separate: stems={list(manifest['stems'])}\n")

    # 5) per-note edit (Melodyne alternative)
    t0 = time.time()
    from musicfab.modules.notes import apply_edits, write_template

    edits = write_template(src, OUT / "demo_edits.json")
    import json as _json

    table = _json.loads(edits.read_text(encoding="utf-8"))
    table["edits"][0]["semitones"] = 12
    edits.write_text(_json.dumps(table, indent=1), encoding="utf-8")
    stats = apply_edits(src, edits, output=OUT / "demo_note_edit.wav")
    report.append(f"- notes: {stats['edits_applied']} edit(s), {stats['notes_detected']} notes detected")
    report.append(chr(10))
    timings["notes"] = time.time() - t0


    # 6) notation render (Capella alternative)
    t0 = time.time()
    from musicfab.modules.notation import convert

    try:
        svg = convert(OUT / "demo.musicxml", output=OUT / "demo.svg", fmt="svg")
        pdf = convert(OUT / "demo.musicxml", output=OUT / "demo.pdf", fmt="pdf")
        report.append(f"- notation: {svg.name} + {pdf.name} rendered\n")
    except Exception as exc:  # rendering is optional
        report.append(f"- notation: skipped ({exc})\n")
    timings["notation"] = time.time() - t0

    report.append("\n## timings (s)\n\n")
    for k, v in timings.items():
        report.append(f"- {k}: {v:.2f}\n")
    (OUT / "demo_report.md").write_text("".join(report), encoding="utf-8")
    print("".join(report))
    print(f"\nartefacts: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
