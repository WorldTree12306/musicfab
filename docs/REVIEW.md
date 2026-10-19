# 代码审查记录（GLM 只读审查 → 修复状态）

本项目在开发过程中用 GLM 做了两轮只读代码审查（`zcode_run`，plan 模式）。以下是问题与处理状态，便于社区复核。

## 第一轮（核心模块）

| 严重度 | 问题 | 状态 |
|---|---|---|
| 高 | 逐音编辑把片段整体后移 2×margin（40ms），与“未编辑区域原样保留”矛盾 | ✅ 修复（放回原起点） |
| 高 | `_merge_same_pitch` 会把 30ms 内的连奏同音误合并 | ✅ 修复（仅合并真实重叠） |
| 中 | 分轨整段驻留内存，长音频 OOM | ✅ 分块 overlap-add + memmap 累加（>4 分钟自动启用），峰值只驻留单块 |
| 中 | 拍号恒为 4/4、tempo 恒 120 | ✅ 新增 `time_signature` 字段与 `--tempo`，写入 MIDI meta |
| 中 | `duration_scale` 极值静默删音 | ✅ 限制 0.25–4.0，越界写入 errors |
| 中 | 多条编辑按位置覆盖、和弦窗口误伤邻近音 | ⚠️ 部分：按起点排序处理；和弦建议走“分轨+逐轨”流程（文档说明） |
| 低 | 纯 JSON 数组输入崩溃 | ✅ 修复 |
| 低 | 全局屏蔽 warnings/logging | ✅ 改为作用域上下文并恢复 |

## 第二轮（beats / practice / tab）

| 严重度 | 问题 | 状态 |
|---|---|---|
| 高 | 六线谱分栏硬编码 4/4 | ✅ `parse_tab` 输出逐小节拍号与 start/duration，渲染按真实小节 |
| 高 | 渲染时 string 越界无防护 | ✅ 钳制到 `[1, n_strings]`，越界计入 “skipped” 报告 |
| 中 | `--loop-beats` 末端外推超出音频被静默截短 | ✅ 钳位到音频时长并在 meta 记录 `loop_clamped` |
| 中 | `max_bars` 截断静默丢音符 | ✅ SVG 末尾标注 “+N bars not shown / N notes skipped” |
| 中 | tempo 倍频误判（慢歌被估成两倍） | ✅ onset 自相关一致性校正（60 BPM 实测不翻倍） |
| 中低 | 小节归属浮点漂移 | ✅ 小节线附近 `frac>0.995` 吸附到下一小节 |
| 低 | `--loop-beats 0`/负 `beat_start` 静默处理 | ✅ 显式 ValueError |
| 低 | `_esc` 不转义引号、画布高度估算失准 | ✅ `html.escape(quote=True)`；高度按各轨弦数精确累加 |

## 仍未处理（已知限制，欢迎 PR）

1. ~~分轨长音频的分块 overlap-add~~（已实现：`--chunk-seconds`，>4 分钟自动分块）；
2. ~~六线谱跨小节长音的连音线显示~~（已实现：跨小节延音线 class='tie'）；
3. 下拍仍是无监督启发式（低频重音相位），复杂编曲可能判错；无独立 downbeat 模型；
4. 和弦密集时的逐音重合成伪影（建议先分轨再逐轨编辑）；
5. 便携 exe 中 practice/notes 的重合成受 numba 冻结限制（源码安装无此问题）。
