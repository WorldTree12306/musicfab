"""Fetch local test fixtures that are too large / licensed to commit.

* Generates synthetic WAV files via :mod:`scripts.gen_test_audio`.
* Downloads a couple of small Guitar Pro samples from the PyGuitarPro test
  suite (used only locally for development; not redistributed by musicfab).

Usage:
    python scripts/fetch_fixtures.py
"""
from __future__ import annotations

import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"
SAMPLES = ["Chords.gp5", "001_Funky_Guy.gp5"]
BASE = "https://api.github.com/repos/Perlence/PyGuitarPro/contents/tests/{name}"


def fetch_gp(name: str) -> None:
    dst = FIX / name
    if dst.exists() and dst.stat().st_size > 0:
        print(f"skip existing {name}")
        return
    url = BASE.format(name=urllib.parse.quote(name))
    req = urllib.request.Request(
        url, headers={"User-Agent": "musicfab-fixtures", "Accept": "application/vnd.github.raw"}
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    dst.write_bytes(data)
    print(f"downloaded {name} ({len(data)} bytes)")


def main() -> int:
    FIX.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import gen_test_audio

        sys.argv = ["gen_test_audio", "-o", str(FIX)]
        gen_test_audio.main()
    except Exception as exc:  # pragma: no cover - optional
        print(f"audio fixture generation failed: {exc}")
    for name in SAMPLES:
        try:
            fetch_gp(name)
        except Exception as exc:  # pragma: no cover - network optional
            print(f"could not download {name}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
