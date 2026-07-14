# 提案：GCA 工作评估与简历生成双方向能力

## 1. 提案结论

GCA 应明确拆分为两个面向不同用户、不同风险等级和不同输出契约的产品方向：

1. `Work Assessment`：分析已经完成的工作量、工作难度和交付证据。
2. `Resume Generation`：基于已确认的个人贡献证据生成简历候选内容。

推荐采用“共享 Evidence Core + 两个独立 Application Use Case、CLI 命令、Schema 和
LLM Task”的方案。现有 `gca analyze` 继续作为确定性事实与 Contribution Item 的兼容入口，
新增 `gca assess` 和 `gca resume` 两个明确入口。

工作评估不得退化为 commit/代码行排名，也不自动生成员工绩效总分。简历生成不得读取团队
排名或把难度等级改写成未经证实的业务成果。两条流水线只共享可审计事实，不共享结论。

## 2. 背景与问题

### 2.1 当前产品状态

GCA 当前已经具备以下基础：

- Git refs、commit、文件变更、身份、交付状态和 Evidence 的本地索引。
- Contribution Item 聚类与技术/业务双维度确定性摘要。
- `PERSON` 和 `PROJECT` 两类报告。
- 可替换的 HTTP、Ollama、Codex CLI、Claude CLI 等 LLM Provider。
- Evidence ID 白名单、Prompt/Schema 版本、缓存和调用审计。

当前实现仍把总体总结、Contribution Item 总结、能力解释和简历 bullet 放在同一个
`semantic-v1` LLM Task 中，相关实现位于：

- `application/services/semantic_enhancement.py`
- `domain/models/semantic.py`
- `schemas/llm/semantic-v1.json`
- `prompts/v1/*.txt`

当前能力规则主要通过路径识别 API、测试、数据库、缓存、交付和文档信号，置信度主要由
支持 commit 数量决定。它可以证明“出现了某类工程活动”，但不能证明工作量大小或工作难度。

### 2.2 必须解决的问题

如果继续使用一个泛化的 `analyze` 报告承载所有用途，会产生以下混淆：

- 工作量事实、难度推断、能力标签和简历文案处于同一个 Schema，边界不清晰。
- 面向经理的评估输出和面向候选人的表达输出使用不同语气和证据强度，却由同一 Prompt 生成。
- 简历生成可能误用团队排名、提交数量或内部难度标签。
- 工作难度可能被 LLM 文案替代，而不是由可重复的确定性规则计算。
- 无法为两类功能分别定义默认过滤、身份要求、隐私策略和验收标准。

### 2.3 研究资料说明

当前仓库没有 `doc/research/` 目录。本提案以现有代码、原始提案、实施计划、JSON Schema、
阶段报告以及生成式黄金仓库的匿名验证结果为依据。

## 3. 产品能力边界

### 3.1 方向一：Work Assessment

目标用户：研发经理、项目负责人、工程师本人。

需要回答：

- 指定周期内完成了哪些独立工作事项。
- 哪些工作已经进入目标分支或发布版本。
- 工作规模如何分布，而不是简单提交了多少次。
- 每个工作事项的工程难度来自哪些可验证信号。
- 工作覆盖了哪些技术模块和业务领域。
- 哪些结论因身份、分支、PR、测试或线上数据缺失而不确定。

不得回答：

- 最终绩效等级、奖金、晋升或淘汰结论。
- 无法从证据证明的工时、工作态度、加班时长或个人独占成果。
- 跨仓库直接比较的绝对分数。

### 3.2 方向二：Resume Generation

目标用户：工程师本人、简历顾问、招聘流程中的候选人。

需要回答：

- 哪些已验证工作适合进入简历。
- 如何按目标岗位、语言和篇幅组织项目概述、职责和 bullet。
- 哪些技术能力有 Evidence 支持。
- 哪些表述只能使用 `contributed`，哪些可以使用 `implemented`。
- 哪些成果数据缺少可验证来源，不能写入简历。

不得回答：

