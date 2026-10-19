"""musicfab command line interface."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _lazy():
    """Import heavy modules only when a subcommand needs them."""
    from . import __version__
    return __version__


def cmd_version(_: argparse.Namespace) -> int:
    print(f"musicfab { _lazy() }")
    return 0


def cmd_probe(args: argparse.Namespace) -> int:
    from .core.audio import probe

    info = probe(args.audio)
    print(json.dumps(info, indent=2, ensure_ascii=False))
    return 0


def cmd_transcribe(args: argparse.Namespace) -> int:
    from .modules.transcribe import transcribe

    tempo, time_signature, beats = args.tempo, args.time_signature, None
    if args.auto_tempo:
        from .modules.beats import detect_beats

        info = detect_beats(args.audio)
        tempo = info["tempo"]
        time_signature = info["time_signature"]
        beats = info["beats"]
        print(f"auto tempo: {tempo:.2f} BPM, {len(beats)} beats")

    proj = transcribe(
        args.audio,
        model=args.model,
        output_midi=args.output,
        output_musicxml=args.musicxml,
        tempo=tempo,
        time_signature=time_signature,
        beats=beats,
        quantize_beats=args.quantize_beats,
    )
    out = Path(args.save) if args.save else Path(args.audio).with_suffix(".mfproj.json")
    proj.save(out)
    print(f"saved project: {out}")
    return 0


def cmd_beats(args: argparse.Namespace) -> int:
    from .modules.beats import detect_beats

    info = detect_beats(args.audio, beats_per_bar=args.beats_per_bar)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(info, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"saved beats: {out} (tempo {info['tempo']} BPM, {len(info['beats'])} beats)")
    else:
        print(json.dumps(info, indent=1, ensure_ascii=False))
    return 0


def cmd_daw(args: argparse.Namespace) -> int:
    from .modules.daw import build_bundle

    manifest = build_bundle(
        args.input_dir,
        output_dir=args.output,
        name=args.name,
        tempo=args.tempo if args.tempo else None,
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


def cmd_practice(args: argparse.Namespace) -> int:
    from .modules.practice import practice

    practice(args.audio, tempo=args.tempo, semitones=args.semitones,
             loop=tuple(args.loop) if args.loop else None,
             beat_loop=args.loop_beats, beat_start=args.beat_start,
             bar_loop=args.loop_bars, bar_start=args.bar_start, output=args.output)
    return 0


def cmd_shift(args: argparse.Namespace) -> int:
    from .modules.pitch import shift_audio

    shift_audio(args.audio, semitones=args.semitones, output=args.output)
    return 0


def cmd_notes(args: argparse.Namespace) -> int:
    from .modules.notes import apply_edits, detect_notes, write_template

    if args.edits:
        stats = apply_edits(args.audio, args.edits, output=args.output, model=args.model)
        print(json.dumps(stats, indent=2, ensure_ascii=False))
        return 0

    edits_path = args.output if args.output and args.output.endswith(".json") else Path(args.audio).with_suffix(".edits.json")
    tpl = write_template(args.audio, edits_path, model=args.model)
    notes = detect_notes(args.audio, model=args.model)
    print(f"detected {len(notes)} notes; editable table: {tpl}")
    print("edit the JSON, then run: musicfab notes <audio> --edits <table> -o out.wav")
    return 0


def cmd_separate(args: argparse.Namespace) -> int:
    from .modules.separate import separate

    manifest = separate(
        args.audio,
        model=args.model,
        output_dir=args.output_dir,
        transcribe_stems=args.transcribe,
        auto_tempo=args.auto_tempo,
        tempo=args.tempo,
        shifts=args.shifts,
        chunk_seconds=args.chunk_seconds,
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


def cmd_notation(args: argparse.Namespace) -> int:
    from .modules.notation import convert

    convert(args.input, output=args.output, fmt=args.format)
    return 0


def cmd_tab(args: argparse.Namespace) -> int:
    from .modules.tab import import_tab

    import_tab(args.input, output=args.output, fmt=args.format)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="musicfab", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("version", help="print version").set_defaults(func=cmd_version)

    pp = sub.add_parser("probe", help="show audio file information")
    pp.add_argument("audio")
    pp.set_defaults(func=cmd_probe)

    pt = sub.add_parser("transcribe", help="audio -> MIDI/MusicXML (AnthemScore alternative)")
    pt.add_argument("audio")
    pt.add_argument("-o", "--output", help="output MIDI path")
    pt.add_argument("--musicxml", help="output MusicXML path")
    pt.add_argument("--model", default="auto", help="model backend: auto|pti|basicpitch")
    pt.add_argument("--tempo", type=float, default=120.0, help="tempo for MIDI/MusicXML export")
    pt.add_argument("--time-signature", default="4/4", help="time signature for export, e.g. 3/4")
    pt.add_argument("--auto-tempo", action="store_true", help="detect tempo/beats automatically")
    pt.add_argument("--quantize-beats", type=int, default=0, metavar="SUBDIV",
                    help="snap notes to the beat grid (subdivisions per beat; 0 = off)")
    pt.add_argument("--save", help="project JSON path")
    pt.set_defaults(func=cmd_transcribe)

    pr = sub.add_parser("practice", help="slow down / transpose / loop for practice (Transcribe! alternative)")
    pr.add_argument("audio")
    pr.add_argument("--tempo", type=float, default=1.0, help="playback speed, 1.0 = original")
    pr.add_argument("--semitones", type=float, default=0.0)
    pr.add_argument("--loop", nargs=2, type=float, metavar=("START", "END"))
    pr.add_argument("--loop-beats", type=int, help="loop N detected beats")
    pr.add_argument("--beat-start", type=int, default=0, help="index of the first beat for --loop-beats")
    pr.add_argument("--loop-bars", type=int, help="loop N detected bars (uses detected time signature)")
    pr.add_argument("--bar-start", type=int, default=0, help="index of the first bar for --loop-bars")
    pr.add_argument("-o", "--output", required=True)
    pr.set_defaults(func=cmd_practice)

    ps = sub.add_parser("shift", help="note-level pitch shift (Melodyne alternative)")
    ps.add_argument("audio")
    ps.add_argument("--semitones", type=float, required=True)
    ps.add_argument("-o", "--output", required=True)
    ps.set_defaults(func=cmd_shift)

    pb = sub.add_parser("beats", help="tempo / beat / downbeat estimation")
    pb.add_argument("audio")
    pb.add_argument("-o", "--output", help="write beats JSON (default: print)")
    pb.add_argument("--beats-per-bar", type=int, default=4)
    pb.set_defaults(func=cmd_beats)

    pd = sub.add_parser("daw", help="assemble a DAW import bundle from stem projects (RipX alternative)")
    pd.add_argument("input_dir", help="directory produced by 'separate --transcribe'")
    pd.add_argument("-o", "--output", help="bundle directory (default: <input>/daw)")
    pd.add_argument("--name", help="bundle name (default: input directory name)")
    pd.add_argument("--tempo", type=float, default=0.0, help="override tempo")
    pd.set_defaults(func=cmd_daw)

    pnotes = sub.add_parser("notes", help="detect/edit individual notes and resynthesise (Melodyne alternative)")
    pnotes.add_argument("audio")
    pnotes.add_argument("--edits", help="edit table JSON produced by this command without --edits")
    pnotes.add_argument("-o", "--output", help="output WAV (with --edits) or edit table JSON (without)")
    pnotes.add_argument("--model", default="basicpitch")
    pnotes.set_defaults(func=cmd_notes)

    psep = sub.add_parser("separate", help="stem separation (RipX alternative)")
    psep.add_argument("audio")
    psep.add_argument("--model", default="htdemucs")
    psep.add_argument("-o", "--output-dir", required=True)
    psep.add_argument("--transcribe", action="store_true", help="also transcribe every stem to a project/MIDI")
    psep.add_argument("--auto-tempo", action="store_true", help="detect tempo per stem during --transcribe")
    psep.add_argument("--tempo", type=float, default=120.0, help="tempo used when --transcribe without --auto-tempo")
    psep.add_argument("--shifts", type=int, default=0, help="demucs shift averaging (higher = slower/better)")
    psep.add_argument("--chunk-seconds", type=float, default=0.0,
                      help="chunked overlap-add size (0 = auto above 4 minutes)")
    psep.set_defaults(func=cmd_separate)

    pn = sub.add_parser("notation", help="score engraving/export (Capella alternative)")
    pn.add_argument("input")
    pn.add_argument("-o", "--output", required=True)
    pn.add_argument("-f", "--format", default="musicxml", choices=["musicxml", "pdf", "png", "svg", "midi"])
    pn.set_defaults(func=cmd_notation)

    ptab = sub.add_parser("tab", help="guitar tab import/convert (Guitar Pro alternative)")
    ptab.add_argument("input")
    ptab.add_argument("-o", "--output", required=True)
    ptab.add_argument("-f", "--format", default="json", choices=["json", "musicxml", "midi", "svg", "html", "pdf", "png"])
    ptab.set_defaults(func=cmd_tab)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except NotImplementedError as exc:
        print(f"[not implemented] {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
