# 能力对照：musicfab vs 六个商业软件

> 说明：本表只陈述 musicfab 自身能力与已知限制；“商业对照”列仅指该软件的主要用途，不评价其具体功能细节。
> musicfab 是 clean-room 实现，与这些软件无任何代码/模型/授权关联。

## 总览

| 能力 | 商业对照 | musicfab 命令 | 实现方式 | 已知限制 |
|---|---|---|---|---|
| 音频 → MIDI/乐谱 | AnthemScore | `transcribe` / `notation` / `score` | Basic Pitch ONNX（可选 PTI）+ music21 + Verovio | 无图形编辑；和弦/复杂织体精度低于专有模型；无拍号自动识别（可用 `--auto-tempo` 测速） |
| 音符级修音/变调 | Melodyne | `notes` / `shift` | 逐音变调/时值/力度 + 相位声码器重合成 | 只重合成被编辑片段；密集和弦有伪影（建议先分轨）；无共振峰/频谱画笔编辑 |
| 慢放/循环/移调练习 | Transcribe! | `practice` / `gui` | librosa 变速/移调 + 拍点/小节检测 + PySide6 播放器 | 无视频/谱面同步；音频格式依赖 soundfile/ffmpeg；GUI 为最小实现 |
| 分轨 + 转谱 + DAW | RipX | `separate` / `daw` / `score` | Demucs htdemucs 4 轨 + 逐轨 Basic Pitch + 多轨 MIDI/总谱 | 4 轨固定（drums/bass/other/vocals）；无音符级 DAW 编辑；DAW 工程以 MIDI+WAV 交付 |
| 记谱/排版 | Capella | `notation` / `score` | music21 → MusicXML/MEI → Verovio → SVG/PDF/PNG | 不支持歌词/和弦符号编辑；排版质量取决于 Verovio；无交互式谱面编辑 |
| 六线谱 | Guitar Pro | `tab` | PyGuitarPro 解析 gp3/gp4/gp5 + 自研 SVG/HTML 渲染 | 只读 + 渲染，不能编辑六线谱；`.gpx` 需先转换；无音色/效果回放 |

## 组合工作流

| 需求 | 推荐命令组合 |
|---|---|
| 单曲扒谱（钢琴/旋律） | `transcribe --auto-tempo --quantize-beats 1` → `notation --quantize-beats 1 -f pdf` |
| 练习一首歌 | `gui song.wav`（拖拽 A/B 或按小节循环）；或 `practice --loop-beats 8` |
| 修一个错音 | `notes song.wav -o edits.json` → 改 JSON → `notes song.wav --edits edits.json -o fixed.wav` |
| 全曲拆解（RipX 式） | `rip song.wav -o out/ --quantize-beats 1`（一次出 stems/projects/MIDI/DAW/总谱） |
| 分轨后进 DAW | `separate song.wav --transcribe --auto-tempo -o stems/` → `daw stems/` |
| 六线谱查看/打印 | `tab song.gp5 -f html`（浏览器打开）或 `-f pdf` |

## 与商业软件的共同边界

1. **不和任何商业软件交换工程文件**：AnthemScore `.asdt`、Melodyne `.mdd`、Capella `.capx` 等封闭格式不解析；用 MIDI/MusicXML 作为交换格式。
2. **精度差异**：商业软件使用多年积累的专有模型与人工标注数据；musicfab 用公开模型，复杂混音/密集和弦上会有差距，适合个人学习与自用。
3. **无授权绕过**：本项目不包含、不调用、不破解任何商业软件的授权机制。

## 许可与分发

- 代码 MIT；第三方依赖许可见 [`LICENSES.md`](LICENSES.md)。
- Demucs 权重首次运行下载，不随仓库分发；PyMuPDF 为可选 AGPL 依赖（仅个人自用场景启用）。