- 团队内部人员排名或绩效评价。
- 由代码行数推导的效率提升。
- 未验证的收入、转化率、用户增长、性能百分比和主导权。
- 未确认身份的公开个人简历。

### 3.3 共享与隔离边界

```text
Git / refs / identity / delivery / diff / optional PR-issue-CI facts
                              |
                     Evidence Snapshot v1
                              |
              +---------------+---------------+
              |                               |
      Work Assessment Pipeline         Resume Generation Pipeline
      deterministic by default         narrative transformation
      difficulty/size rules            target-role/style selection
      optional LLM explanation         optional LLM generation
              |                               |
      WorkAssessmentReport v1            ResumeReport v1
```

允许共享：

- Repository、Person、Commit、DeliveryStatus、ContributionItem、Evidence。
- 技术模块、业务域、测试/文档/数据库等确定性信号。
- Provider SPI、缓存、调用审计和报告基础设施。

必须隔离：

- Use Case、Prompt、输出 Schema、默认过滤和人工复核状态。
- 工作规模/难度结论与简历文案。
- 团队项目报告与个人公开输出。

## 4. 功能需求

### 4.1 已完成工作口径

工作评估必须区分“投入过”和“已完成”：

| 状态 | 工作评估语义 | 默认计入已完成工作量 |
|---|---|---|
| `AUTHORED_ONLY` | 已开发，尚未进入目标分支 | 否，单独展示 |
| `LANDED` | 已进入目标分支 | 是 |
| `RELEASED` | 已进入目标发布版本 | 是，保留发布证据 |
| `REVERTED` | 曾交付但已撤销 | 否，计入返工/风险证据 |
| patch duplicate | cherry-pick/squash 等重复内容 | 去重后只计一次 |

默认报告应同时展示：

- `completedWork`：`LANDED` 和 `RELEASED` 的净 Contribution Item。
- `pendingWork`：仅 `AUTHORED_ONLY` 的 Contribution Item。
- `rework`：包含 revert、重复修复或反复变更信号的事项。
- `integrationWork`：Merge 和发布集成活动，不与功能开发重复计量。

目标分支配置错误时，不允许输出“完成率”结论，只输出显著警告。

### 4.2 工作量模型

工作量采用多维分布，不输出单一员工总分：

| 维度 | 建议指标 | 说明 |
|---|---|---|
| 完成事项 | completed item 数量及列表 | 以 Contribution Item 为主单位 |
| 规模分布 | `SMALL/MEDIUM/LARGE/XLARGE` | 按有效文件、有效 diff、方法变化等信号分桶 |
| 交付程度 | landed/released/pending/reverted | 与开发投入分开 |
| 覆盖广度 | module、layer、language 数量 | 不直接等于难度 |
| 工作类型 | feature/fix/refactor/test/docs/perf | 反映工作结构 |
| 工程配套 | test/docs/migration/config/rollback | 反映完整交付活动 |
| 时间范围 | first/last authored date | 不推导实际工时 |

规模分桶应基于版本化规则和仓库基线，至少排除：

- Merge commit 的重复 diff。
- generated/vendor/build/lockfile 等噪声。
- 相同 patch-id 的重复提交。
- 二进制文件的文本行数。

规模分桶只允许在同仓库、同规则版本下比较。跨语言和跨仓库比较必须显示不可比警告。

### 4.3 工作难度模型

难度必须按 Contribution Item 计算，再聚合为周期分布。建议使用四个等级：

- `ROUTINE`：局部、低风险、标准模式变更。
- `STANDARD`：单域内有一定逻辑或接口变化。
- `COMPLEX`：跨模块、复杂状态、兼容或数据变更。
- `HIGH_RISK`：资金、安全、并发、迁移、公共契约或高影响变更。

难度由独立维度合成：

