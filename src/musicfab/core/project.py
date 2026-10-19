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
    beats: list[float] = field(default_factory=list)
    tracks: list[Track] = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    # -- constructors -------------------------------------------------
    @classmethod
    def from_notes(cls, notes: list[Note], name: str = "untitled", **meta) -> "Project":
        return cls(name=name, tracks=[Track(notes=list(notes))], meta=meta)

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
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if raw.get("format") != FORMAT:
            raise ValueError(f"not a musicfab project: {raw.get('format')!r}")
        if int(raw.get("version", 0)) > VERSION:
            raise ValueError("project comes from a newer musicfab version")
        tracks = []
        for t in raw.get("tracks", []):
            tracks.append(
                Track(
                    name=t.get("name", "main"),
                    instrument=int(t.get("instrument", 0)),
                    notes=[Note(**n) for n in t.get("notes", [])],
                )
            )
        return cls(
            name=raw.get("name", "untitled"),
            audio=raw.get("audio", {}),
            tempo=float(raw.get("tempo", 120.0)),
            beats=[float(b) for b in raw.get("beats", [])],
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
