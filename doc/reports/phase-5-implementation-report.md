# 阶段 5 实施报告：发布就绪与双轨阶段 8 验收

## 结论

原实施方案阶段 5、双轨方案阶段 8 中可在本机完成的代码、测试、文档和发布自动化已经实现。
GCA 现在具备固定黄金仓库、完整双轨 E2E、三平台 CI/standalone 工作流、隔离 wheel 安装
验证、方法论与隐私边界、数据模型、安装升级说明，以及性能和安全审计材料。

正式 `0.1.0` 已完成远端验收：Windows/Linux/macOS 普通 CI、Gitleaks、三平台 standalone
构建和冒烟、wheel/sdist 保留、SHA-256 checksums 以及 GitHub Release 均已通过。正式版本
标记为 `0.1.0`，并由 `v0.1.0` tag 固定发布提交。

## TDD 记录

### RED

1. 新增黄金双轨生命周期测试，首先因 `tests.helpers.golden_repository` 不存在而收集失败。
2. 新增发布就绪测试，首先因 8 份必需文档、CI 构建/安装门禁、release workflow 和
   `gca.spec` 缺失而 3 项失败。

### GREEN

1. 实现真实 Git 黄金仓库构建器，覆盖：
   - Alice landed feature/test/docs；
   - Alice authored-only branch；
   - Bob 独立工作；
   - merge、cherry-pick duplicate、revert；
   - migration、docs-only、generated、binary、lockfile 和 release tag；
   - 空格和中文仓库路径。
2. 跑通 `init -> identities -> analyze -> assess person/all -> resume no-LLM/mock/outcomes ->
   runs -> report Markdown/JSON`。
3. 增加三平台普通 CI 的核心覆盖率、package build、隔离 wheel 生命周期和 Gitleaks 门禁。
4. 增加三平台 release workflow，验证 wheel、pipx 和 PyInstaller standalone 后上传产物。
5. 增加 wheel/standalone 的真实 `init/status/doctor/uninit` 安装后冒烟脚本。

### IMPROVE

1. 过滤 PyInstaller 的 `alembic.testing` 子模块，降低无关测试依赖和构建噪声。
2. 用发布就绪 E2E 固定文档与 CI 契约，避免后续删除关键门禁。
3. README、CHANGELOG 和 SECURITY 与发布边界同步。
4. 版本保持 dev 状态，直到远端三平台证据和制品审查完成。

## 文档交付物

- `doc/architecture/architecture.md`
- `doc/architecture/data-model.md`
- `doc/cli/cli-reference.md`
- `doc/guides/installation.md`
- `doc/guides/methodology.md`
- `doc/guides/privacy.md`
- `doc/testing/golden-dataset.md`
- `doc/releases/0.1.0.md`
- `doc/reports/performance-baseline.md`
- `doc/reports/security-privacy-audit.md`

## 本地质量门禁

参考环境：Windows 11、Python 3.13.2。

| 检查 | 结果 |
|---|---|
| pytest | 118 passed |
| 全项目覆盖率 | 90.83%，超过 80% 门槛 |
| Domain/Application 核心覆盖率 | 97%，超过 90% 门槛 |
| Ruff | 通过 |
| mypy strict | 97 个源码文件通过 |
| wheel/sdist | 构建成功 |
| 隔离 wheel 安装 | `gca --help/version` 与完整工作区生命周期通过 |
| Windows standalone | 25,136,188 bytes，完整工作区生命周期通过 |
| TOML/YAML | 解析通过 |
| `git diff --check` | 通过 |
| 大文件检查 | 无已跟踪文件超过 1 MiB |

pre-commit 在初始化 `ruff-pre-commit` 环境时无法连接 `github.com:443`，未能执行远端 hook。
已执行本地 Ruff、TOML/YAML 解析、差异检查和大文件等价检查。Gitleaks 已进入 CI，必须在远端
工作流中通过。

## 性能基线

约 15,000 commits、200+ refs 的匿名规模基准：首次索引小于 9 分钟，无变化同步小于 1 秒，
确定性项目评估小于 3 秒，确定性个人简历小于 2 秒。详细口径见
`doc/reports/performance-baseline.md`。

## 外部验收结果

- [x] Windows、Linux、macOS × Python 3.12/3.13 普通 CI 全部通过。
- [x] Tagged release workflow 的三平台 standalone 构建和冒烟全部通过。
- [x] Wheel、sdist、三平台 standalone 和 SHA-256 checksums 已发布并保留。
- [x] Gitleaks Git 历史扫描通过。
- [x] 版本已调整为 `0.1.0`，正式 `v0.1.0` tag 和 GitHub Release 已创建。

阶段 9 的结构复杂度与调用影响 Adapter 仍是已批准的 MVP 后续项，不阻塞上述发布验收。