| 难度维度 | 确定性信号示例 |
|---|---|
| 结构复杂度 | 方法数量、圈复杂度变化、控制流、AST 节点变化 |
| 影响范围 | 模块/分层数量、公共 API、调用方、fan-in/fan-out |
| 数据风险 | DDL、索引、迁移、事务、多表写入、数据修复 |
| 分布式风险 | Redis、MQ、并发、锁、幂等、重试、一致性 |
| 业务关键性 | 支付、钱包、权限、安全等项目配置的关键域 |
| 兼容要求 | API/Schema/配置格式变更、旧逻辑兼容、回滚路径 |
| 交付负担 | 测试、文档、脚本、发布配置、监控和告警 |

每个难度结论必须包含：

- `level`
- `dimensionSignals`
- `ruleVersion`
- `evidenceIds`
- `confidence`
- `gaps`

LLM 可以解释上述确定性结果，但不能提高/降低难度等级。

### 4.4 简历生成模型

简历方向只接受已确认 Person，默认只选择 `LANDED/RELEASED` 工作，可显式允许包含待交付工作。

输入建议包括：

- `--person`
- `--since/--until`
- `--target-role`
- `--language zh-CN|en-US`
- `--style concise|star|xyz`
- `--max-bullets`
- `--include-pending`
- `--verified-outcomes <file>`，后续阶段支持人工确认的外部成果。

输出建议包括：

- 项目概述候选。
- 技术栈与能力证据。
- 工作经历 bullet 候选。
- STAR/XYZ 候选。
- 每条公开文案对应的 Evidence 引用和 claim strength。
- 不应写入简历的证据缺口。

claim strength 建议分为：

- `CONTRIBUTED`：存在参与证据，无法证明完整责任。
- `IMPLEMENTED`：主要实现证据明确，但不声称独占所有权。
- `LED`：只有人工确认、PR/Issue ownership 或其他外部证据充分时允许。

### 4.5 外部成果输入

Git 无法证明收入、转化率、用户增长或线上性能结果。后续允许通过显式文件加入人工验证成果：

```yaml
outcomes:
  - id: OUT-001
    text: "接口 P95 延迟从 420ms 降至 180ms"
    source: "benchmark-report-2026-04.md"
    verifiedBy: "team-lead"
    verifiedAt: "2026-04-20"
```

未提供 `source` 和验证信息的数字不得进入简历输出。

## 5. 非功能需求

- 确定性：相同 Evidence Snapshot、配置和规则版本得到相同工作评估。
- 可审计：每个规模、难度和简历 claim 均可回溯 Evidence。
- 隐私：Person email、源码正文和内部排名默认不进入 LLM Prompt。
- 可替换：两条流水线继续通过统一 `LlmProvider` 使用任意 Provider。
- 可降级：`assess --no-llm` 完整可用；`resume --no-llm` 生成保守模板。
- 可维护：两条 Schema 和 Prompt 独立版本化。
- 性能：复用现有索引和 Snapshot，不重复遍历完整 Git 历史。
- 兼容性：现有 `analyze/report/runs` 命令和历史报告继续可读。

## 6. 方案一：单流水线 Profile 模式

### 6.1 概述

保留当前 `gca analyze` 流水线，通过 `--profile assessment|resume` 切换字段、Prompt 和渲染器。
继续使用一个 AnalysisRun 和一个顶层报告 Schema。

### 6.2 实现

1. 给 `analyze` 增加 `profile` 参数。
2. 在现有报告中增加可选 `workload`、`difficulty` 和 `resume` 字段。
3. `semantic-v1` 根据 profile 选择不同 Prompt 片段。
4. Markdown 根据存在的字段选择章节。

### 6.3 优点

- 改动最小，能较快产出界面。
- 复用当前 AnalysisRun、Schema 和 CLI。
- 不需要新增明显的领域边界。

### 6.4 缺点

- 两种产品语义继续耦合，可选字段和条件分支快速膨胀。
- 同一运行既像内部评估又像公开简历，权限和隐私边界模糊。
- Prompt、缓存 hash 和失败降级难以独立演进。
- 容易把工作难度、团队比较或内部警告带入简历。

复杂度：低
风险：高
工作量：小

