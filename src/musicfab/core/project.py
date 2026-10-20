"""Unified musicfab project format (.mfproj.json)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

FORMAT = "musicfab-project"
VERSION = 1


@dataclass
class Note:
    start: float
    end: float
    pitch: int
    velocity: int = 80
    instrument: int = 0

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass
class Track:
    name: str = "main"
    instrument: int = 0
    notes: list[Note] = field(default_factory=list)


@dataclass
class Project:
    name: str = "untitled"
    audio: dict = field(default_factory=dict)
    tempo: float = 120.0
    time_signature: str = "4/4"
    beats: list[float] = field(default_factory=list)
    tracks: list[Track] = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    # -- constructors -------------------------------------------------
    @classmethod
    def from_notes(
        cls,
        notes: list[Note],
        name: str = "untitled",
        tempo: float = 120.0,
        time_signature: str = "4/4",
        audio: dict | None = None,
        beats: list[float] | None = None,
        **meta,
    ) -> "Project":
        return cls(
            name=name,
            tempo=float(tempo),
            time_signature=time_signature,
            audio=dict(audio or {}),
            beats=[float(b) for b in (beats or [])],
            tracks=[Track(notes=list(notes))],
            meta=meta,
        )

    @property
    def notes(self) -> list[Note]:
        out: list[Note] = []
        for t in self.tracks:
            out.extend(t.notes)
        return out

    # -- persistence --------------------------------------------------
    def to_dict(self) -> dict:
        d = asdict(self)
        d["format"] = FORMAT
        d["version"] = VERSION
        return d

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=1, ensure_ascii=False), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: str | Path) -> "Project":
        path = Path(path)
        raw = json.loads(path.read_text(encoding="utf-8"))
        if raw.get("format") != FORMAT:
            raise ValueError(f"not a musicfab project: {raw.get('format')!r}")
        if int(raw.get("version", 0)) > VERSION:
            raise ValueError("project comes from a newer musicfab version")
        tracks = []
        for i, t in enumerate(raw.get("tracks", [])):
            notes = []
            for j, n in enumerate(t.get("notes", [])):
                try:
                    notes.append(Note(**n))
                except (TypeError, KeyError, ValueError) as exc:
                    raise ValueError(f"{path}: track {i} note {j} invalid: {exc}") from exc
            try:
                tracks.append(
                    Track(
                        name=t.get("name", "main"),
                        instrument=int(t.get("instrument", 0)),
                        notes=notes,
                    )
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{path}: track {i} invalid: {exc}") from exc
        try:
            tempo = float(raw.get("tempo", 120.0))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{path}: invalid tempo: {exc}") from exc
        if not tempo > 0:
            raise ValueError(f"{path}: tempo must be positive, got {tempo}")
        try:
            beats = [float(b) for b in raw.get("beats", [])]
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{path}: invalid beats: {exc}") from exc
        for a, b in zip(beats, beats[1:]):
            if b <= a:
                raise ValueError(f"{path}: beats must be strictly increasing (got {a} then {b})")
        return cls(
            name=raw.get("name", "untitled"),
            audio=raw.get("audio", {}),
            tempo=tempo,
            time_signature=raw.get("time_signature", "4/4"),
            beats=beats,
            tracks=tracks,
            meta=raw.get("meta", {}),
        )

    # -- stats --------------------------------------------------------
    def summary(self) -> dict:
        notes = self.notes
        pitches = [n.pitch for n in notes]
        return {
            "name": self.name,
            "notes": len(notes),
            "tracks": len(self.tracks),
            "duration": round(max((n.end for n in notes), default=0.0), 3),
            "pitch_range": [min(pitches), max(pitches)] if pitches else [],
            "tempo": self.tempo,
        }
