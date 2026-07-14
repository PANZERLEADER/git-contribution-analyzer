# 阶段 3 实施报告：确定性贡献分析与报告

## 结论

实施计划阶段 3 已完成。`gca` 现在可以在完全不使用 LLM 的情况下，对一个已确认 Person 生成可重放、可审计的贡献分析，并导出 Markdown/JSON 报告。

报告不会将 commit 数或代码行数转换成绩效等级，也不会输出单一员工总分。所有 Contribution Item 和 capability claim 都必须引用 Evidence ID，并明确记录证据缺口。

## 已实现命令

| 命令 | 行为 |
|---|---|
| `gca analyze [path] --person ... --no-llm` | 生成确定性贡献分析并保存 AnalysisRun |
| `gca runs list [path] --json` | 列出运行状态、参数、Git baseline 和规则版本 |
| `gca runs show <run-id> [path] --json` | 重放已完成运行的版本化 JSON |
| `gca report [path] --run ... --format markdown` | 从持久化运行重建 Markdown 报告 |
| `gca report [path] --run ... --format json` | 从持久化运行重建规范化 JSON 报告 |

`analyze` 支持以下过滤条件：

- `--since` / `--until`：包含边界的 ISO date/time。
- `--branch`：只保留目标 ref 可达 commit。
- `--release`：只保留指定 release tag 包含的 commit。
- `--scope`：按仓库路径前缀过滤。
- `--delivery`：`AUTHORED_ONLY`、`LANDED`、`RELEASED`、`REVERTED` 或 `DELIVERED`。

## 确定性规则

### Commit 分类

支持 `FEATURE`、`FIX`、`REFACTOR`、`PERFORMANCE`、`TEST`、`DOCUMENTATION`、`BUILD`、`CI`、`CHORE`、`STYLE`、`REVERT` 和 `OTHER`。

### Contribution Item 聚合

1. 相同 issue key 优先聚合，置信度 `HIGH`。
2. 相同 Conventional Commit scope 且相邻不超过 14 天，置信度 `MEDIUM`。
3. 相同顶层 module、commit type 和 14 天窗口作为保守回退，置信度 `LOW`。
4. 每个 item 保留全部 commit hashes、paths、modules、delivery statuses 和 Evidence IDs。

### Capability Rules

首批规则覆盖：

- `API_DESIGN`
- `TESTING`
- `DATABASE`
- `PERFORMANCE`
- `DELIVERY`
- `DOCUMENTATION`
- `CROSS_MODULE`

规则只在路径证据存在时触发。每条结论包含置信度、Evidence IDs 和固定缺口说明，不根据行数推导业务收益。

## AnalysisRun 与数据模型

Alembic migration：`0003_analysis`

新增或扩展的数据包括：

- `analysis_runs`：状态、Person、参数、baseline、规则版本、Provider、结果和失败信息。
- `contribution_items`：聚合键、标题、置信度、commit 和 Evidence 引用。
- `evidence`：类型、摘要、commit、path 和指标。
- `capability_assessments`：能力标签、置信度、理由、Evidence 和 gaps。

状态流已验证：`RUNNING -> COMPLETED` 和 `RUNNING -> FAILED`。失败运行保留错误信息并释放 workspace lock。

固定 Clock 和 ID 注入时，相同输入重复执行得到逐字一致的规范化 JSON；生产运行默认使用独立 UUID 和当前时间。

## JSON Schema

- `schemas/analysis/v1.json`：`gca analyze --json` 命令 envelope。
- `schemas/report/v1.json`：可重放的报告结构。

集成测试使用 JSON Schema 校验真实 CLI 输出，并验证所有 Contribution Item 和 capability Evidence 引用均存在。

## TDD 记录

### RED

- 领域模型不存在时，commit 分类/聚合/capability 测试导入失败。
- `analyze` 不存在时，CLI 返回用法错误 2，而非身份退出码 5。
- 固定 run ID 重放时，AnalysisRun 主键冲突。

### GREEN

- 实现不可变 Contribution、Evidence 和 CapabilityAssessment 模型。
- 实现纯确定性聚合和 capability rules。
- 实现 SQLite analysis store、`0003_analysis` 和完整 CLI 纵向流程。
- 实现幂等的显式 run ID 重放，默认 UUID 行为保持不变。

### IMPROVE

- 批量读取单个 Person 的 file changes，避免逐 commit SQL 查询。
- 使用规范化 JSON 持久化，key 排序稳定。
- 补充身份歧义、未确认身份、日期、branch、release、scope、delivery 和失败恢复测试。
- 增加 Markdown 免责声明和 Evidence Index。

## 质量门禁

| 检查 | 结果 |
|---|---|
| pytest | 30 passed |
| 覆盖率 | 88.59%，达到 80% 门槛 |
| Ruff | 通过 |
| mypy strict | 55 个源码文件通过 |
| wheel/sdist | 构建成功 |
| wheel 隔离安装 | 成功 |
| 隔离环境完整流程 | `init -> identities map -> analyze -> report` 成功 |
| 隔离环境 migration | `alembic_version=0003_analysis` |

## 生成式黄金仓库验证

验证仓库由 `tests/helpers/git_repo_builder.py` 在临时目录构造，只使用 `example.com` 保留域名和
虚构身份，不包含外部项目路径、真实姓名、邮箱或业务源码。

| 指标 | 结果 |
|---|---|
| 原生 Git 与报告 commit 计数 | 一致 |
| Contribution Items | 稳定且可重放 |
| Evidence | 每个 Item 均可追溯 |
| Capability assessments | 仅由规则和 Evidence 生成 |
| 缺失 Evidence 引用 | 0 |
| `LANDED` / `AUTHORED_ONLY` | fixture 预期一致 |
| Schema | valid |

fixture 覆盖线性提交、分支、tag、rename、binary、revert、cherry-pick、force-push 和身份映射。
报告包含 commit metadata、fixture path、计数和 Evidence 引用，不包含源码正文；重复运行的确定性
字段保持一致。

## 已知限制

- exact-email 会将同邮箱不同姓名归为同一 Person；共享邮箱必须人工识别，当前尚不支持在同邮箱下拆分 Person。
- 聚合是确定性启发式，不等同于 Jira/PR 的真实工作项关系。
- 顶层目录作为 module 口径，复杂 monorepo 后续需要可配置 module mapping。
- Git 只能证明代码活动和交付路径，不能证明业务收益、独立所有权、协作质量或线上效果。
- capability rules 是证据标签，不是能力等级或晋升结论。
- resume bullet 和语义总结将在阶段 4 由可替换 LLM Provider 增强，仍必须引用本阶段 Evidence。

## 下一阶段入口

阶段 4 将定义统一 `LlmProvider` SPI，接入 Mock、OpenAI-compatible、Anthropic 和 Ollama，实现结构化语义摘要、能力解释和简历候选描述。Provider 不可用时必须降级到本阶段的确定性报告，并记录完整调用审计。