## 7. 方案二：共享 Evidence Core + 双流水线

### 7.1 概述

索引、身份、交付判定、Contribution Item 和 Evidence 形成共享 Snapshot。在 Application 层新增
独立的 `AssessWork` 与 `GenerateResume` Use Case，各自拥有领域模型、Schema、Prompt 和报告。

### 7.2 实现

1. 将现有确定性结果固化为 `EvidenceSnapshot`，包含 baseline、filters、Person、Items 和 Evidence。
2. 新增 `WorkItemSizeAssessment`、`DifficultyAssessment` 和 `WorkAssessmentReport`。
3. 新增 `ResumeCandidate`、`ResumeClaim` 和 `ResumeReport`。
4. `analysis_runs` 增加 `run_type` 与可选 `parent_run_id`，或者引入等价的显式运行关联表。
5. 新增 `work-assessment/v1`、`resume/v1` 和独立 LLM Schema。
6. 新增 CLI 命令并保留 `gca analyze`：

```powershell
gca assess <repo> --person <identity> --since 2026-01-01 --no-llm
gca assess <repo> --all --since 2026-01-01 --no-llm
gca resume <repo> --person <confirmed-identity> --target-role "Senior Backend Engineer"
```

7. `gca report --run` 根据 `run_type` 选择对应 renderer。

### 7.3 优点

- 两个产品方向在 CLI、领域模型、Schema、Prompt 和权限上边界清晰。
- 共享最昂贵的 Git 索引和 Evidence，避免重复解析。
- 工作评估可以坚持确定性，简历方向可以充分使用可替换 LLM。
- 可以分别测试、版本化、缓存和回放。
- 符合当前 Domain/Application/Adapters/CLI 分层，不需要拆仓库。

### 7.4 缺点

- 需要增加运行类型、Schema 和迁移，初始改动高于方案一。
- 必须明确 Snapshot 的不可变性和父子运行关系。
- 工作难度规则需要黄金样例和跨语言适配器，不能一次完成。

复杂度：中
风险：中
工作量：中

## 8. 方案三：独立插件化产品

### 8.1 概述

将 GCA Core 作为事实引擎，Work Assessment 和 Resume Generation 分别实现为独立插件或 Python
包，通过版本化 Snapshot API 读取证据，可单独安装和发布。

### 8.2 实现

1. 抽取 `gca-core`，只保留索引、身份、交付、Contribution Item 和 Evidence。
2. 创建 `gca-work-assessment` 和 `gca-resume` 插件。
3. 建立插件 manifest、发现机制和跨包 Schema 兼容矩阵。
4. CLI 动态注册 `assess` 和 `resume` 命令。

### 8.3 优点

- 物理隔离最强，可以独立发布、授权和定制。
- 适合未来第三方能力包和企业版插件。
- 简历功能可以使用不同依赖而不影响核心工具。

### 8.4 缺点

- 当前项目规模下明显过度设计。
- 包版本、插件发现、安装和兼容测试成本高。
- Snapshot API 尚未稳定，过早拆包会放大演进成本。
- Windows 打包和单文件分发更复杂。

复杂度：高
风险：中到高
工作量：大

## 9. 方案比较

| 评估项 | 方案一：单流水线 Profile | 方案二：共享内核双流水线 | 方案三：独立插件 |
|---|---|---|---|
| 产品方向清晰度 | 低 | 高 | 最高 |
| 复用现有架构 | 高 | 高 | 中 |
| 初始开发成本 | 低 | 中 | 高 |
| 长期可维护性 | 低 | 高 | 中到高 |
| Schema 独立演进 | 差 | 好 | 最好 |
| LLM 权限隔离 | 差 | 好 | 最好 |
| 本地索引复用 | 好 | 好 | 依赖 API |
| Windows 分发复杂度 | 低 | 低 | 高 |
| 当前阶段匹配度 | 低 | 最高 | 低 |

## 10. 推荐方案

推荐方案二：共享 Evidence Core + 双流水线。

推荐理由：

