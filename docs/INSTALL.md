# 安装与部署（离线）

musicfab 本体只依赖 `numpy/scipy/soundfile`；六个能力按需安装后端，全部可离线运行。

## 1. 基础安装

```bash
git clone <your-fork-url> musicfab && cd musicfab
python -m pip install -e ".[dev]"     # 开发
# 或最小运行：
python -m pip install -e .
python -m pip install mido music21 librosa pretty_midi
musicfab version
```

要求 Python ≥ 3.10（实测 3.13 通过）。

## 2. 各模块后端

| 模块 | 安装命令 | 首次联网？ |
|---|---|---|
| transcribe（AnthemScore） | `pip install -e ".[transcribe-onnx]"` + `pip install basic-pitch --no-deps` | 否（ONNX 模型随包） |
| transcribe 钢琴增强 | `pip install piano_transcription_inference` | 是（首次下载权重） |
| practice / shift | `pip install librosa` | 否 |
| separate（RipX） | `pip install "demucs==4.0.1" --no-deps` + `pip install dora-search openunmix einops julius lameenc pyyaml tqdm` | 是（首次下载 80 MB htdemucs 权重） |
> 长音频（>4 分钟）自动分块 overlap-add，内存只驻留单个分块；可用 `--chunk-seconds 30` 强制指定分块大小。
| notation（Capella） | `pip install verovio pymupdf resvg-py`（MuseScore 4 可选，矢量排版更佳） | 否 |
| tab（Guitar Pro） | `pip install pyguitarpro` | 否 |

> Demucs 需要 torch：`pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu`（CPU 版约 200 MB）。
>
> 转谱说明：`[transcribe-onnx]` extra 提供 ONNX 转谱的全部运行依赖（mir_eval / scikit-learn / resampy / onnxruntime / setuptools 约束）；`basic-pitch` 本体因 PyPI 上声明 TensorFlow 依赖（Windows/py3.11+），需 `--no-deps` 单独安装以避免约 600 MB 的 TensorFlow——实测 ONNX 后端完全可用。`[transcribe]` 是 `[transcribe-onnx]` 的等价别名（历史兼容）。

## 2.5 图形界面（可选）

```bash
pip install "musicfab[gui]"     # PySide6
musicfab gui song.wav
```

界面功能：波形总览、**鼠标拖拽 A/B 选区循环**（双击清除）、播放/暂停、0.5x–1.5x 变速、±12 半音移调、按小节循环（自动检测拍号与下拍）。
渲染在本地完成（与 `musicfab practice` 同一套相位声码器），不联网。

## 3. 测试与演示

```bash
python scripts/gen_test_audio.py      # 生成合成测试音频
python scripts/fetch_fixtures.py      # 可选：下载 .gp5 样例（PyGuitarPro 测试集）
musicfab doctor                       # 环境自检（JSON）
python -m pytest -q                   # 67 tests
python examples/demo.py               # 端到端演示 -> build/demo/

逐音编辑（Melodyne 式）：
python -m musicfab.cli notes song.wav -o edits.json     # 生成编辑表（检测音符）
# 修改 edits.json 里某条的 semitones / duration_scale / velocity_scale
python -m musicfab.cli notes song.wav --edits edits.json -o edited.wav

分轨到 DAW：
python -m musicfab.cli separate song.wav --transcribe --auto-tempo -o stems/
python -m musicfab.cli daw stems/ --name mysong
```

示例输出（本机实测，CPU）：

```
transcribe: 8 notes, pitches=[60,62,64,65,67,69,71,72]  4.2s
separate:   drums/bass/other/vocals                     8.9s (4s 音频)
practice:   0.5x + -2 半音                              0.6s
shift:      +3 半音                                     0.1s
notation:   MusicXML -> SVG                             0.3s
```

## 4. 便携包（可选）

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_portable.ps1
```

- 产物：`dist/musicfab.exe`（lite onefile，约 185 MB）+ `dist/THIRD_PARTY_NOTICES.md` + `dist/musicfab-<version>-win64.zip`；
- 构建走 `musicfab.spec`（含 numba runtime hook 与 basic_pitch/music21/verovio 数据）；
- 含 torch/demucs 的完整包会到 1 GB 以上；建议用「程序 + 首次运行时下载权重」的方式分发。

## 5. PDF/PNG 导出与 MuseScore（可选）

默认路线：MusicXML → Verovio SVG → **resvg** 光栅化 → PyMuPDF 出 PDF/PNG，只需 `pip install verovio pymupdf resvg-py`，无需系统库。

若要更好的排版（连音、歌词、多声部更精确），可另装 MuseScore 4（GPL）：
1. 从 <https://musescore.org> 下载安装；
2. 确保 `musescore4`/`MuseScore4.exe` 在 PATH 或默认安装目录（也可设 `MUSESCORE_BIN`）；
3. `musicfab notation song.musicxml -o song.pdf -f pdf` 会自动优先用 MuseScore。

musicfab 只通过子进程调用 MuseScore，不做链接，避免 GPL 传染。

## 6. Windows 注意事项

- `cairosvg` 需要系统 cairo DLL，通常不可用；PDF/PNG 优先走 MuseScore。
- MP3 解码依赖 `soundfile` 的 libsndfile ≥ 1.2 或系统 ffmpeg；没有 ffmpeg 时请先转 WAV。
- 所有模型权重缓存在 `%USERPROFILE%\.cache\torch\hub\checkpoints`（Demucs）与 basic-pitch 包内（230 KB）。

## 7. 便携 exe（lite）实测范围

发布资产：`dist/musicfab-<version>-win64.zip`（内含 `musicfab.exe` 与 `THIRD_PARTY_NOTICES.md`），exe 约 185 MB。本机实测：

| 子命令 | 便携包 | 说明 |
|---|---|---|
| `version` / `probe` | ✅ | |
| `transcribe` | ✅ | basic-pitch ONNX 随包，无需 TF |
| `notation` | ✅ | MusicXML/MIDI/SVG（Verovio） |
| `tab` | ✅ | .gp3/.gp4/.gp5 |
| `notes`（仅检测/编辑表） | ⚠️ | 检测可用；`--edits` 重合成需源码安装（同 practice） |
| `practice` / `shift` / `notes`（重合成） | ❌ | librosa 的 numba `vectorize` 在冻结包内无法缓存（onedir/noarchive 方案亦失败）；请用源码安装 |
| `separate` | ❌ | 需要 torch/demucs，未打包 |

常见问题：

| 现象 | 原因 | 解决 |
|---|---|---|
| `[PYI-…] Could not create temporary directory!` | onefile 需要可写 `%TEMP%`（安全策略/杀软可能拦） | `set TEMP=D:\tmp` 后运行，或改用 `--onedir` |
| `cannot cache function ... no locator available` | 冻结包内 numba 无法建立 JIT 缓存 | 已用 runtime hook 强制 `cache=False`；practice/shift 仍建议源码安装 |
| 首次启动慢 | onefile 每轮解包 155 MB | 发布可用 `--onedir` 提高启动速度 |
