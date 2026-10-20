# 代码审查：优化空间清单（GLM，2026-10-20）

对 musicfab 的一次只读优化审查（GLM，plan 模式），共 12 条。本文件记录状态，便于后续继续处理。

## 已修复（0.1.1，本批）

| # | 问题 | 修复 |
|---|---|---|
| 1 | Verovio 只渲染第 1 页，长曲 PDF/PNG 静默丢页 | `notation._render_verovio_svgs()` 渲染全部页；PDF 合成多页；SVG/PNG 第 2 页起写 `<stem>_pN.<ext>` 并在 stderr 报告页数 |
| 5 | `Project.from_notes` 把 `audio` 吞进 `meta`，顶层 `audio` 恒为空 | 新增显式 `audio` / `beats` 形参；`transcribe()` 直接传入；补 round-trip 测试 |
| 6 | 无 NaN/Inf 防护；`Project.load` 报错无上下文 | `audio.load/write` 校验有限值并抛带路径的 `ValueError`；`Project.load` 对 note/track/tempo/beats 校验并带文件路径 |
| 7 | `--tempo` 在 practice（倍速）与 transcribe（BPM）语义不同；doctor 误报 | practice 新增 `--speed` 等价别名；doctor 的 `transcribe` 要求 basic-pitch+onnxruntime，新增 `pti`，`pdf` 识别 cairosvg/MuseScore 备选 |
| 8 | `musicfab notes` 模板模式跑两次模型推理 | `write_template()` 返回 `(path, notes)`，CLI 复用结果 |
| 9 | 先量化后合并导致尾碎片合并失效 | `_merge_same_pitch()` 移到量化之前；量化后只兜底零长度 |
| 10 | beats 的 onset 包络/STFT 重复计算 | onset envelope 只算一次，`beat_track` 与八度校正共享 |

新增测试：`tests/test_multipage_notation.py`（3 项：多页 PDF 逐页非空白、SVG/PNG 分页文件、stderr 页数提示）、`tests/test_batch2_fixes.py`（11 项：schema/NaN/错误上下文/别名/doctor/单次推理/合并顺序）。

## 已修复（0.2.0）

| # | 问题 | 修复 |
|---|---|---|
| 2 | 排版 MIDI 往返 | music21 直接构造（Part/partName/tempo/拍号，tie 拆分，16 分网格，输入不改） |
| 3 | 重复测速与模型加载 | mixture 测速一次共享；Basic Pitch 模型缓存 |
| 4 | 分块分离内存/边界/清理 | 两侧 reflect-pad、就地除法、memmap 分块流式写、异常清理 `.chunked` |

## 待处理（按收益排序）

| # | 问题 | 建议 | 工作量 |
|---|---|---|---|
| 11 | CI 无 pip 缓存；`[transcribe]` extra 装不出转谱；spec 硬编码本机路径 | setup-python 加 `cache: pip`；新增 `transcribe-onnx` extra；spec 路径用 `sysconfig` | S |
| 12 | 发布物许可声明：便携包捆绑 PyMuPDF（AGPL）/resvg（MPL），LICENSES 有死条目 | release 附第三方许可文本与源码链接；清理 LICENSES | S-M |

## 备注

- 便携 exe 的 numba 限制、无 ffmpeg、下拍启发式、和弦逐音重合成伪影为已知且接受项，不在本清单。
- 后续每批修复都应保持 `pytest -q` 全绿（当前 65 项）。
