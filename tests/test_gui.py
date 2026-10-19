from __future__ import annotations

import os
from pathlib import Path

import pytest

FIX = Path(__file__).parent / "fixtures"

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_gui_smoke(tmp_path: Path):
    pytest.importorskip("PySide6")
    audio = FIX / "melody.wav"
    if not audio.exists():
        pytest.skip("fixture melody.wav missing")

    from PySide6 import QtWidgets

    from musicfab.gui import make_window

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    Window = make_window()
    window = Window(str(audio))
    assert window.audio_path == audio
    assert window._duration > 1.0
    assert window.waveform._peaks, "waveform peaks should be populated"

    out = window.render_preview(tmp_path / "preview.wav")
    assert out.exists() and out.stat().st_size > 1000
    window.close()


def test_gui_ab_selection_limits_render(tmp_path: Path):
    pytest.importorskip("PySide6")
    audio = FIX / "melody.wav"
    if not audio.exists():
        pytest.skip("fixture melody.wav missing")
    from PySide6 import QtWidgets
    from musicfab.gui import make_window

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    Window = make_window()
    window = Window(str(audio))
    source_duration = window._duration
    window.waveform.set_selection(0.25, 0.5)
    window.ab_check.setChecked(True)
    out = window.render_preview(tmp_path / "ab.wav")
    import soundfile as sf

    info = sf.info(str(out))
    rendered = info.frames / info.samplerate
    assert rendered == pytest.approx(source_duration * 0.25, rel=0.15)
    window.close()
