# 发布前回归记录

- 日期：2026-10-19
- 环境：Windows（win32）、Python 3.13.8、musicfab 0.1.0
- 分支：`main`（工作区干净）

## 1. 测试

```bash
python -m pytest -q
# 43 passed in ~104s
```

覆盖：音频 I/O、工程格式、转谱、变速/移调、逐音编辑、拍点/下拍、分轨（含分块）、DAW 打包、记谱 PDF/PNG、六线谱渲染、GUI 冒烟、doctor。

## 2. 环境自检

```bash
musicfab doctor --strict
# exit 0
# ready: probe transcribe practice shift notes beats separate notation pdf tab gui (11/11)
# missing: []
# model cache: ~/.cache/torch/hub/checkpoints (htdemucs 权重已缓存)
```

- `ffmpeg`: 未在 PATH 中（WAV/FLAC/OGG 由 libsndfile 处理；MP3 需 ffmpeg 或 libsndfile ≥1.2）。

## 3. 端到端演示（4 秒合成旋律）

```bash
python examples/demo.py
```

| 步骤 | 结果 | 耗时 |
|---|---|---|
| transcribe | 8 个音符，音高 `[60,62,64,65,67,69,71,72]` | 4.9 s |
| practice | 0.5x 变速输出 | 0.6 s |
| shift | +3 半音输出 | 0.1 s |
| separate | 4 轨（drums/bass/other/vocals） | 9.8 s |
| notes | 1 个逐音编辑（+12 半音） | 0.5 s |
| notation | SVG + PDF（非空白） | 1.5 s |

## 4. 文档产物

```bash
musicfab tab tests/fixtures/Chords.gp5 -o build/reg_tab.pdf -f pdf      # 27.7 KB
musicfab notation build/demo/demo.musicxml -o build/reg_score.pdf -f pdf # 40.1 KB
```

- PDF 非空白校验通过（PyMuPDF 抽样非白像素 > 阈值）；
- `docs/gui.png`、`docs/tab.png`、`docs/score.png`、`docs/score_full.png` 均已用最新代码重新生成。

## 5. 便携包（lite）

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_portable.ps1
dist/musicfab.exe   # 185 MB, onefile
```

实测（本文档日期构建）：

| 命令 | 结果 |
|---|---|
| `version` / `doctor` | ✅ |
| `transcribe` | ✅ 输出 MIDI |
| `notation -f pdf` | ✅ 40 KB |
| `tab -f pdf` | ✅ |
| `notes`（生成编辑表） | ✅ |
| `practice` / `shift` | ❌ 需源码安装（numba 冻结限制） |
| `rip` / `separate` | ❌ 未打包 torch/demucs |

## 6. 发布状态

- [x] 六大替代模块可运行并通过回归
- [x] 文档（README/INSTALL/PLAN/LICENSES/COMPAT/REVIEW/COMPARISON/RELEASE/CHANGELOG）
- [x] 演示与截图
- [ ] 推送到 GitHub（等待用户创建空仓库；脚本 `scripts/publish_github.ps1` 已就绪）
- [ ] CI 首跑与 `v0.1.0` tag
