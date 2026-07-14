# 阶段 2 实施报告：Git 索引与身份归一化

## 结论

实施计划阶段 2 已完成。`gca` 现在可以对本地 Git 仓库执行首次索引、全量重建和增量同步，持久化 refs、commit 元数据、父关系、文件变更、身份别名和交付状态。所有 Git 事实均由 Native Git、PyDriller 和确定性规则生成，不依赖 LLM。

## 已实现命令

| 命令 | 行为 |
|---|---|
| `gca init [path]` | 创建 `.gca/`、迁移数据库并自动建立首次索引 |
| `gca index [path] --json` | 全量重建 Git 事实索引 |
| `gca sync [path] --json` | 保留既有历史，新增 commit 并刷新 refs 和交付状态 |
| `gca identities list [path] --json` | 列出 Person、别名、来源和确认状态 |
| `gca identities map [path] ... --json` | 将 Git 别名人工确认到规范 Person |
| `gca status [path] --json` | 输出索引 commit、identity、ref 和最近同步状态 |

## Git 事实与语义

- 索引本地分支、`origin` 远程分支和 tags，并保留 force-push 后不再可达的历史 commit。
- 持久化 author、committer、时间、tree、subject、body、父关系和 merge 标识。
- 通过 PyDriller读取 add、modify、delete、rename、copy、binary、insertions 和 deletions。
- 通过稳定 patch ID 识别 cherry-pick 或重复补丁。
- 通过目标分支可达性区分 `AUTHORED_ONLY` 与 `LANDED`。
- 通过 release tag 包含关系标记 `RELEASED`。
- 解析标准 Git revert message，建立 revert commit 与被撤销 commit 的关系并标记 `REVERTED`。
- exact email 自动归一为同一 Person；`.mailmap` 映射标记为已确认；模糊姓名不自动合并。

## TDD 记录

### RED

阶段 2 从真实临时 Git 仓库用例开始，覆盖未合入分支、release tag、rename、binary、cherry-pick、revert、merge 双父节点、force-push、`.mailmap`、人工映射和事务回滚。

性能改进阶段补充了两个命令数量测试：

1. 批量获取目标分支可达集合和首个 release tag，不允许逐 commit 调用 `merge-base --is-ancestor` 或 `tag --contains`。
2. lightweight 和 annotated tag 必须正确解析，完整 ref 快照只允许一次 `for-each-ref`，不允许逐 ref 调用 `rev-parse`。

### GREEN

实现 Native Git/PyDriller 读取、SQLite 仓储、Alembic `0002_git_index`、身份归一化和交付状态解析，使所有功能与集成测试通过。

### IMPROVE

- Git commit metadata 每 200 commits 批量读取。
- PyDriller 每 200 commits 批量遍历。
- stable patch ID 每 100 commits 批量计算。
- `.mailmap` 按 name/email 缓存。
- ref 快照由逐 ref `rev-parse` 改为单次 `for-each-ref`。
- 目标分支可达性由逐 commit `merge-base` 改为一次 `rev-list`。
- release tag 由逐 commit `tag --contains` 改为按 tag 批量建立包含映射。

## 质量门禁

| 检查 | 结果 |
|---|---|
| pytest | 21 passed |
| 覆盖率 | 86.21%，达到 80% 门槛 |
| Ruff | 通过 |
| mypy strict | 41 个源码文件通过 |
| wheel/sdist | 构建成功 |
| wheel 隔离安装 | 成功，自动安装 PyDriller |
| 打包内容 | 包含 `0002_git_index.py`、Native Git 和 PyDriller adapters |
| 隔离环境迁移 | `alembic_version=0002_git_index` |

## 匿名性能基准

参考环境：Windows、Python 3.13、NVMe 本地磁盘。基准来源不记录项目名、路径、人员身份或
提交内容，只保留无法用于人员归因的规模级数据。

| 指标 | 结果 |
|---|---|
| Git commits | 约 15,000 |
| Git refs | 200+ |
| Git objects | 约 300,000 |
| 首次 `gca init` | 小于 9 分钟 |
| 零增量 `gca sync` | 小于 1 秒 |
| SQLite 文件大小 | 小于 30 MiB |

首次索引低于计划的 15 分钟目标；零增量同步低于 30 秒目标。Release tag、身份映射和交付
状态语义由生成式 Git fixture 的集成测试覆盖。

`.gca/` 忽略行为在临时 fixture 中验证，不记录或修改任何外部业务仓库。

## 已知限制

- 当前 CLI 在长时间索引期间没有阶段进度输出，只在结束时输出结果。
- `config.yml` 已定义 refs patterns，但阶段 2 的 commit 枚举仍采用 `git rev-list --all`；自定义 refs 范围将在后续阶段补齐。
- 真实性能验证覆盖首次索引和零增量同步；新增 100 commits 的独立基准尚未执行。
- squash merge 无法仅依靠原 commit hash 还原来源，当前只能通过 patch/evidence 在后续分析阶段做保守关联。
- contribution clustering、能力评估、简历总结和报告属于阶段 3；可替换 LLM Provider 属于阶段 4。

## 下一阶段入口

阶段 3 将基于本阶段的确定性 Git 事实实现无 LLM 贡献分析、Contribution Item 聚合、Evidence、能力规则和 Markdown/JSON 报告，并保持所有结论可追溯到 commit、file change 和 delivery status。
