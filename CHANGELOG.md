# Changelog

## 0.3.0 — 2026-10-20

收尾批次（GLM 审查 #11/#12，优化清单 12/12）：

- **CI**：`actions/setup-python` 启用 pip 缓存（`pyproject.toml`）、job `timeout-minutes: 30`；保留失败注解与依赖版本 notice
- **打包**：`musicfab.spec` 成为唯一规范配方（顶部注明用法）；删除硬编码本机路径的实验 `musicfab_onedir.spec`；`build_portable.ps1` 改走 spec、使用当前解释器、构建后自动生成许可通知并打成 `dist/musicfab-<version>-win64.zip`
- **安装**：新增 `transcribe-onnx` extra（与 `transcribe` 等价，含 onnxruntime、setuptools 约束）；INSTALL 说明 `basic-pitch --no-deps` 的 ONNX 安装方式
- **许可证**：新增 `scripts/collect_licenses.py` 生成 `THIRD_PARTY_NOTICES.md`（含 Demucs 权重 CC-BY-4.0 与 PyMuPDF AGPL / resvg MPL 义务）；`LICENSES.md` 清理死条目；`RELEASE.md` 明确 zip 资产与源码链接
- 测试：65 → 67 项

## 0.2.0 — 2026-10-20

优化批次二（GLM 审查 #2/#3/#4）：

- **notation / export**：`to_musicxml` 改为 music21 直接构造（每轨一个 Part、保留 partName/tempo/拍号、不可记谱时值拆成 tie 链、输入 Project 不再被修改）；显式量化按拍格吸附后落到 1/16 note 网格，避免 MusicXML 不可记谱的碎时值；异常时回退旧 MIDI 路径
- **transcribe**：Basic Pitch ONNX 模型/会话模块级缓存，多文件/多 stem 批量转谱不再重复建会话
- **separate**：`--auto-tempo` 改为在 mixture 上只测一次并共享给所有 stem（修复各 stem 拍格不一致导致的总谱/DAW 错位）；`--no-separate` 与 rip 复用同一测速逻辑
- **separate 分块模式**：输入两侧 reflect-pad 半个 segment（消除首尾上下文截断）、累加器就地除法（峰值内存 O(chunk)）、memmap 分块流式写 WAV、失败时清理 `.chunked` 临时目录
- 测试：58 → 65 项

## 0.1.1 — 2026-10-20

优化批次一（GLM 审查后修复）：

- notation：修复 **Verovio 只渲染第 1 页**，长曲 PDF 现在包含全部页；SVG/PNG 第 2 页起写 `<stem>_pN` 并在 stderr 报告页数
- project：`from_notes` 支持顶层 `audio`/`beats` 字段；`Project.load` 对 note/track/tempo/beats 给出带文件路径的错误
- audio：读写前校验 NaN/Inf，坏音频不再产生静默垃圾
- transcribe：同音碎片合并在量化之前执行（量化路径下谱面更干净）
- beats：onset 包络只计算一次（拍点/八度校共享），减少重复特征提取
- notes：模板模式只跑一次模型推理
- cli：`practice --speed` 作为 `--tempo` 的等价别名
- doctor：`transcribe` 需 basic-pitch+onnxruntime；新增 `pti`；`pdf` 识别 cairosvg/MuseScore 备选
- 测试：44 → 58 项

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
- 58 项 pytest、GitHub Actions CI（Windows/Linux × py3.11/3.12）
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
