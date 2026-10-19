# musicfab — 六个商业音乐软件的开源免费替代

musicfab 用开源模型与库重新实现六个常见商业音乐工具的核心能力，全部可离线运行、可脚本化、可批量处理。

| 原商业软件 | musicfab 子命令 | 开源技术栈 |
|---|---|---|
| AnthemScore（音频→乐谱） | `musicfab transcribe` | piano_transcription_inference / basic-pitch / MT3 + Beat-This + music21 |
| Melodyne（音符级修音/变调） | `musicfab shift` / `musicfab notes edit` | CREPE/pYIN + pyworld/PSOLA + librosa |
| Transcribe!（慢放/循环/移调） | `musicfab practice` | librosa / Rubber Band + 循环切片 |
| RipX（分轨+转谱+DAW） | `musicfab separate` + `transcribe` | Demucs / Spleeter + Basic Pitch + MIDI 工程 |
| Capella（记谱/排版） | `musicfab notation` | MuseScore CLI / LilyPond / Verovio |
| Guitar Pro（六线谱） | `musicfab tab` | PyGuitarPro + alphaTab / TuxGuitar 格式互操作 |

> **合规声明**：本项目是 clean-room 实现，只使用开源组件；不包含、不反编译、不分发任何商业软件（AnthemScore、Melodyne、Transcribe!、RipX、Capella、Guitar Pro）的代码、模型权重或授权数据。详见 `docs/LICENSES.md`。

## 快速开始

```bash
python -m pip install -e .
musicfab --version
musicfab probe your_song.mp3
musicfab transcribe your_song.mp3 -o out.mid --musicxml out.musicxml
```

## 子命令

| 命令 | 说明 | 状态 |
|---|---|---|
| `probe` | 查看音频信息（格式/采样率/时长/声道） | ✅ |
| `transcribe` | 音频转 MIDI/MusicXML（AnthemScore 替代） | ✅ basic-pitch(ONNX) / PTI 可选 |
| `practice` | 变速/移调/循环练习（Transcribe! 替代） | ✅ |
| `shift` | 音符级变调（Melodyne 替代） | ✅ 音频级 / 谱面级 `shift_notes` |
| `separate` | 分轨（RipX 替代） | ✅ htdemucs 4 轨，可 `--transcribe` 逐轨转谱 |
| `notation` | 记谱/排版/导出（Capella 替代） | ✅ MusicXML/MIDI/SVG；PDF/PNG 需 MuseScore CLI |
| `tab` | 六线谱导入（Guitar Pro 替代） | ✅ `.gp3/.gp4/.gp5` → JSON/MIDI/MusicXML |

## 安装可选后端

```bash
# 转谱（默认 ONNX 后端，无需 TensorFlow；模型 230 KB 随包）
pip install basic-pitch --no-deps
pip install mir_eval scikit-learn "resampy>=0.4.2,<0.4.3"

# 钢琴专用转谱（可选，质量更好，需要 torch）
pip install piano_transcription_inference

# 分轨（RipX 替代）
pip install "demucs==4.0.1" --no-deps
pip install dora-search openunmix einops julius lameenc pyyaml tqdm
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu

# 六线谱 / 渲染
pip install pyguitarpro verovio
# PDF/PNG 导出另需 MuseScore 4（GPL，仅子进程调用）
```

> 说明：`basic-pitch` 在 PyPI 上声明 TensorFlow 依赖（Windows/py3.11+），但本项目走 **ONNX 后端**，用 `--no-deps` 安装即可避免 600 MB 的 TensorFlow，实测完全可用。

## 项目格式

统一的 JSON 工程（`.mfproj.json`）：

```json
{
  "format": "musicfab-project",
  "version": 1,
  "name": "song",
  "audio": {"path": "song.wav", "sample_rate": 44100},
  "tempo": 120.0,
  "beats": [],
  "tracks": [{"name": "main", "instrument": 0,
              "notes": [{"start": 0.0, "end": 0.5, "pitch": 60, "velocity": 80}]}],
  "meta": {}
}
```

## 开发

```bash
python -m pip install -e ".[dev]"
pytest -q
python scripts/gen_test_audio.py    # 生成测试音频
```

## License

本项目代码 MIT。第三方组件许可证见 `docs/LICENSES.md`；其中 GPL 工具（MuseScore、Rubber Band 等）一律以**子进程**方式调用，不作为库链接，避免许可证传染。
