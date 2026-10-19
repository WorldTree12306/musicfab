# Changelog

## 0.1.0 — 2026-10-19

首个可运行版本：六个商业音乐软件的开源替代（个人非商用场景）。

### 新增模块

- **transcribe** — 音频转 MIDI/MusicXML（AnthemScore 替代）
  - Basic Pitch ONNX 后端（无需 TensorFlow），可选 `piano_transcription_inference`
  - `--auto-tempo` 自动测速、`--quantize-beats N` 按拍点量化
  - 同音重复检测合并、可选秒级网格量化
- **practice** — 变速/移调/循环练习（Transcribe! 替代）
  - 0.5x–1.5x 变速、±12 半音、`--loop-beats` / `--loop-bars`（按检测下拍对齐）
  - 生成 `.practice.json` 参数记录
- **shift / notes** — 变调与逐音编辑（Melodyne 替代）
  - `shift` 整段变调；`notes` 检测音符 → 编辑表 → 只重合成被编辑片段（音高/时值/起点/力度）
- **separate** — 分轨（RipX 替代）
  - Demucs htdemucs 4 轨；长音频自动分块 overlap-add（memmap，低内存）
  - `--transcribe` 逐轨转谱、`--auto-tempo` 每轨测速、`--quantize-beats` 逐轨量化
- **daw** — 分轨工程打包为多轨 MIDI + `tracks.json` + `grid.json`（拍点/小节）+ README（Ardour/LMMS/Reaper 可导入）
- **score** — 分轨工程合成多轨总谱（MusicXML/PDF/PNG/SVG，可按拍点量化）
- **rip** — 一键工作流：分轨 → 逐轨转谱 → DAW 工程 + 总谱（RipX 式）；`--no-separate` 轻量模式只做转谱+出谱
- **notation** — 记谱/排版（Capella 替代）
  - MusicXML/MIDI 互转（music21）、SVG（Verovio）、PNG/PDF（resvg + PyMuPDF）
- **tab** — 六线谱（Guitar Pro 替代）
  - `.gp3/.gp4/.gp5` → JSON/MIDI/MusicXML；自研 SVG/HTML/PNG/PDF 渲染（真实小节拍号、延音线）
- **beats** — 速度/拍点/下拍估计（低频重音相位 + 置信度）
- **gui** — 离线练习播放器（PySide6）：波形、拖拽 A/B 循环、变速、移调、按小节循环

### 基础设施

- `doctor` 环境自检（依赖/后端/模型缓存/功能可用性）
- 统一 `.mfproj.json` 工程格式（tempo/time_signature/beats/tracks）
- CLI：`version/probe/transcribe/practice/shift/notes/beats/separate/daw/notation/tab/gui`
- 端到端 demo（`examples/demo.py`）、测试夹具生成/下载脚本
- 43 项 pytest、GitHub Actions CI（Windows/Linux × py3.11/3.12）
- 文档：README / INSTALL / PLAN / LICENSES / COMPAT / REVIEW

### 修复

- 逐音编辑片段整体后移 40ms（margin 重复计算）
- 同音连奏被误合并
- 纯 JSON 数组编辑表崩溃、`duration_scale` 极值静默删音
- 拍号/速度丢失（永远 4/4、120）
- 六线谱 4/4 硬编码、弦索引越界、截断静默
- 静音 stem 测速返回 0 BPM
- Verovio SVG 的 `<use>` 字形引用导致 PDF/PNG 空白（改用 resvg 光栅化）

### 已知限制

见 `docs/REVIEW.md` 与 `docs/INSTALL.md`：

- 便携 exe 为 lite 版（transcribe/notation/tab/PDF）；practice/notes 重合成与 GUI 需源码安装（numba 冻结限制）
- 下拍为启发式，复杂编曲可能判错
- 和弦密集时逐音重合成有伪影，建议先分轨再逐轨编辑
- `.gpx` 需先用 TuxGuitar/MuseScore 转换