- 用户面对的是两个明确任务，不是同一个报告的两种显示模式。
- 工作评估需要确定性和审计优先；简历需要表达质量和目标岗位适配优先。
- 当前 GCA 已经具备可复用的索引、Evidence、Provider 和运行审计，无需物理拆包。
- 独立 Use Case 和 Schema 可以阻止内部评估信息泄漏到简历。
- 保留 `gca analyze` 可控制兼容成本，并为后续插件化保留边界。

## 11. 推荐领域模型

### 11.1 共享 Snapshot

```text
EvidenceSnapshot
  id
  repositoryId
  baselineCommit
  filters
  personScope
  contributionItems
  evidence
  identityWarnings
  createdAt
  schemaVersion
```

### 11.2 工作评估

```text
WorkAssessmentReport
  snapshotId
  completedWork
  pendingWork
  rework
  integrationWork
  workloadSummary
  difficultyDistribution
  itemAssessments[]
  technicalSummary
  businessSummary
  warnings
  limitations

WorkItemAssessment
  contributionItemId
  completionStatus
  sizeBand
  difficultyLevel
  dimensionSignals[]
  confidence
  evidenceIds[]
  gaps[]
```

### 11.3 简历输出

```text
ResumeReport
  snapshotId
  person
  targetRole
  language
  projectSummaryCandidates[]
  experienceBullets[]
  skillEvidence[]
  omittedClaims[]
  warnings

ResumeClaim
  text
  claimStrength
  contributionItemIds[]
  evidenceIds[]
  verifiedOutcomeIds[]
  confidence
```

## 12. CLI 与兼容策略

### 12.1 推荐命令

```powershell
# 兼容：生成原始贡献事实和 Evidence
gca analyze <repo> --person <identity> --no-llm
gca analyze <repo> --all --no-llm

# 新方向一：工作评估
gca assess <repo> --person <identity> --since 2026-01-01 --no-llm
gca assess <repo> --all --since 2026-01-01 --no-llm

# 新方向二：简历生成
gca resume <repo> --person <confirmed-identity> `
  --target-role "Senior Backend Engineer" `
  --language zh-CN `
  --style star
