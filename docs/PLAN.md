# musicfab 六模块实施计划

目标：用开源组件实现六个商业音乐软件的核心能力，全部离线、可批量、可脚本化。
代码 MIT；模型/工具按各自许可证使用（见 `docs/LICENSES.md`）。

## Phase 0 — 骨架（本目录）
- 包结构、CLI、统一工程格式、音频 I/O、导出骨架、测试音频
- 验收：`musicfab version` / `probe` / `pytest` 通过

## Phase 1 — transcribe（AnthemScore 替代）✅
- 后端：`basic-pitch` ONNX（默认，无 TF）→ `piano_transcription_inference`（可选，钢琴）
- 实现：`modules/transcribe.py`（阈值/最短音长/量化、MIDI+MusicXML 导出）
- 验收：`melody.wav` 转谱 12 音（C 大调序列吻合）✅；MusicXML 可被 music21/MuseScore 读入 ✅

## Phase 2 — practice（Transcribe!）/ shift（Melodyne）✅
- practice：librosa 变速/移调/循环切片 + `.practice.json` 参数记录
- shift：相位声码器变调（音频级）+ `shift_notes`（谱面级，不改音频）
- notes：逐音编辑（semitones / start_shift / duration_scale / velocity_scale），只重合成被编辑片段，其余原音保留 ✅
- 验收：0.5x 时长≈2x（容差 25%）✅；+12 半音主频≈2x ✅

## Phase 3 — separate（RipX）✅
- Demucs htdemucs（4 轨：drums/bass/other/vocals），权重首次自动下载（80 MB）
- `--transcribe` 可对每轨复用 Phase 1 生成 `.mfproj.json`
- 验收：4 轨输出 + 44.1k 采样率 + stems.json 清单 ✅（5.3s 音频 CPU 9.4s）

## Phase 4 — notation（Capella）/ tab（Guitar Pro）✅
- notation：MusicXML/MIDI 互转（music21）、SVG（Verovio）、PDF/PNG（PyMuPDF 内置；MuseScore 可选更佳排版）
- tab：PyGuitarPro 读取 `.gp3/.gp4/.gp5` → JSON/MIDI/MusicXML；`.gpx` 需先转（文档说明）
- 验收：`.gp5` 样例解析出音轨/音符并导出 MIDI ✅；MIDI→MusicXML→SVG 链路 ✅

## Phase 5 — 打包与发布
- [x] 安装说明 / 许可证清单 / 兼容性说明
- [x] pytest 全绿（含慢速分轨测试标记）
- [ ] PyInstaller 便携包
- [ ] GitHub Actions（Windows/Linux 单测 + 示例产物）
