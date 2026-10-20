# 第三方组件许可证清单

> 原则：本仓库只包含 MIT 许可的自有代码；第三方全部通过 pip/CLI/子进程使用，不复制源码、不打包商业软件的任何数据。
> 机器可读的版本/许可清单由 `scripts/collect_licenses.py` 生成（`THIRD_PARTY_NOTICES.md`），便携包发布 zip 内附带该文件。

## 1. 仓库 / 开发依赖（pip 安装，不随发布物分发）

| 组件 | 用途 | 许可证 | 备注 |
|---|---|---|---|
| numpy / scipy | 数值计算 | BSD-3 | |
| soundfile | 音频 I/O | LGPL-2.1（libsndfile 动态捆绑于 wheel） | |
| setuptools | resampy 运行期 pkg_resources 依赖 | MIT | |
| mido | MIDI 读写 | MIT | |
| music21 | MusicXML 生成 | BSD-3 | |
| pretty_midi | MIDI 辅助 | MIT | |
| librosa / resampy / soxr | 特征/变速/变调/重采样 | ISC / ISC / MPL-2.0(soxr) | |
| basic-pitch (Spotify) | 通用转谱 | Apache-2.0 | ONNX 模型随包（230 KB），以 `--no-deps` 安装避免 TensorFlow |
| onnxruntime | 转谱推理运行时 | MIT | |
| mir_eval / scikit-learn | basic-pitch 运行依赖 | MIT / BSD-3 | |
| piano_transcription_inference | 钢琴转谱（可选 pti） | MIT（模型权重需查仓库声明） | 权重单独下载 |
| torch | Demucs 推理 / 可选 PTI | BSD-3 | CPU wheel，不进便携包 |
| Demucs（代码） | 分轨 | **MIT** | 见第 4 节权重说明 |
| dora-search / openunmix / einops / julius / lameenc | demucs 依赖 | MIT / MIT / MIT / MIT / LGPL-2.1 | 仅本地安装 |
| pyguitarpro | 读取 .gp3/.gp4/.gp5 | LGPL-3 | 作为普通依赖 import（LGPL 允许动态使用） |
| verovio | MusicXML/MEI 渲染 SVG | LGPL-3 | Python wheel |
| PySide6 | GUI | LGPL-3 | 不进便携包（excludes） |
| cairosvg（可选） | SVG→PNG/PDF 备选 | LGPL-3 | Windows 需 cairo DLL；优先 PyMuPDF |
| pytest / pyinstaller | 测试与打包 | MIT / GPL(bootloader 例外) | 仅开发期 |

## 2. 便携包捆绑（dist/musicfab-<version>-win64.zip）

以下组件会以二进制形式进入发布 zip，zip 内附带 `THIRD_PARTY_NOTICES.md`：

| 组件 | 许可证 | 义务与来源 |
|---|---|---|
| PyMuPDF | **AGPL-3.0** | zip 接收者可依 AGPL 索取对应源码；确切版本见通知文件，上游源码 <https://github.com/pymupdf/PyMuPDF>。本项目为个人非商用、不修改 PyMuPDF 的 MIT 代码库 |
| resvg-py | **MPL-2.0** | 文件级 copyleft，随包附带版本与来源（上游 resvg：<https://github.com/RazrFalcon/resvg>）即满足归属要求 |
| verovio / music21 / basic-pitch 等 wheel 内数据 | LGPL-3 / BSD-3 / Apache-2.0 | 见通知文件表格 |

## 3. 仅子进程调用的外部工具（不 import、不链接、不分发）

| 组件 | 许可证 | 状态 |
|---|---|---|
| MuseScore CLI | GPL-3 | 已支持：排版/导出 PDF 的首选后端，仅 `-o` 子进程调用 |
| LilyPond / Rubber Band CLI | GPL-2 / GPL-2 | 预留（当前代码未调用），若启用同样仅子进程 |

## 4. 模型权重

- **htdemucs**：Demucs 代码 MIT，权重为 **CC-BY-4.0**，来源 <https://github.com/adefossez/demucs>（首次运行自 `dl.fbaipublicfiles.com` 下载并缓存）。**权重不随仓库或发布物分发**，分发产物时注明来源即可。
- **Basic Pitch ICASSP 2022 ONNX**：随 basic-pitch wheel（Apache-2.0），进入便携包。

## 发布注意

1. 不要把商业软件（AnthemScore/Melodyne/Transcribe!/RipX/Capella/Guitar Pro）的二进制、模型权重、反编译代码放入仓库。
2. 发布便携 zip 前，`scripts/build_portable.ps1` 会自动生成 `THIRD_PARTY_NOTICES.md` 并与 exe 一起打包；发布说明中引用该文件与上游源码链接。
3. CC-BY-NC 类权重不随仓库分发，只提供下载脚本；商用需替换。
4. GPL 工具只通过命令行调用，不 import、不链接。
