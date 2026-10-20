"""musicfab — open-source alternatives to six commercial music tools."""

import os
import sys
import tempfile

__version__ = "0.2.0"

# Frozen (PyInstaller) builds: numba cannot create a cache locator inside the
# one-file bundle, which breaks librosa's JIT-decorated functions.  Disabling
# JIT keeps librosa fully functional (just a bit slower) in portable builds.
if getattr(sys, "frozen", False) and not os.environ.get("NUMBA_DISABLE_JIT"):
    os.environ["NUMBA_DISABLE_JIT"] = "1"
    try:
        os.environ.setdefault("NUMBA_CACHE_DIR", os.path.join(tempfile.gettempdir(), "musicfab-numba"))
    except Exception:  # pragma: no cover
        pass
