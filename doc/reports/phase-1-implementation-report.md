# 阶段 1 实施报告：工程骨架、CLI 和工作区

## 结论

实施计划阶段 1 的本地可验证范围已经完成。项目现在具备独立 Python 包、`gca`
CLI、仓库发现、`.gca/` 工作区、Alembic/SQLite 初始化、配置、锁、Git exclude、
状态检查、诊断和安全卸载能力。

## 已实现命令

| 命令 | 状态 |
|---|---|
| `gca --help` | 已实现并在 Windows 实测 |
| `gca --version` | 已实现并在 Windows 实测 |
| `gca init [path]` | 已实现，幂等初始化 |
| `gca status [path] --json` | 已实现，符合 v1 Schema |
| `gca doctor [path] --json` | 已实现，失败时返回稳定退出码 |
| `gca uninit [path] --yes` | 已实现，仅删除安全的 `.gca/` |

## 工作区产物

```text
.gca/
├── cache/
├── locks/workspace.lock
├── reports/
├── runs/
├── config.yml
├── identities.yml
├── index.sqlite
└── meta.json
```

`.gca/` 通过 `.git/info/exclude` 本地忽略，不自动修改仓库的受版本控制文件。

## 验证结果

| 检查 | 结果 |
|---|---|
| pytest | 11 passed |
| 覆盖率 | 85.09%，达到 80% 门禁 |
| Ruff | 通过 |
| mypy strict | 31 个源码文件通过 |
| wheel/sdist | 构建成功 |
| wheel 隔离安装 | 成功 |
| 隔离环境 `gca init/status` | 成功 |
| Windows CLI | 已实测 |
| Linux/macOS CLI | CI matrix 已配置，待首次远端运行 |

## TDD 记录

### RED

生产包不存在时，4 个测试模块在导入阶段失败。随后增加仓库登记和未初始化诊断测试，
分别验证 SQLite 空记录和错误退出码问题。

### GREEN

实现最小 CLI/Application/Adapter 闭环后，全部生命周期测试通过。

### IMPROVE

补充类型检查、格式检查、JSON Schema、Alembic migration、仓库记录 upsert、构建和
隔离 wheel 冒烟测试。

## 当前边界

- `indexStatus` 当前固定为 `not-indexed`，Git 历史索引属于阶段 2。
- 身份文件已经创建，但身份扫描和映射命令属于阶段 2。
- LLM 配置默认关闭，Provider SPI 属于阶段 4。
- 尚未执行 Git commit。

## 下一阶段入口

阶段 2 从 Native Git 安全执行器和 refs 快照开始，然后实现 commit/file change 全量索引、
增量同步、身份别名和目标分支可达性。阶段 2 的首个 RED 测试应使用真实临时 Git 仓库验证
线性提交、分支和 tag 的索引结果。