```

### 12.2 兼容规则

- `gca analyze` 在 1.x 内不删除、不改变现有 JSON 语义。
- 旧的 `semantic.resumeBullets` 继续可读，但标记为 deprecated。
- 新版本不再向 `semantic-v1` 增加工作量或难度字段。
- `gca resume` 只读取新 `resume/v1`，不依赖旧字段。
- `gca runs list/show` 增加 `runType` 和 `parentRunId`。
- `gca report` 根据运行类型严格选择 Schema 和 renderer。

## 13. LLM 权限边界

| 能力 | Work Assessment | Resume Generation |
|---|---|---|
| 计算 Git 事实 | 禁止 | 禁止 |
| 决定完成状态 | 禁止 | 禁止 |
| 决定规模/难度等级 | 禁止 | 不适用 |
| 解释确定性结论 | 可选 | 可引用 |
| 选择简历候选事项 | 不适用 | 允许，必须引用 Evidence |
| 改写语气和结构 | 不适用 | 允许 |
| 生成未验证百分比 | 禁止 | 禁止 |
| 推断收入/用户结果 | 禁止 | 禁止 |
| 修改 Evidence | 禁止 | 禁止 |

两类任务分别使用 `assessment-explanation-v1` 和 `resume-v1` Prompt/Schema，不共享缓存 key。

## 14. 分阶段落地建议

### 阶段 A：产品边界和运行契约

- 新增 `runType`、`parentRunId` 和 Evidence Snapshot 契约。
- 新增 `assess`、`resume` 命令骨架和独立 Schema。
- 保持当前分析结果兼容。

### 阶段 B：工作量与难度 MVP

- 基于现有 Git、路径、Contribution Item 和交付状态实现规模分桶。
- 实现数据库、并发、缓存、API、测试、文档和跨模块风险信号。
- 输出难度等级、置信度、Evidence 和 gaps。
- 此阶段不依赖 LLM。

### 阶段 C：结构复杂度与影响分析

- 增加 `ComplexityAnalyzer` 和 `ImpactAnalyzer` Application Port。
- 首批使用支持 Java/Python/JavaScript 等语言的结构分析 Adapter。
- 增加方法复杂度、调用影响和公共契约变化信号。
- 无适配器的语言回退到路径/变更规则并降低置信度。

### 阶段 D：独立简历流水线

- 拆分 `resume-v1` Prompt、Pydantic 模型和 JSON Schema。
- 支持目标岗位、语言、风格、篇幅和保守模板降级。
- 增加 Evidence appendix 和 claim-strength 校验。

### 阶段 E：外部证据增强

- 接入 PR、Review、Issue、CI、发布和人工 verified outcomes。
- 提升完成状态、协作、质量和业务成果的置信度。
- 仍不自动输出最终绩效等级。

## 15. 验收标准

### 15.1 Work Assessment

- 相同 Snapshot 和规则版本重复运行得到完全相同的 JSON。
- `AUTHORED_ONLY` 默认不计入 completed workload。
- Merge、revert、generated files 和 patch duplicate 不造成重复工作量。
- 每个 size/difficulty 结论均包含 Evidence、规则版本、置信度和 gaps。
- 一个小 diff 的高风险迁移可以被判为高难度；大量简单文档修改不能仅因行数被判高难度。
- 项目报告允许 `--all`，未确认身份必须独立显示警告。
- 报告不生成单一员工总分，不把 commit/代码行直接转换为绩效。

### 15.2 Resume Generation

- 只允许为已确认 Person 生成个人简历。
- 每条 bullet 至少引用一个 Contribution Item 和一个 Evidence ID。
- 无 verified outcome 时拒绝百分比、收入、用户增长和线上效果表述。
- `LED` 必须存在显式 ownership/人工验证证据。
- `--no-llm` 能生成结构合法的保守模板。
- 简历报告不包含团队排名、其他人员邮箱和内部难度比较。

### 15.3 兼容与质量

- 现有 `analyze --person/--all`、历史 run 和 PERSON/PROJECT 报告继续可用。
- 新旧 Schema 都有 JSON Schema 验证和黄金样例。
- Domain/Application 测试覆盖率不低于 90%，全项目不低于 80%。
- Windows、Linux、macOS 均验证新 CLI 帮助和最小生命周期。
- Provider 失败时保留确定性工作评估；简历按配置降级或明确失败。

## 16. 风险与缓解

| 风险 | 缓解措施 |
|---|---|
| 工作量被当成员工价值 | 使用多维分布，不输出单一总分，强制限制说明 |
| 难度规则偏向大 diff | 将规模与难度分离，引入风险和影响维度 |
| 跨语言指标不可比 | 仓库内基线、Adapter 置信度和不可比警告 |
| 目标分支错误导致“未完成” | 输出目标分支和 baseline，异常比例触发警告 |
| 身份错误导致归属错误 | 个人评估/简历要求 confirmed Person |
| LLM 夸大简历 | Evidence 白名单、claim strength、数字和 ownership 校验 |
| 两条流水线复制逻辑 | 共享不可变 Evidence Snapshot 和公共验证器 |
| Schema 数量增加 | 独立版本、迁移测试和 runType 分派 |

## 17. 决策请求与下一步

本提案请求确认以下决策：

1. 确认 GCA 的两个正式产品方向名称与边界。
2. 确认采用方案二：共享 Evidence Core + 双流水线。
3. 确认“已完成”默认只包含 `LANDED/RELEASED`。
4. 确认工作量使用规模分布，不生成单一员工总分。
5. 确认难度等级由确定性规则决定，LLM 只做解释。
6. 确认简历只面向已确认 Person，并使用独立 Prompt/Schema。

批准后使用 `make-plan` 生成详细实施计划，优先完成阶段 A 和阶段 B，再进入简历流水线。
