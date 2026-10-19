"""Minimal offline practice player (Transcribe! alternative).

Features
--------
* open any audio file supported by :mod:`musicfab.core.audio`;
* waveform overview;
* playback speed 0.5x-1.5x and pitch shift -12..+12 semitones (rendered
  offline with the same phase vocoder used by ``musicfab practice``);
* loop a whole file or a range of detected bars (uses :func:`detect_beats`);
* everything runs locally — no network, no telemetry.

Run with ``musicfab gui [file]`` or ``python -m musicfab.gui [file]``.
PySide6 is an optional dependency: ``pip install musicfab[gui]``.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")


def _qt():
    from PySide6 import QtCore, QtGui, QtMultimedia, QtWidgets

    return QtCore, QtGui, QtMultimedia, QtWidgets


class WaveformWidget:
    """Factory returning a QWidget subclass (Qt import is deferred)."""


def _make_waveform_class():
    QtCore, QtGui, _QtMultimedia, QtWidgets = _qt()

    class Waveform(QtWidgets.QWidget):
        positionChanged = QtCore.Signal(float)

        def __init__(self) -> None:
            super().__init__()
            self._peaks = []  # list of (min, max) per column
            self._progress = 0.0
            self.setMinimumHeight(120)
            self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

        def set_peaks(self, peaks) -> None:
            self._peaks = list(peaks)
            self.update()

        def set_progress(self, value: float) -> None:
            self._progress = max(0.0, min(1.0, float(value)))
            self.update()

        def paintEvent(self, event) -> None:  # noqa: N802 - Qt naming
            painter = QtGui.QPainter(self)
            painter.fillRect(self.rect(), QtGui.QColor("#15181c"))
            if not self._peaks:
                painter.setPen(QtGui.QColor("#7d8590"))
                painter.drawText(self.rect(), QtCore.Qt.AlignCenter, "no audio loaded")
                return
            width = max(1, self.width())
            height = self.height()
            mid = height / 2
            painter.setPen(QtGui.QPen(QtGui.QColor("#3fb950"), 1))
            step = len(self._peaks) / width
            for x in range(width):
                lo, hi = self._peaks[min(len(self._peaks) - 1, int(x * step))]
                painter.drawLine(x, int(mid - hi * mid), x, int(mid - lo * mid))
            px = int(self._progress * width)
            painter.setPen(QtGui.QPen(QtGui.QColor("#f0883e"), 2))
            painter.drawLine(px, 0, px, height)
            painter.end()

    return Waveform


class PlayerWindow:
    """Factory for the main window (Qt import is deferred)."""


def make_window():
    QtCore, QtGui, QtMultimedia, QtWidgets = _qt()
    Waveform = _make_waveform_class()

    class MainWindow(QtWidgets.QMainWindow):
        def __init__(self, audio: str | None = None) -> None:
            super().__init__()
            self.setWindowTitle("musicfab practice")
            self.resize(980, 560)
            self.audio_path: Path | None = None
            self._duration = 0.0
            self._tmpdir = tempfile.TemporaryDirectory(prefix="musicfab-gui-")
            self._player = QtMultimedia.QMediaPlayer(self)
            self._audio_out = QtMultimedia.QAudioOutput(self)
            self._player.setAudioOutput(self._audio_out)

            self.waveform = Waveform()
            self.waveform.positionChanged.connect(self._seek)

            self.open_btn = QtWidgets.QPushButton("Open audio…")
            self.play_btn = QtWidgets.QPushButton("Play")
            self.play_btn.setEnabled(False)
            self.render_btn = QtWidgets.QPushButton("Render && play")
            self.render_btn.setEnabled(False)
            self.loop_check = QtWidgets.QCheckBox("Loop")
            self.loop_check.setChecked(True)

            self.speed = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            self.speed.setRange(50, 150)
            self.speed.setValue(100)
            self.speed_label = QtWidgets.QLabel("1.00x")
            self.semi = QtWidgets.QSpinBox()
            self.semi.setRange(-12, 12)
            self.semi.setSuffix(" st")
            self.bar_loop = QtWidgets.QSpinBox()
            self.bar_loop.setRange(0, 64)
            self.bar_loop.setSpecialValueText("off")
            self.bar_loop.setSuffix(" bars")
            self.bar_start = QtWidgets.QSpinBox()
            self.bar_start.setRange(0, 999)

            self.position = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            self.position.setRange(0, 1000)
            self.time_label = QtWidgets.QLabel("0:00 / 0:00")

            self.open_btn.clicked.connect(self._open_dialog)
            self.play_btn.clicked.connect(self._toggle_play)
            self.render_btn.clicked.connect(self._render_and_play)
            self.speed.valueChanged.connect(lambda v: self.speed_label.setText(f"{v / 100:.2f}x"))
            self.waveform.positionChanged.connect(self._seek)
            self.position.sliderMoved.connect(self._seek)
            self._player.positionChanged.connect(self._on_position)
            self._player.durationChanged.connect(self._on_duration)
            self._player.playbackStateChanged.connect(self._on_state)

            controls = QtWidgets.QHBoxLayout()
            controls.addWidget(self.open_btn)
            controls.addWidget(self.play_btn)
            controls.addWidget(self.render_btn)
            controls.addWidget(self.loop_check)
            controls.addSpacing(12)
            controls.addWidget(QtWidgets.QLabel("speed"))
            controls.addWidget(self.speed, 1)
            controls.addWidget(self.speed_label)
            controls.addWidget(QtWidgets.QLabel("pitch"))
            controls.addWidget(self.semi)
            controls.addWidget(QtWidgets.QLabel("loop bars"))
            controls.addWidget(self.bar_loop)
            controls.addWidget(QtWidgets.QLabel("from"))
            controls.addWidget(self.bar_start)

            layout = QtWidgets.QVBoxLayout()
            layout.addWidget(self.waveform, 1)
            layout.addWidget(self.position)
            layout.addWidget(self.time_label)
            layout.addLayout(controls)
            central = QtWidgets.QWidget()
            central.setLayout(layout)
            self.setCentralWidget(central)
            self.statusBar().showMessage("ready")

            if audio:
                self.load(audio)

        # -- loading ---------------------------------------------------
        def _open_dialog(self) -> None:
            path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, "Open audio", "", "Audio (*.wav *.flac *.ogg *.mp3);;All files (*)"
            )
            if path:
                self.load(path)

        def load(self, path: str | Path) -> None:
            from .core.audio import load as load_audio, probe

            self.audio_path = Path(path)
            info = probe(self.audio_path)
            data, sr = load_audio(self.audio_path, mono=True)
            self._duration = len(data) / sr
            peaks = _peaks(data, columns=1200)
            self.waveform.set_peaks(peaks)
            self.play_btn.setEnabled(True)
            self.render_btn.setEnabled(True)
            self.open_btn.setText(self.audio_path.name)
            self.statusBar().showMessage(
                f"{self.audio_path.name} · {info.get('sample_rate', sr)} Hz · {self._duration:.1f}s"
            )
            self._on_duration(int(self._duration * 1000))

        # -- rendering -------------------------------------------------
        def render_preview(self, output: str | Path) -> Path:
            if not self.audio_path:
                raise RuntimeError("no audio loaded")
            from .modules.practice import practice

            tempo = self.speed.value() / 100.0
            semitones = float(self.semi.value())
            loop = None
            bars = int(self.bar_loop.value())
            if bars > 0:
                from .modules.beats import detect_beats

                info = detect_beats(self.audio_path)
                try:
                    per_bar = int(str(info.get("time_signature", "4/4")).split("/")[0])
                except Exception:
                    per_bar = 4
                beats = info["beats"]
                start_idx = int(self.bar_start.value()) * per_bar
                if len(beats) >= start_idx + 2:
                    start = beats[start_idx]
                    end_idx = min(len(beats) - 1, start_idx + bars * per_bar)
                    end = beats[end_idx]
                    if end > start:
                        loop = (start, end)
            out = practice(
                self.audio_path,
                tempo=tempo,
                semitones=semitones,
                loop=loop,
                output=output,
            )
            self.statusBar().showMessage(f"rendered {Path(output).name}")
            return out

        def _render_and_play(self) -> None:
            if not self.audio_path:
                return
            out = Path(self._tmpdir.name) / "preview.wav"
            self.render_preview(out)
            self._player.stop()
            self._player.setSource(QtCore.QUrl.fromLocalFile(str(out)))
            try:
                self._player.setLoops(
                    QtMultimedia.QMediaPlayer.Loops.Infinite if self.loop_check.isChecked()
                    else QtMultimedia.QMediaPlayer.Loops.Once
                )
            except Exception:
                pass
            self._player.play()

        # -- playback --------------------------------------------------
        def _toggle_play(self) -> None:
            if self._player.playbackState() == QtMultimedia.QMediaPlayer.PlayingState:
                self._player.pause()
            elif self._player.source().isEmpty():
                self._render_and_play()
            else:
                self._player.play()

        def _seek(self, value) -> None:
            # sliders emit int; waveform emits float fraction
            if isinstance(value, float) and 0.0 <= value <= 1.0:
                pos = int(value * self._player.duration())
            else:
                pos = int(value)
            if self._player.duration() > 0:
                self._player.setPosition(max(0, min(pos, self._player.duration())))

        def _on_position(self, pos: int) -> None:
            dur = self._player.duration() or 1
            self.waveform.set_progress(pos / dur)
            if not self.position.isSliderDown():
                self.position.setValue(int(1000 * pos / dur))
            self.time_label.setText(f"{_fmt(pos)} / {_fmt(dur)}")

        def _on_duration(self, dur: int) -> None:
            self.time_label.setText(f"{_fmt(self._player.position())} / {_fmt(dur)}")

        def _on_state(self, state) -> None:
            if state == QtMultimedia.QMediaPlayer.PlayingState:
                self.play_btn.setText("Pause")
            else:
                self.play_btn.setText("Play")

        def closeEvent(self, event) -> None:  # noqa: N802 - Qt naming
            self._player.stop()
            self._tmpdir.cleanup()
            super().closeEvent(event)

    return MainWindow


def _peaks(data, columns: int = 1000):
    import numpy as np

    n = len(data)
    if n == 0:
        return []
    step = max(1, n // columns)
    out = []
    for start in range(0, n, step):
        chunk = data[start: start + step]
        if len(chunk) == 0:
            continue
        out.append((float(chunk.min()), float(chunk.max())))
    return out


def _fmt(ms: int) -> str:
    seconds = max(0, int(ms // 1000))
    return f"{seconds // 60}:{seconds % 60:02d}"


def main(argv: list[str] | None = None) -> int:
    QtCore, QtGui, QtMultimedia, QtWidgets = _qt()
    args = list(sys.argv[1:] if argv is None else argv)
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([sys.argv[0]])
    Window = make_window()
    audio = args[0] if args else None
    window = Window(audio)
    window.show()
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
