"""Entry point for ``python -m musicfab`` and PyInstaller."""
from __future__ import annotations

from musicfab.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
