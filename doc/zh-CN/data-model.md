# GCA 数据模型

[中文文档索引](README.md) | [English](../architecture/data-model.md)

## 工作区

每个被分析仓库拥有独立的 `.gca/` 工作区：

```text
.gca/
  config.yml
  meta.json
  index.sqlite
  locks/
```

除人工身份确认、持久化 run、经过验证的外部输入和 LLM 审计/缓存外，数据库内容都可以从 Git
重新构建。执行数据库降级前，应备份 `index.sqlite`。

## Git 索引表

| 表 | 用途 |
|---|---|
| `repositories` | 仓库根目录、Git 目录和默认分支 |
| `refs` | 观测到的 branch/tag 及其活跃状态 |
| `commits` | 作者、时间、消息、patch/revert 元数据和 diff 汇总 |
| `commit_parents` | 有序父提交关系，包括 merge |
| `file_changes` | 每次提交的路径、变更类型、二进制标记和有效行数 |
| `commit_delivery` | `AUTHORED_ONLY`、`LANDED`、`RELEASED`、`REVERTED` 证据 |
| `persons` | 仓库范围内的规范 Person 身份 |
| `identity_aliases` | 精确邮箱、mailmap 和人工别名证据 |
| `identity_merge_events` | 可逆 Person 合并快照和 alias 移动记录 |

身份别名不会通过模糊名称自动合并。生成简历前，Person 必须经过显式确认。可逆合并会保留
inactive source Person 并记录其 target redirect，历史 run JSON 保持不变。

## 分析表

| 表 | 用途 |
|---|---|
| `analysis_runs` | 带版本的 `ANALYSIS`、`WORK_ASSESSMENT`、`WORK_ASSESSMENT_SERIES` 或 `RESUME` run 和结果 JSON |
| `contribution_items` | 分析 run 中稳定分组的工作事项 |
| `evidence` | claim 引用的 commit/path/metric 证据 |
| `capability_assessments` | 有 Evidence 支持的技术能力信号 |
| `llm_invocations` | 不含 API key 的 Provider/model/prompt/schema/status 审计 |
| `llm_cache` | 以 request hash 为键的已验证结构化 Provider 响应 |

工作评估和简历结果存储在 `analysis_runs.result_json`。即使后续规则版本变化，历史结果仍可以重放。

## 结构基线表

| 表 | 用途 |
|---|---|
| `structural_commit_facts` | 有效索引提交元数据和事实规则版本 |
| `structural_file_occurrences` | 按 commit 保存所有非零有效文件 occurrence |
| `structural_edge_occurrences` | 按 commit 保存所有非零规范文件对 occurrence |
| `structural_baselines` | 不可变的仓库/分支/范围/cutoff baseline 身份和状态 |
| `structural_file_counts` | 一个 baseline 的 lifetime/recent 文件计数 |
| `structural_edge_counts` | 一个 baseline 的 lifetime/recent 文件对计数 |
| `structural_materializations` | 带版本 hotspot/coupling JSON 和内容 hash |

Occurrence 是可从本地 Git 重建的观察数据，低于展示阈值时也会保留。只有 `COMPLETED` baseline
可消费；不完整状态只用于诊断。prune 只删除可重建 baseline 聚合，不删除 Git 事实或历史分析 run。

## 数据库迁移

- `0001_initial`：仓库和初始 run 状态。
- `0002_git_index`：ref、commit、file change、delivery 和 identity。
- `0003_analysis`：Contribution Item、Evidence 和能力结果。
- `0004_llm_audit`：调用审计和响应缓存。
- `0005_run_types`：显式 run type 和可选父 run。
- `0006_identity_merges`：可逆 Person 合并事件和 redirect。
- `0007_structural_baselines`：结构事实、occurrence、baseline 和 materialization。

打开工作区时会自动执行升级。降级属于维护操作，必须先备份数据库。集成测试覆盖
迁移与仓库生命周期路径。
