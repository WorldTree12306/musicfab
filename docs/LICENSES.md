# 第三方组件许可证清单

> 原则：本仓库只包含 MIT 许可的自有代码；第三方全部通过 pip/CLI/子进程使用，不复制源码、不打包商业软件的任何数据。
> 发布前逐项核对；标注 NC（非商用）的组件仅在个人/自用场景启用。

| 组件 | 用途 | 许可证 | 备注 |
|---|---|---|---|
| numpy / scipy / soundfile | 数值与音频 I/O | BSD-3 / BSD-3 / LGPL-2.1 | LGPL 动态使用 |
| mido | MIDI 读写 | MIT | |
| music21 | MusicXML 生成 | BSD-3 | |
| librosa | 特征/变速/变调 | ISC | |
| pretty_midi | MIDI 辅助 | MIT | |
| piano_transcription_inference | 钢琴转谱 | MIT（模型权重需查仓库声明） | 模型单独下载 |
| basic-pitch (Spotify) | 通用转谱 | Apache-2.0 | ONNX 模型随包（230 KB），以 `--no-deps` 安装 |
| resampy / mir_eval / scikit-learn | basic-pitch 运行依赖 | ISC / MIT / BSD-3 | |
| torch / torchaudio | 推理运行时（可选） | BSD-3 | CPU wheel |
| Demucs | 分轨 | MIT（**代码**）；`htdemucs` 权重为 CC-BY-4.0，分发时注明来源 | 首次运行自动下载 |
| dora-search / openunmix / einops / julius / lameenc | demucs 依赖 | MIT / MIT / MIT / MIT / LGPL-2.1 | 仅本地安装 |
| pyguitarpro | 读取 .gp3/.gp4/.gp5 | LGPL-3 | 作为普通依赖 import（LGPL 允许动态使用） |
| verovio | MusicXML/MEI 渲染 SVG | LGPL-3 | Python wheel |
| pymupdf（可选，PDF/PNG） | SVG→PDF/PNG | **AGPL-3.0** | 仅作为可选依赖安装；不随仓库分发。个人自用无影响，商用发布需评估 |
| cairosvg（可选） | SVG→PNG/PDF | LGPL-3 | Windows 需 cairo DLL；优先用 PyMuPDF |
| MuseScore CLI | 排版/导出 PDF | GPL-3 | **仅子进程调用**，不链接 |
| Verovio | MEI/MusicXML 渲染 | LGPL-3 | 子进程或 wheel |
| LilyPond | 排版 | GPL-3 | 子进程 |
| Rubber Band CLI | 高质量变速/变调 | GPL-2 | 子进程 |

## 发布注意
1. 不要把商业软件（AnthemScore/Melodyne/Transcribe!/RipX/Capella/Guitar Pro）的二进制、模型权重、反编译代码放入仓库。
2. CC-BY-NC 的模型权重不随仓库分发，只提供下载脚本；商用需替换。
3. GPL 工具只通过命令行调用，不 import、不链接。
