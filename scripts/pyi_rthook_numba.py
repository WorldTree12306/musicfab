"""PyInstaller runtime hook: make numba work inside a frozen bundle.

Numba's disk cache locator cannot resolve modules stored in the PYZ archive
("cannot cache function ... no locator available for file
'librosa\\core\\audio.py'"), which breaks librosa's ``@jit(cache=True)``,
``@vectorize(..., cache=True)`` and ``@guvectorize(..., cache=True)``
decorators.

Fix: keep real JIT compilation but force ``cache=False`` on those decorators
before librosa/resampy import numba.  ``stencil`` has no cache option and is
left untouched.  The wrapper preserves each decorator's calling convention
(bare decorator vs. parameterised usage).

Status in the lite portable build: ``transcribe``/``notation``/``tab`` work;
``practice``/``shift`` still hit numba's frozen-call-template issue, so those
features require a source install (documented in docs/INSTALL.md).
"""
import os
import sys

if getattr(sys, "frozen", False):
    os.environ.setdefault("NUMBA_CACHE_DIR", os.path.join(os.environ.get("TEMP", "."), "musicfab-numba"))
    try:
        import numba

        def _make_no_cache(orig):
            def wrapper(*args, **kwargs):
                kwargs = dict(kwargs)
                kwargs["cache"] = False
                try:
                    return orig(*args, **kwargs)
                except TypeError:
                    kwargs.pop("cache", None)
                    return orig(*args, **kwargs)

            return wrapper

        for _name in ("jit", "njit", "vectorize", "guvectorize"):
            _orig = getattr(numba, _name, None)
            if _orig is not None:
                setattr(numba, _name, _make_no_cache(_orig))
    except Exception:  # pragma: no cover - best effort
        pass
