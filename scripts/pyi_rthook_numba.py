"""PyInstaller runtime hook: make numba work inside a frozen one-file bundle.

Numba cannot create its on-disk JIT-cache locator for modules that live inside
the PYZ archive ("no locator available for file 'librosa\\core\\audio.py'"),
which breaks librosa's ``@jit(cache=True)`` decorators.  We neutralise JIT (and
caching) before librosa/resampy import numba, which keeps pure-Python fallbacks
working at a modest speed cost.
"""
import os
import sys

if getattr(sys, "frozen", False):
    os.environ.setdefault("NUMBA_DISABLE_JIT", "1")
    try:
        import numba
        import numba.core.config as _cfg

        _cfg.DISABLE_JIT = True
        _cfg.DISABLE_CACHING = True

        def _no_jit(func=None, *args, **kwargs):
            if func is None:
                return lambda f: f
            return func

        numba.jit = _no_jit
        numba.njit = _no_jit
        for _name in ("vectorize", "guvectorize", "generated_jit", "stencil"):
            if hasattr(numba, _name):
                setattr(numba, _name, _no_jit)
    except Exception:  # pragma: no cover - best effort
        pass
