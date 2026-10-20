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
- [ ] 便携包（可选）：`powershell -ExecutionPolicy Bypass -File scripts/build_portable.ps1`
      - 产出 `dist/musicfab.exe` 与发布资产 **`dist/musicfab-<version>-win64.zip`**
        （zip 内含 `musicfab.exe` + `THIRD_PARTY_NOTICES.md`）；
      - 验证 zip 内两个文件齐全，exe 的 `version/probe/transcribe/notation/tab` 冒烟；
      - **许可证义务**：zip 捆绑了 PyMuPDF（AGPL-3.0）与 resvg-py（MPL-2.0）。
        Release notes 必须引用 zip 内的 `THIRD_PARTY_NOTICES.md`，并给出本仓库源码链接
        与 PyMuPDF / resvg 上游源码链接（AGPL 接收者可据此索取对应源码；MPL 满足文件级归属）。
        Demucs 权重（CC-BY-4.0）不随 zip 分发，Release notes 注明来源 URL。

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
