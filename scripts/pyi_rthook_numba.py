"""PyInstaller runtime hook: fix numba JIT caching inside a frozen bundle.

Numba's disk cache locator cannot resolve modules stored in the PYZ archive
("cannot cache function ... no locator available for file
'librosa\\core\\audio.py'"), which breaks librosa's ``@jit(cache=True)`` and
``@guvectorize(..., cache=True)`` decorators.

Fix: keep real JIT compilation (fast) but force ``cache=False`` on ``jit``,
``njit`` and ``guvectorize`` before librosa/resampy import numba.  Decorators
that do not support caching (``vectorize``, ``stencil``) are left untouched.

Note: because numba's ``vectorize`` cache cannot be stripped safely, ``practice``
and ``shift`` still require a source install; the portable build targets
``transcribe``/``notation``/``tab``.
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
                if "cache" in kwargs or args:
                    kwargs["cache"] = False
                try:
                    return orig(*args, **kwargs)
                except TypeError:
                    kwargs.pop("cache", None)
                    return orig(*args, **kwargs)

            return wrapper

        for _name in ("jit", "njit", "guvectorize"):
            _orig = getattr(numba, _name, None)
            if _orig is not None:
                setattr(numba, _name, _make_no_cache(_orig))
    except Exception:  # pragma: no cover - best effort
        pass
