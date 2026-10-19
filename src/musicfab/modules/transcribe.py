"""Audio -> notes (AnthemScore alternative).

Backends
--------
``basicpitch`` (default, pure ONNX/CPU)
    Spotify Basic Pitch (Apache-2.0).  Detects onsets/frames/contours and
    converts them to note events.  The ONNX model ships with the ``basic-pitch``
    wheel and runs on onnxruntime, so **no TensorFlow is required** when the
    package is installed with ``--no-deps`` plus its pure dependencies.

``pti`` (optional, piano specialist)
    ByteDance ``piano_transcription_inference`` (MIT, PyTorch).  Higher quality
    for solo piano; install with ``pip install piano_transcription_inference``.
    Weights are downloaded by that package on first use.

Both backends are offline after their model files are present.
"""
from __future__ import annotations

from pathlib import Path

from ..core.export import to_midi, to_musicxml
from ..core.project import Note, Project, Track


def _merge_same_pitch(notes: list[Note], gap: float = 0.03) -> list[Note]:
    """Merge overlapping / nearly-touching notes with the same pitch.

    Backends sometimes emit a note twice (onset + frame detection) or split a
    sustained tone; merging keeps the project tidy without changing pitch.
    """
    if not notes:
        return notes
    notes = sorted(notes, key=lambda n: (n.pitch, n.start, n.end))
    merged: list[Note] = []
    for n in notes:
        if merged and merged[-1].pitch == n.pitch and n.start <= merged[-1].end + gap:
            prev = merged[-1]
            prev.end = max(prev.end, n.end)
            prev.velocity = max(prev.velocity, n.velocity)
        else:
            merged.append(n)
    merged.sort(key=lambda n: (n.start, n.pitch))
    return merged


def _basicpitch_notes(
    audio: Path,
    *,
    onset_threshold: float = 0.5,
    frame_threshold: float = 0.3,
    min_note_ms: float = 50.0,
) -> list[Note]:
    import logging
    import warnings

    warnings.filterwarnings("ignore")
    logging.disable(logging.WARNING)
    from basic_pitch import ICASSP_2022_MODEL_PATH
    from basic_pitch.inference import predict

    _model_output, _midi_data, note_events = predict(
        str(audio),
        ICASSP_2022_MODEL_PATH,
        onset_threshold=onset_threshold,
        frame_threshold=frame_threshold,
        minimum_note_length=min_note_ms,
        minimum_frequency=None,
        maximum_frequency=None,
        multiple_pitch_bends=False,
        melodia_trick=True,
    )
    notes: list[Note] = []
    for ev in note_events:
        start, end, pitch = float(ev[0]), float(ev[1]), int(round(float(ev[2])))
        amplitude = float(ev[3]) if len(ev) > 3 else 0.8
        velocity = max(1, min(127, int(round(amplitude * 127))))
        notes.append(Note(start=round(start, 4), end=round(end, 4), pitch=pitch, velocity=velocity))
    notes.sort(key=lambda n: (n.start, n.pitch))
    return notes


def _pti_notes(audio: Path) -> list[Note]:
    import logging
    import warnings

    warnings.filterwarnings("ignore")
    logging.disable(logging.WARNING)
    import librosa
    from piano_transcription_inference import PianoTranscription, sample_rate

    data, _ = librosa.load(str(audio), sr=sample_rate, mono=True)
    transcriptor = PianoTranscription(device="cpu")
    transcribed = transcriptor.transcribe(data)
    notes: list[Note] = []
    for onset, offset, midi, velocity in transcribed.get("est_note", []):
        notes.append(
            Note(
                start=round(float(onset), 4),
                end=round(float(offset), 4),
                pitch=int(round(float(midi))),
                velocity=int(round(127 * float(velocity))) if float(velocity) <= 1.0 else int(velocity),
            )
        )
    notes.sort(key=lambda n: (n.start, n.pitch))
    return notes


def _pick_backend(model: str) -> str:
    model = (model or "auto").lower()
    if model in {"auto", "basicpitch", "basic-pitch", "basic_pitch"}:
        if model != "auto":
            return "basicpitch"
        try:  # prefer the piano specialist when available
            import piano_transcription_inference  # noqa: F401

            return "pti"
        except Exception:
            return "basicpitch"
    if model in {"pti", "piano_transcription_inference", "piano"}:
        return "pti"
    raise ValueError(f"unknown transcription backend: {model!r} (auto|basicpitch|pti)")


def transcribe(
    audio: str | Path,
    *,
    model: str = "auto",
    output_midi: str | Path | None = None,
    output_musicxml: str | Path | None = None,
    onset_threshold: float = 0.5,
    frame_threshold: float = 0.3,
    min_note_ms: float = 50.0,
    quantize: float | None = None,
) -> Project:
    """Transcribe an audio file into a :class:`Project`.

    Parameters
    ----------
    model:
        ``auto`` (best available), ``basicpitch`` or ``pti``.
    quantize:
        If given, snap note starts/ends to the nearest multiple of this many
        seconds (e.g. ``0.125`` for a 32nd-note grid at 120 BPM).
    """
    src = Path(audio)
    if not src.exists():
        raise FileNotFoundError(src)
    backend = _pick_backend(model)
    if backend == "pti":
        notes = _pti_notes(src)
    else:
        notes = _basicpitch_notes(
            src, onset_threshold=onset_threshold, frame_threshold=frame_threshold, min_note_ms=min_note_ms
        )

    if quantize and quantize > 0:
        q = float(quantize)
        for n in notes:
            n.start = round(round(n.start / q) * q, 4)
            n.end = round(round(n.end / q) * q, 4)
            if n.end <= n.start:
                n.end = round(n.start + q, 4)

    notes = _merge_same_pitch(notes)
    proj = Project.from_notes(notes, name=src.stem, audio={"path": str(src)}, backend=backend)
    proj.tracks = [Track(name=src.stem, notes=notes)]

    if output_midi:
        to_midi(proj, output_midi)
    if output_musicxml:
        to_musicxml(proj, output_musicxml)
    return proj
