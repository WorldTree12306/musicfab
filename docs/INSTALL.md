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
| transcribe（AnthemScore） | `pip install basic-pitch --no-deps` + `pip install mir_eval scikit-learn "resampy>=0.4.2,<0.4.3"` | 否（ONNX 模型随包） |
| transcribe 钢琴增强 | `pip install piano_transcription_inference` | 是（首次下载权重） |
| practice / shift | `pip install librosa` | 否 |
| separate（RipX） | `pip install "demucs==4.0.1" --no-deps` + `pip install dora-search openunmix einops julius lameenc pyyaml tqdm` | 是（首次下载 80 MB htdemucs 权重） |
| notation（Capella） | `pip install verovio`；PDF/PNG 另装 MuseScore 4 | 否 |
| tab（Guitar Pro） | `pip install pyguitarpro` | 否 |

> Demucs 需要 torch：`pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu`（CPU 版约 200 MB）。

## 3. 测试与演示

```bash
python scripts/gen_test_audio.py      # 生成合成测试音频
python scripts/fetch_fixtures.py      # 可选：下载 .gp5 样例（PyGuitarPro 测试集）
python -m pytest -q                   # 11 tests
python examples/demo.py               # 端到端演示 -> build/demo/
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
pip install pyinstaller
pyinstaller -n musicfab --onefile --collect-submodules musicfab src/musicfab/__main__.py
```

- 轻量包（只含 transcribe/practice/shift/notation/tab）：约 60–80 MB。
- 含 torch/demucs 的完整包会到 1 GB 以上；建议用「程序 + 首次运行时下载权重」的方式分发。

## 5. MuseScore（PDF/PNG 排版）

1. 从 <https://musescore.org> 下载 MuseScore 4（GPL）；
2. 安装后确保 `musescore4`/`MuseScore4.exe` 在 PATH 或默认安装目录；
3. `musicfab notation song.musicxml -o song.pdf -f pdf`。

musicfab 只通过子进程调用 MuseScore，不做链接，避免 GPL 传染。

## 6. Windows 注意事项

- `cairosvg` 需要系统 cairo DLL，通常不可用；PDF/PNG 优先走 MuseScore。
- MP3 解码依赖 `soundfile` 的 libsndfile ≥ 1.2 或系统 ffmpeg；没有 ffmpeg 时请先转 WAV。
- 所有模型权重缓存在 `%USERPROFILE%\.cache\torch\hub\checkpoints`（Demucs）与 basic-pitch 包内（230 KB）。

## 7. 便携 exe 常见问题

| 现象 | 原因 | 解决 |
|---|---|---|
| `[PYI-…] Could not create temporary directory!` | onefile 需要可写的 `%TEMP%`（部分安全策略/杀软会拦） | `set TEMP=D:\tmp` 后运行，或改用 `--onedir` 构建 |
| `cannot cache function '__o_fold': no locator available` | 冻结包里 numba 无法建立 JIT 缓存 | 已在 `musicfab/__init__.py` 对 frozen 环境自动设置 `NUMBA_DISABLE_JIT=1` 并重编 |
| 首次启动慢 | onefile 每轮都要解包 155 MB | 发布可用 `--onedir` 版本，启动更快 |

> 便携包（lite）包含 transcribe/practice/shift/notation/tab；**分轨（demucs/torch）不打包**，需要源码安装。
