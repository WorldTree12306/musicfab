# 发布检查清单

发布 `/发布到 GitHub` 前逐项确认。

## 1. 代码与测试

- [ ] `python -m pytest -q` 全绿（当前 37 项，Demucs 慢测约 45s）
- [ ] `python examples/demo.py` 端到端跑通（生成 `build/demo/`）
- [ ] `python -m musicfab.cli version` / `--help` 正常
- [ ] GUI 冒烟：`QT_QPA_PLATFORM=offscreen python -m musicfab.cli gui tests/fixtures/melody.wav`（无崩溃）

## 2. 许可证合规

- [ ] 仓库内**不含**任何商业软件代码/模型权重/反编译产物
- [ ] `docs/LICENSES.md` 与实际依赖一致（重点：PyMuPDF AGPL 可选、resvg MPL-2.0、PyGuitarPro LGPL、MuseScore GPL 仅子进程）
- [ ] Demucs 权重（CC-BY-4.0）首次运行自动下载，不随仓库分发
- [ ] 测试夹具（`.gp5`、`.wav`）未提交（`.gitignore` 覆盖），由脚本生成/下载

## 3. 产物

- [ ] `docs/` 配图有效：`gui.png`、`tab.png`、`score.png`
- [ ] `CHANGELOG.md` 更新
- [ ] 便携包（可选）：`scripts/build_portable.ps1` 生成 `dist/musicfab.exe`，验证 `version/probe/transcribe/notation/tab`

## 4. 发布

```bash
# 1) 本地检查
git status --short          # 应为空
git log --oneline | head    # 提交历史

# 2) 在 GitHub 新建空仓库（public，不要初始化 README/gitignore）
#    然后：
powershell -ExecutionPolicy Bypass -File scripts/publish_github.ps1 `
  -RepoUrl git@github.com:<user>/musicfab.git

# 3) CI 验证：Actions 应跑通 Windows/Linux × py3.11/3.12（含 transcribe 冒烟）
```

## 5. 发布后

- [ ] 打 tag：`git tag v0.1.0 && git push origin v0.1.0`
- [ ] Release notes 引用 `CHANGELOG.md`
- [ ] README 顶部截图与安装说明复核
