# GCA 工作评估与简历生成双轨实施方案

## 1. 基本信息

| 项目 | 内容 |
|---|---|
| 功能名称 | Work Assessment 与 Resume Generation 双轨能力 |
| 项目 | Git Contribution Analyzer（GCA） |
| 影响模块 | Domain、Application、SQLite Adapter、LLM Adapter、Reporting、CLI、Schema、文档 |
| 技术栈 | Python 3.12+、Typer、Pydantic 2、SQLAlchemy 2、Alembic、SQLite、pytest、jsonschema |
| 相关提案 | `doc/proposals/work-assessment-and-resume-dual-track-proposals.md`（推荐方案二） |
| 推荐架构 | 共享 Evidence Core + 两条独立流水线 |
| 作者 | Codex |
| 日期 | 2026-07-13 |
| 计划状态 | 待实施 |

本方案是后续 `implement` 工作流的执行依据。实施必须按阶段采用
RED -> GREEN -> IMPROVE，不允许先扩展 LLM 文案再补确定性事实。

## 2. 背景与当前状态

### 2.1 当前能力

GCA 已具备以下可复用基础：

- Git refs、commit、file change、patch-id、revert 和 delivery status 的本地索引。
- Person/IdentityAlias 归一化及 confirmed identity 校验。
- Contribution Item 聚类、Evidence 生成、CapabilityAssessment 和技术/业务双维度摘要。
- `gca analyze --person|--all`、`runs list/show`、`report` CLI。
- PERSON/PROJECT 确定性报告及 JSON Schema。
- HTTP、Ollama、Codex CLI、Claude CLI 等可替换 `LlmProvider`。
- LLM Prompt/Schema 版本、Evidence ID 白名单、缓存和调用审计。

### 2.2 当前实现边界

当前关键实现如下：

| 关注点 | 当前文件 | 现状 |
|---|---|---|
| CLI | `src/git_contribution_analyzer/cli/app.py` | 只有 `analyze`，没有 `assess`、`resume` |
| 个人分析 | `application/use_cases/analyze_contributions.py` | 在一个用例内完成事实、规则、LLM 和持久化 |
| 项目分析 | `application/use_cases/analyze_project.py` | 生成 PROJECT 报告 |
| 语义增强 | `application/services/semantic_enhancement.py` | 一个 `semantic-v1` 同时生成摘要、能力解释和 resume bullets |
| 语义模型 | `domain/models/semantic.py` | `SemanticEnhancement` 混合多个产品目的 |
| 能力模型 | `domain/models/assessment.py` | 仅有 `CapabilityAssessment`，不是工作评估模型 |
| 贡献事实 | `domain/models/contribution.py` | 已有 ContributionItem、Evidence，但没有 Snapshot |
| SQLite run | `adapters/storage/sqlite/models.py` | `analysis_runs` 没有 `run_type`、`parent_run_id` |
| 报告渲染 | `adapters/reporting/markdown.py` | 只识别 PERSON/PROJECT |
| LLM Schema | `schemas/llm/semantic-v1.json` | `resumeBullets` 与其他语义字段耦合 |

仓库没有 `doc/research/`。本计划以已批准提案、当前源码、SQLite 迁移、Schema 和测试为事实依据。

### 2.3 问题陈述

现有 `analyze` 只能证明“发生了哪些贡献活动”，不能可靠回答以下两个独立问题：

1. 管理和复盘场景：已完成哪些工作，工作规模和工程难度如何，证据及缺口是什么。
2. 个人表达场景：哪些已确认贡献可以转成简历内容，允许使用何种责任措辞，哪些成果不能声称。

如果继续把两类结论放入 `semantic-v1`，内部评估、公开表达、身份约束和 LLM 权限会继续混淆。

## 3. 目标与非目标

### 3.1 目标

1. 建立不可变、可指纹化的 `EvidenceSnapshot`，让 `analyze`、`assess` 和 `resume` 复用同一事实构建逻辑。
2. 新增 `gca assess --person|--all`，输出已完成工作、规模分布、难度分布、技术总结和业务总结。
3. 新增 `gca resume --person`，输出有 Evidence 引用和 claim strength 的简历候选内容。
4. 规模、完成状态、难度和 claim 上限由确定性规则决定；LLM 只能解释或改写。
5. 为两条流水线建立独立 Domain 模型、Use Case、Prompt、Schema、Renderer 和运行审计。
6. 保留 `gca analyze` 及历史 PERSON/PROJECT 报告的读取和渲染能力。
7. Provider 失败时保留确定性工作评估；`resume --no-llm` 仍生成合法、保守的模板。

### 3.2 非目标

- 不生成员工总分、绩效等级、奖金、晋升或淘汰建议。
- 不根据 commit 数量、代码行数或在线时长推导工时、效率和工作态度。
- 不在 v1 中做跨仓库、跨语言的绝对工作量排名。
- 不允许 LLM 修改完成状态、规模等级、难度等级、Evidence 或 claim strength 上限。
- 不从 Git 自动推断收入、转化率、用户增长、线上性能百分比或独占所有权。
- 不在本阶段拆分 `gca-core`、`gca-assessment`、`gca-resume` 为独立 Python 包。
- 不让阶段 9 的 AST/调用图 Adapter 阻塞 MVP。

## 4. 功能需求与验收标准

### FR-01：共享 Evidence Snapshot

系统必须从当前索引、过滤条件和身份范围构建一个不可变 `EvidenceSnapshot`。

验收标准：

- Snapshot 包含 repository、baseline、filters、person scope、Contribution Items、Evidence、identity warnings 和版本。
- Snapshot ID 由规范化 JSON 的 SHA-256 生成，排除 `createdAt` 等非确定字段。
- 相同索引基线、过滤条件、身份范围和规则版本得到相同 Snapshot ID。
- `assess` 的确定性计算与可选 LLM 解释读取同一个 Snapshot 对象，不重新读取 Git 历史。

### FR-02：运行类型与关联

`analysis_runs` 必须支持 `ANALYSIS`、`WORK_ASSESSMENT`、`RESUME` 三种运行类型和可选父运行。

验收标准：

- 历史行迁移后全部为 `ANALYSIS`。
- `runs list/show` 返回 `runType` 和 `parentRunId`。
- `report --run` 根据 run type 选择严格匹配的 renderer。
- 父运行只能来自同一 repository；不存在或未完成的父运行被拒绝。

### FR-03：完成工作分类

工作评估按 Contribution Item 区分：

- `completedWork`：净状态为 `LANDED` 或 `RELEASED`。
- `pendingWork`：只有 `AUTHORED_ONLY`。
- `rework`：存在 `REVERTED`、重复修复或反复变更证据。
- `integrationWork`：Merge、release integration 等活动，和功能开发分开。

验收标准：

- `AUTHORED_ONLY` 默认不进入 completed workload。
- `REVERTED` 不进入 completed workload，但保留返工和风险证据。
- 相同 patch-id、merge diff、generated/vendor/build/lockfile 和 binary line count 不重复计量。
- 目标分支异常时输出显著警告，不生成完成率。

### FR-04：工作规模评估

每个 eligible Contribution Item 必须产生 `WorkItemSizeAssessment`，等级为
`SMALL`、`MEDIUM`、`LARGE`、`XLARGE`。

验收标准：

- 输出 effective files、effective churn、module span、基线样本和 rule version。
- 规模是周期内的分布和事项列表，不汇总为员工分数。
- 规则排除 merge 重复、patch duplicate、binary 行数和配置的 noise paths。
- 同 Snapshot、规则版本和配置重复计算结果完全一致。

### FR-05：工作难度评估

每个 eligible Contribution Item 必须产生 `DifficultyAssessment`，等级为
`ROUTINE`、`STANDARD`、`COMPLEX`、`HIGH_RISK`。

验收标准：

- 输出结构、影响、数据、分布式、业务关键性、兼容和交付负担维度信号。
- 每个等级包含 `ruleVersion`、`evidenceIds`、`confidence` 和 `gaps`。
- 小 diff 的高风险数据库迁移可判为 `HIGH_RISK`。
- 大量简单文档不能只因行数被判为高难度。
- LLM 返回不同等级时必须校验失败，不能覆盖确定性等级。

### FR-06：`gca assess`

新增个人和项目两种工作评估入口。

验收标准：

- 支持 `--person` 与 `--all`，二者互斥且至少提供一个。
- 支持复用 `analyze` 的 since/until/branch/release/scope/delivery 过滤。
- `--no-llm` 是完整功能路径，不影响任何确定性字段。
- Provider 失败且允许降级时 run 为 `PARTIAL`，确定性结果完整保留。
- `--all` 不输出人员排名、单一分数或其他人的简历内容。

### FR-07：独立 Resume 模型与保守模板

简历生成只接受 confirmed Person，并基于 Snapshot 生成独立 `ResumeReport`。

验收标准：

- 每个 `ResumeClaim` 至少引用一个 Contribution Item 和一个 Evidence ID。
- 默认只使用 `LANDED/RELEASED`；`--include-pending` 才能加入待交付内容并显式标记。
- `--no-llm` 可生成符合 Schema 的保守模板。
- 输出不含团队排名、其他人员邮箱和内部难度比较。

### FR-08：Claim strength

claim strength 固定为 `CONTRIBUTED`、`IMPLEMENTED`、`LED`。

验收标准：

- Git 证据存在但责任边界不完整时上限为 `CONTRIBUTED`。
- confirmed Person、有主要实现 Evidence、无归属冲突且工作已交付时可为 `IMPLEMENTED`。
- `LED` 必须有显式 ownership 或人工验证证据；仅 Git 提交永远不能自动得到 `LED`。
- LLM 只能在确定性上限内选择更保守的措辞。

### FR-09：Verified outcomes

`gca resume` 可选读取人工验证的 YAML 成果文件。

验收标准：

- 每条 outcome 必须有 id、text、source、verifiedBy、verifiedAt。
- 数字、百分比、收入、用户增长和线上效果只有引用 verified outcome 时才能进入 claim。
- outcome 不修改 Git Evidence，只作为独立外部证据引用。
- 无验证来源的数字型 claim 被拒绝，而不是静默删除后继续。

### FR-10：独立 LLM Task

工作评估解释和简历生成分别使用 `assessment-explanation-v1` 与 `resume-v1`。

验收标准：

- 两类任务拥有独立 Prompt、Pydantic 模型、JSON Schema 和 cache key。
- Prompt 不包含 Person email、源码正文、其他人员详情或团队排名。
- 所有输出经过 Evidence 白名单、Item 白名单、数字和 ownership 校验。
- 所有 Provider 继续走现有 `LlmProvider`、cache 和 invocation audit。

### FR-11：兼容读取

验收标准：

- 旧 `analyze --person/--all` 输出语义不变。
- 历史 PERSON/PROJECT run 可以继续 `runs show` 和 `report`。
- `semantic.resumeBullets` 在 Schema 和文档中标为 deprecated，但 1.x 内继续可读。
- 新实现不再向 `semantic-v1` 增加工作量或难度字段。

### FR-12：双维度总结

工作评估和简历报告都必须保留技术维度与业务维度，但用途不同。

验收标准：

- Work Assessment 的技术/业务总结只描述 Evidence 覆盖和规则结论。
- Resume 的技术/业务内容只从已选择的 ResumeClaim 派生。
- LLM 不能借业务总结生成未验证业务结果。

## 5. 非功能需求

| 编号 | 要求 | 指标 |
|---|---|---|
| NFR-01 | 确定性 | 固定 clock/run ID 后，相同 Snapshot 与规则版本输出逐字一致 |
| NFR-02 | 可审计 | 100% size、difficulty、resume claim 可回溯 Item 和 Evidence |
| NFR-03 | 隐私 | LLM Prompt 不含 email、源码正文、其他人员明细和内部排名 |
| NFR-04 | 可替换 | 新任务通过现有 `LlmProvider`，不依赖具体厂商 API |
| NFR-05 | 可降级 | assess LLM 失败保留完整确定性结果；resume 支持 `--no-llm` |
| NFR-06 | 性能 | 单次命令只从 SQLite 构建一次 Snapshot，不重复扫描完整 Git 历史 |
| NFR-07 | 兼容 | 旧 CLI、run、PERSON/PROJECT JSON 和 Markdown 继续可用 |
| NFR-08 | 测试 | Domain/Application 新代码覆盖率 >= 90%，全项目 >= 80% |
| NFR-09 | 跨平台 | Windows、Linux、macOS 的 help、最小生命周期和路径处理通过 CI |
| NFR-10 | 安全 | 不执行仓库脚本，不在配置、Prompt、日志中写入凭证 |

## 6. 已确定的设计决策

1. 保留单仓库、单 Python 包，不做插件化拆包。
2. `EvidenceSnapshot` 是内存中的不可变领域值对象；新报告持久化其 canonical metadata、Item 和 Evidence，v1 不新增 snapshot 表。
3. `snapshotId` 是内容指纹，不使用随机 UUID；`createdAt` 不参与指纹。
4. `analysis_runs.run_type` 是公开运行分类；`parent_run_id` 是同库逻辑关联，MVP 由 Application 校验，不建立 SQLite 自关联外键。
5. 新命令直接从当前索引构建 Snapshot；从既有 run 回放时才设置 `parent_run_id`。首版不增加隐式“自动复用 latest”行为。
6. 当前 `domain/models/assessment.py` 保留 `CapabilityAssessment`；新的工作评估模型放在 `work_assessment.py`，避免概念冲突。
7. 工作量只输出事项和分布，不输出人员总分、完成率或跨人排名。
8. 难度等级由 `difficulty-rules-v1` 决定，LLM 只生成解释文本。
9. Resume 只允许 confirmed Person；项目 `--all` 不支持 resume。
10. `LED` 只由 verified ownership/outcome 等外部证据解锁。
11. 旧 `semantic.resumeBullets` 保留兼容但不再被 `gca resume` 读取。
12. 结构复杂度和调用影响 Adapter 放在阶段 9，MVP 缺失时通过 `gaps` 降低置信度。

本计划没有待实施前再决定的开放问题。

## 7. 总体架构

```text
CLI
  |-- gca analyze -----------------------------+
  |-- gca assess --person|--all ---------------+----> BuildEvidenceSnapshot
  `-- gca resume --person ---------------------+       (once per command)
                                                         |
                                      +------------------+------------------+
                                      |                                     |
                              AssessWork Use Case                    GenerateResume Use Case
                                      |                                     |
                         workload_rules + difficulty_rules          resume_claim_rules
                                      |                                     |
                         optional assessment explanation             deterministic template
                                      |                              or optional resume-v1 LLM
                                      |                                     |
                         WorkAssessmentReport v1                 ResumeReport v1
                                      |                                     |
                                      +---------- Run Store ----------------+
                                                    |
                              analysis_runs + details + llm_invocations/cache
```

### 7.1 依赖方向

```text
Domain <- Application <- Adapters <- CLI
```

- Domain 不导入 Typer、SQLAlchemy、具体 Provider 或文件系统 Adapter。
- Application 接收 Snapshot、Provider 和结构化 verified outcomes。
- Adapter 负责 SQLite、YAML、Markdown 和具体 LLM。
- CLI 只负责参数校验、配置装配、调用 Use Case 和输出 envelope。

### 7.2 Snapshot 构建流程

1. 解析 repository 和 `.gca/config.yml`。
2. 验证索引、baseline 和 person scope。
3. 读取过滤后的 commit facts。
4. 对 patch duplicate、merge、revert、noise path 和 binary 进行规范化。
5. 聚类 Contribution Item，构建 Evidence 和现有 capability/双维度摘要事实。
6. 以排序后的 canonical JSON 计算 `snapshotId`。
7. 将同一个 Snapshot 对象传给确定性规则和可选 LLM task builder。

## 8. 领域模型设计

### 8.1 `RunType`

位置：`domain/models/run.py`

```python
class RunType(StrEnum):
    ANALYSIS = "ANALYSIS"
    WORK_ASSESSMENT = "WORK_ASSESSMENT"
    RESUME = "RESUME"
```

如果不希望新增单独文件，可将其放入 `domain/models/analysis.py`；实施时固定使用独立
`run.py`，避免过滤条件和运行状态继续耦合。

### 8.2 `EvidenceSnapshot`

位置：`domain/models/snapshot.py`

```text
EvidenceSnapshot
  schema_version: "snapshot-v1"
  id: sha256 canonical payload
  repository_id: str
  repository_root: str
  baseline_commit: str | None
  filters: AnalysisFilters
  scope_type: PERSON | PROJECT
  persons: tuple[SnapshotPerson, ...]
  contribution_items: tuple[SnapshotContributionItem, ...]
  evidence: tuple[Evidence, ...]
  identity_warnings: tuple[str, ...]
  rule_versions: SnapshotRuleVersions
  created_at: datetime
```

规范化要求：

- persons 按 person id 排序。
- Contribution Items 按 person id、first authored time、item id 排序。
- Evidence 按 evidence id 排序。
- set/map 输出前排序。
- `created_at`、run id、Provider 信息不参与 Snapshot 指纹。
- Snapshot 不暴露 Person email 给 LLM context；email 只保留在本地报告身份区。

### 8.3 工作评估模型

位置：`domain/models/work_assessment.py`

```text
SizeBand = SMALL | MEDIUM | LARGE | XLARGE
DifficultyLevel = ROUTINE | STANDARD | COMPLEX | HIGH_RISK
CompletionBucket = COMPLETED | PENDING | REWORK | INTEGRATION

WorkItemSizeAssessment
  band
  effective_files
  effective_churn
  module_span
  baseline_sample_size
  baseline_mode: REPOSITORY | STATIC_FALLBACK
  rule_version
  evidence_ids

DimensionSignal
  dimension
  code
  severity
  description
  evidence_ids

DifficultyAssessment
  level
  dimension_signals
  rule_version
  evidence_ids
  confidence
  gaps

WorkItemAssessment
  contribution_item_id
  person_id
  completion_bucket
  delivery_statuses
  work_type
  size
  difficulty
  engineering_support
  evidence_ids
  warnings

WorkAssessmentReport
  schema_version
  report_type: WORK_ASSESSMENT
  scope_type: PERSON | PROJECT
  run
  snapshot
  subjects
  workload_summary
  difficulty_distribution
  technical_summary
  business_summary
  explanation | null
  identity_warnings
  warnings
  limitations
```

`subjects` 对 PERSON scope 只有一个元素；PROJECT scope 每个 Person 一个元素。项目顶层只做总量分布，
不产生排序、名次或“高于平均”等比较措辞。

### 8.4 Resume 模型

位置：`domain/models/resume.py`

```text
ClaimStrength = CONTRIBUTED | IMPLEMENTED | LED
ResumeStyle = CONCISE | STAR | XYZ
ResumeLanguage = zh-CN | en-US

VerifiedOutcome
  id
  text
  source
  verified_by
  verified_at

ResumeClaim
  text
  claim_strength
  contribution_item_ids
  evidence_ids
  verified_outcome_ids
  confidence
  pending

SkillEvidence
  skill
  evidence_ids
  contribution_item_ids

OmittedClaim
  candidate
  reason_code
  missing_evidence

ResumeReport
  schema_version
  report_type: RESUME
  run
  snapshot
  person
  target_role
  language
  style
  project_summary_candidates
  experience_bullets
  skill_evidence
  omitted_claims
  technical_summary
  business_summary
  warnings
  limitations
```

所有 Pydantic 输出模型使用 `extra="forbid"` 和 alias，所有 dataclass 使用 `frozen=True, slots=True`。

## 9. JSON 契约

### 9.1 Work Assessment 核心片段

```json
{
  "schemaVersion": "1.0",
  "reportType": "WORK_ASSESSMENT",
  "scopeType": "PERSON",
  "run": {
    "id": "uuid",
    "runType": "WORK_ASSESSMENT",
    "parentRunId": null,
    "status": "COMPLETED",
    "ruleVersion": "work-assessment-v1",
    "providerId": "none"
  },
  "snapshot": {
    "id": "sha256",
    "schemaVersion": "snapshot-v1",
    "baselineCommit": "commit-hash",
    "filters": {}
  },
  "subjects": [],
  "workloadSummary": {
    "completedItems": 0,
    "pendingItems": 0,
    "reworkItems": 0,
    "integrationItems": 0,
    "sizeDistribution": {
      "SMALL": 0,
      "MEDIUM": 0,
      "LARGE": 0,
      "XLARGE": 0
    }
  },
  "difficultyDistribution": {
    "ROUTINE": 0,
    "STANDARD": 0,
    "COMPLEX": 0,
    "HIGH_RISK": 0
  },
  "technicalSummary": {},
  "businessSummary": {},
  "explanation": null,
  "warnings": [],
  "limitations": []
}
```

### 9.2 Resume claim 核心片段

```json
{
  "text": "实现并交付用户接口及配套测试",
  "claimStrength": "IMPLEMENTED",
  "contributionItemIds": ["CI-001"],
  "evidenceIds": ["EV-001", "EV-002"],
  "verifiedOutcomeIds": [],
  "confidence": "HIGH",
  "pending": false
}
```

### 9.3 新增 Schema

| 文件 | 用途 |
|---|---|
| `schemas/work-assessment/v1.json` | WorkAssessmentReport |
| `schemas/resume/v1.json` | ResumeReport |
| `schemas/commands/assess-v1.json` | `gca assess --json` envelope |
| `schemas/commands/resume-v1.json` | `gca resume --json` envelope |
| `schemas/llm/assessment-explanation-v1.json` | 可选工作评估解释 |
| `schemas/llm/resume-v1.json` | LLM 简历候选输出 |

Schema 使用 Draft 2020-12，所有正式对象默认 `additionalProperties: false`。

## 10. 确定性规则设计

### 10.1 Eligible change 过滤

以下变更不进入 effective size：

- merge commit 的重复 diff。
- `is_excluded=true` 的 file change。
- generated、vendor、build output、lockfile 和用户配置的 noise path。
- binary 文件的 insertions/deletions；binary 文件数量仍可作为交付信号。
- 与已计量 commit 相同 patch-id 的重复提交。
- reverted item 的原始工作不进入 completed workload。

过滤器先于 size 和 difficulty 执行，并将排除原因写入可审计 metrics。

### 10.2 Size baseline 与分桶

规则版本：`workload-rules-v1`。

1. 在相同 repository、filters 时间窗口和规则版本内，使用所有 eligible completed items 构建基线。
2. 样本数 >= 20 时使用 repository baseline；否则使用 static fallback。
3. 指标为 effective churn、effective files 和 module span；commit count 只展示，不参与 band。
4. repository baseline 使用 P50/P75/P90，将每个指标映射到 SMALL/MEDIUM/LARGE/XLARGE，最终取最高 band。
5. 增加绝对下限，防止小仓库样本把微小变更放大：

| Band | 至少满足一个绝对条件 |
|---|---|
| MEDIUM | churn > 80，或 files > 3，或 modules > 1 |
| LARGE | churn > 300，或 files > 10，或 modules > 2 |
| XLARGE | churn > 1000，或 files > 30，或 modules > 4 |

static fallback 直接使用上述阈值。规模只代表有效变更范围，不代表难度或价值。

### 10.3 Difficulty 规则

规则版本：`difficulty-rules-v1`。难度不使用代码行数作为升级条件。

| 维度 | 首批信号 |
|---|---|
| 结构复杂度 | 多层逻辑路径、方法/控制流信号；无 AST 时记录 gap |
| 影响范围 | 多 module、多 layer、公共 API/Schema/config contract |
| 数据风险 | DDL、migration、index、transaction、多表写、数据修复 |
| 分布式风险 | Redis、MQ、lock、retry、idempotency、concurrency、consistency |
| 业务关键性 | 配置的 payment/wallet/auth/security 等 critical paths |
| 兼容要求 | 兼容旧字段、版本迁移、rollback、public contract change |
| 交付负担 | test、docs、migration、config、monitoring、release script |

等级合成使用优先规则，不对员工输出内部总分：

1. 命中安全、资金、破坏性迁移、并发一致性、公共契约破坏等 critical signal，判 `HIGH_RISK`。
2. 命中至少两个 substantial dimensions，或“跨模块 + 数据/兼容”组合，判 `COMPLEX`。
3. 命中一个 substantial dimension，或单域内有明确逻辑/API 变化，判 `STANDARD`。
4. 仅局部标准模式、测试、文档或配置微调，判 `ROUTINE`。
5. 无 AST/调用图 Adapter 时不升级等级，只增加 gap 并降低 confidence。

### 10.4 Completion bucket

对一个 Contribution Item 的所有 delivery statuses 使用以下优先级：

```text
REVERTED -> REWORK
全部 AUTHORED_ONLY -> PENDING
含 RELEASED/LANDED -> COMPLETED
纯 merge/release integration -> INTEGRATION
```

包含已交付和后续 revert 时归入 REWORK，并保留曾交付事实，但不计入 completed count。

### 10.5 Claim strength 上限

规则版本：`resume-claim-rules-v1`。

- 默认上限：`CONTRIBUTED`。
- 满足 confirmed Person、completed item、主要代码实现 Evidence、无身份/patch 归属冲突时，上限为 `IMPLEMENTED`。
- 只有外部 ownership evidence 明确关联 Item 时，上限为 `LED`。
- pending item 即使 `--include-pending` 也只能为 `CONTRIBUTED`，并设置 `pending=true`。
- LLM 输出 strength 高于上限时整个 LLM 输出无效，按配置降级或失败。

### 10.6 数字和成果校验

校验器必须检测：

- `%`、百分比和倍数表达。
- 收入、金额、用户数量、转化率、延迟、吞吐、可用性等结果型数字。
- “主导/负责全部/独立完成”等 ownership 词。

普通技术标识中的数字（Java 17、HTTP 2、v2 API）通过 allowlist 处理。结果型数字必须引用
`verifiedOutcomeIds`，且所有 ID 存在于已加载 outcomes。

## 11. CLI 设计

### 11.1 `gca assess`

```powershell
gca assess <repo> --person <identity> --since 2026-01-01 --no-llm
gca assess <repo> --all --since 2026-01-01 --no-llm
```

参数：

| 参数 | 必需 | 说明 |
|---|---|---|
| `path` | 否 | 默认当前目录 |
| `--person` / `--all` | 是 | 互斥，至少一个 |
| `--since/--until` | 否 | 复用 ISO 边界语义 |
| `--branch/--release/--scope/--delivery` | 否 | 复用 analyze 过滤 |
| `--no-llm` | 否 | 禁用解释，确定性报告仍完整 |
| `--json` | 否 | 输出 versioned envelope |

`--all` 允许未确认身份，但必须在相应 subject 和 `identityWarnings` 中标记；个人 `--person`
继续要求 confirmed identity。

### 11.2 `gca resume`

```powershell
gca resume <repo> --person <confirmed-identity> `
  --target-role "Senior Backend Engineer" `
  --language zh-CN `
  --style star `
  --max-bullets 6
```

参数：

| 参数 | 默认值 | 校验 |
|---|---|---|
| `--person` | 无 | 必需且唯一 confirmed |
| `--since/--until/--branch/--release/--scope` | 空 | 与 analyze 一致 |
| `--target-role` | 空字符串 | 最大 120 字符，不进入事实规则 |
| `--language` | `zh-CN` | `zh-CN` 或 `en-US` |
| `--style` | `concise` | `concise`、`star`、`xyz` |
| `--max-bullets` | `6` | 1..20 |
| `--include-pending` | false | pending claim 显式标记且上限 CONTRIBUTED |
| `--verified-outcomes` | 空 | UTF-8 YAML，严格 Schema |
| `--no-llm` | false | 使用确定性保守模板 |
| `--json` | false | 输出 versioned envelope |

### 11.3 `runs` 与 `report`

- `runs list` 人类输出增加 `[RUN_TYPE]`。
- `runs list --json` 每行增加 `runType`、`parentRunId`。
- `runs show` 不假设存在 `summary.commits`，根据 run type 输出对应摘要。
- `report` 先读取 `runType`，再严格分派 PERSON/PROJECT、WORK_ASSESSMENT、RESUME renderer。
- 未知 run type 返回 ReportError，不尝试猜测 Schema。

## 12. LLM 任务设计

### 12.1 Assessment explanation

Task：`assessment-explanation`
Prompt version：`assessment-explanation-v1`
Schema version：`assessment-explanation-v1`

输入只包含：

- workload/difficulty 确定性结果。
- 技术/业务域标签。
- 裁剪后的 Evidence summary 和 metrics。
- 允许的 Item/Evidence ID 白名单。

输出只包含：总体解释和逐事项解释，不包含 size/difficulty 字段。Application 将解释附加到已有等级，
而不是让 LLM 返回等级。

### 12.2 Resume generation

Task：`resume-generation`
Prompt version：`resume-v1`
Schema version：`resume-v1`

输入只包含：

- confirmed Person 的 display name，不含 email。
- target role、language、style、max bullets。
- eligible items、claim strength 上限、technical/business tags。
- Evidence summary、metrics 和 verified outcomes。

输出必须为 `ResumeClaim` 候选、项目概述和 skill evidence。Application 再执行 Item/Evidence 白名单、
claim strength、数字、ownership、语言和最大条数校验。

### 12.3 Provider 失败策略

| 场景 | assess | resume |
|---|---|---|
| Provider 不可用且允许 fallback | `PARTIAL`，保留确定性报告 | `PARTIAL`，使用保守模板 |
| Provider 不可用且禁止 fallback | `FAILED`，保留失败 run | `FAILED`，不保存未验证 claim |
| 无 Evidence | `COMPLETED`，跳过解释并警告 | `COMPLETED`，输出空候选和 limitation |
| Schema/白名单校验失败 | 同 Provider output error 策略 | 同 Provider output error 策略 |

## 13. SQLite 迁移与存储

### 13.1 迁移 `0005_run_types.py`

升级：

```sql
ALTER TABLE analysis_runs
  ADD COLUMN run_type VARCHAR(32) NOT NULL DEFAULT 'ANALYSIS';

ALTER TABLE analysis_runs
  ADD COLUMN parent_run_id VARCHAR(36) NULL;

CREATE INDEX ix_analysis_runs_run_type
  ON analysis_runs(repository_id, run_type, started_at);

CREATE INDEX ix_analysis_runs_parent_run_id
  ON analysis_runs(parent_run_id);
```

说明：SQLite v1 不为 `parent_run_id` 建立自引用外键，避免 batch recreate 影响已有
`contribution_items`、`evidence`、`capability_assessments` 和 `llm_invocations`。Application 在
`start_run` 前验证父运行存在、已完成且 repository 相同。

升级后移除 `run_type` 的 server default 依赖，由应用始终显式写入；SQLAlchemy metadata 保留
Python default `ANALYSIS` 兼容测试直接建表。

### 13.2 Store API 变更

`SqliteAnalysisStore.start_run` 新增：

```python
run_type: RunType = RunType.ANALYSIS
parent_run_id: str | None = None
schema_version: str = "1.0"
rule_version: str = "rules-v1"
```

新增/调整方法：

- `load_run_metadata(run_id)`：返回 type、parent、status、schema。
- `validate_parent_run(parent_run_id, expected_repository_id)`。
- `complete_run(..., persist_details=True)` 对三种报告安全处理，不再假设固定字段。
- `_insert_report_rows` 从 Snapshot/报告适配器获取 Item、Evidence、Capability rows，避免硬编码 PERSON shape。
- `get_report` 同时返回 run metadata 或在 result 内补齐历史默认 `ANALYSIS`。

### 13.3 降级策略

`downgrade()` 删除两个索引和两个新增列。迁移测试必须验证空库和仅含 ANALYSIS run 的 downgrade。

生产回滚原则：

- 应用代码回滚时保留 0005 的加法列，旧版本会忽略它们。
- 只有确认没有需要保留的 WORK_ASSESSMENT/RESUME lineage 时才执行数据库 downgrade。
- downgrade 前备份 `.gca/index.sqlite`；新 run 的 `result_json` 仍保留，但旧应用不能渲染新类型。

## 14. 文件级影响清单

### 14.1 新增生产文件

| 文件 | 作用 |
|---|---|
| `domain/models/run.py` | RunType |
| `domain/models/snapshot.py` | EvidenceSnapshot 及 canonical fingerprint |
| `domain/models/work_assessment.py` | size、difficulty、WorkAssessmentReport 模型 |
| `domain/models/resume.py` | VerifiedOutcome、ResumeClaim、ResumeReport 模型 |
| `domain/services/workload_rules.py` | eligible change、baseline 和 size band |
| `domain/services/difficulty_rules.py` | 维度信号和难度合成 |
| `domain/services/resume_claim_rules.py` | claim strength、数字和 ownership 校验 |
| `application/services/evidence_snapshot.py` | 从索引事实构建共享 Snapshot |
| `application/services/assessment_explanation.py` | assessment LLM task 和输出校验 |
| `application/services/resume_generation.py` | deterministic/LLM resume 生成和校验 |
| `application/use_cases/assess_work.py` | WORK_ASSESSMENT 用例和 run 生命周期 |
| `application/use_cases/generate_resume.py` | RESUME 用例和 run 生命周期 |
| `adapters/outcomes/yaml_loader.py` | UTF-8 verified outcomes 严格加载 |
| `adapters/reporting/work_assessment_markdown.py` | 工作评估 Markdown |
| `adapters/reporting/resume_markdown.py` | 简历 Markdown 与 Evidence appendix |
| `adapters/storage/sqlite/migrations/versions/0005_run_types.py` | run type 迁移 |
| `prompts/assessment/v1/__init__.py` | Prompt package |
| `prompts/assessment/v1/explanation.txt` | 工作评估解释 Prompt |
| `prompts/resume/v1/__init__.py` | Prompt package |
| `prompts/resume/v1/system.txt` | 简历约束 Prompt |
| `prompts/resume/v1/style-concise.txt` | concise 模式 |
| `prompts/resume/v1/style-star.txt` | STAR 模式 |
| `prompts/resume/v1/style-xyz.txt` | XYZ 模式 |
| `schemas/work-assessment/v1.json` | 正式工作评估报告 Schema |
| `schemas/resume/v1.json` | 正式简历报告 Schema |
| `schemas/commands/assess-v1.json` | assess CLI envelope |
| `schemas/commands/resume-v1.json` | resume CLI envelope |
| `schemas/llm/assessment-explanation-v1.json` | assessment LLM Schema |
| `schemas/llm/resume-v1.json` | resume LLM Schema |

上表 `prompts/...` 均位于 `src/git_contribution_analyzer/prompts/...`。

### 14.2 修改生产文件

| 文件 | 修改 |
|---|---|
| `cli/app.py` | 新增 assess/resume；抽取共享过滤参数装配；更新 runs/report 人类输出 |
| `domain/models/analysis.py` | 保持 AnalysisFilters 兼容，必要时增加规范化方法 |
| `domain/models/assessment.py` | 明确 CapabilityAssessment 语义，不放工作评估类型 |
| `domain/models/semantic.py` | 保留旧模型并标记 resume bullets deprecated |
| `domain/models/__init__.py` | 导出新领域类型 |
| `application/use_cases/analyze_contributions.py` | 改为消费 EvidenceSnapshot，保持输出不变 |
| `application/use_cases/analyze_project.py` | 复用 Snapshot builder，保持 PROJECT 输出不变 |
| `application/use_cases/generate_report.py` | 按 run type 分派 renderer |
| `application/use_cases/get_run.py` | 新 run type 的摘要与历史默认值 |
| `application/use_cases/list_runs.py` | 暴露 runType/parentRunId |
| `application/services/semantic_enhancement.py` | 旧 semantic 路径保持，增加 deprecated 注释，不接入新功能 |
| `adapters/storage/sqlite/models.py` | analysis_runs 两列和索引定义 |
| `adapters/storage/sqlite/analysis.py` | 通用 run 生命周期、父运行校验、报告详情持久化 |
| `adapters/llm/mock.py` | 按 task id 返回 assessment/resume 固定结果 |
| `adapters/reporting/markdown.py` | 保留旧 renderer，并提供顶层 dispatch 或公共格式函数 |
| `adapters/workspace/config.py` | 新增 assessment/resume 规则配置和 critical paths/noise paths |
| `schemas/llm/semantic-v1.json` | `resumeBullets` 增加 deprecated 标记 |
| `schemas/report/v1.json` | 保持字段可读，标记旧 resume 字段 deprecated |
| `README.md` | 双方向定位、快速示例和边界说明 |
| `CHANGELOG.md` | 新 CLI、Schema、迁移和 deprecation |

### 14.3 新增测试与黄金文件

| 文件 | 覆盖 |
|---|---|
| `tests/unit/test_evidence_snapshot.py` | canonical order、fingerprint、隐私裁剪 |
| `tests/unit/test_workload_rules.py` | 去重、noise、baseline、size band |
| `tests/unit/test_difficulty_rules.py` | 四等级、风险信号、文档反例 |
| `tests/unit/test_resume_claim_rules.py` | strength、数字、ownership、outcome |
| `tests/unit/test_assessment_explanation.py` | task context 和 LLM 白名单 |
| `tests/unit/test_resume_generation.py` | deterministic template、LLM 校验 |
| `tests/unit/test_verified_outcomes.py` | YAML 成功、缺字段、未知字段、编码 |
| `tests/integration/test_assessment_cli.py` | assess CLI、Schema、run、fallback |
| `tests/integration/test_resume_cli.py` | resume CLI、confirmed、styles、outcomes |
| `tests/integration/test_run_type_migration.py` | 0004 -> 0005 -> 0004 |
| `tests/integration/test_report_dispatch.py` | 三种 run type renderer 和历史 run |
| `tests/e2e/test_dual_track_cli.py` | 完整双轨生命周期 |
| `tests/golden/work-assessment/*.json` | 固定 Snapshot 确定性输出 |
| `tests/golden/resume/*.json` | no-LLM 和 Mock LLM 输出 |

修改 `tests/helpers/git_repo_builder.py`，补充 merge、revert、duplicate patch、migration、docs-only、
critical path 和多身份 fixture helper。

## 15. 分阶段实施计划

### 阶段 1：运行类型与 Evidence Snapshot

目标：建立共享事实边界和运行类型，不改变现有 analyze 行为。

RED：

1. 新增 Snapshot 指纹、稳定排序、敏感字段裁剪测试。
2. 新增迁移测试，证明旧 run 升级后为 ANALYSIS。
3. 新增 runs list/show 的 runType/parentRunId 测试。
4. 新增父运行跨仓库、未完成和不存在的拒绝测试。

GREEN：

1. 实现 `RunType`、`EvidenceSnapshot` 和 canonical serializer。
2. 抽取 `application/services/evidence_snapshot.py`。
3. 实现 `0005_run_types.py`、SQLAlchemy metadata 和 Store API。
4. 让 analyze person/project 复用 Snapshot builder，同时保持旧 JSON 一致。

IMPROVE：

1. 消除个人/项目分析重复的 commit -> item -> evidence 逻辑。
2. 固定排序、版本常量和错误类型。
3. 运行旧 analysis、LLM audit 和 E2E 全回归。

交付物：Snapshot v1、run types、迁移、兼容 analyze。

验收：旧 Schema/黄金结果通过；相同输入 Snapshot ID 一致；0004 数据可无损升级。

预计工作量：2-3 工程日。

### 阶段 2：工作量规模模型

目标：实现不依赖 LLM 的 eligible workload 和 size distribution。

RED：

1. `AUTHORED_ONLY` 不进入 completed workload。
2. merge、revert、generated、vendor、lockfile、binary line 和 duplicate patch 不重复计量。
3. repository baseline >=20 与 static fallback <20 的边界测试。
4. 相同 Snapshot 和 rule version 输出逐字一致。

GREEN：

1. 实现 WorkItemSizeAssessment、CompletionBucket 和 workload rules。
2. 加载 assessment noise paths 配置。
3. 生成 completed/pending/rework/integration 四类事项。
4. 生成 SMALL/MEDIUM/LARGE/XLARGE 分布和 baseline metadata。

IMPROVE：

1. 将规则常量集中到不可变 ruleset。
2. 对每个排除原因产生 metrics/warning，保证可审计。
3. 验证大文件和多模块场景的性能。

交付物：`workload-rules-v1` 和规模评估模型。

验收：所有规模结论有 Evidence/rule version；无员工总分；重复内容只计一次。

预计工作量：3-4 工程日。

### 阶段 3：工作难度规则 MVP

目标：用路径、变更类型和交付信号生成四级难度。

RED：

1. 小 diff 数据库迁移判 HIGH_RISK。
2. 大量简单 docs 判 ROUTINE 或 STANDARD，不因行数升级。
3. 跨模块 + 数据兼容判 COMPLEX。
4. 单域普通 feature 判 STANDARD，局部测试/配置判 ROUTINE。
5. 无 AST/impact Adapter 时 gap 和 confidence 正确。

GREEN：

1. 实现 DimensionSignal、DifficultyAssessment 和 rule composer。
2. 加入 migration、transaction、Redis、MQ、lock、idempotency、API contract、critical path 信号。
3. 将现有 capability rules 作为输入信号，不把 capability confidence 当 difficulty。
4. 输出 evidenceIds、gaps 和 confidence。

IMPROVE：

1. 统一路径模式和 rule code 命名。
2. 增加反例，防止规模向难度泄漏。
3. 用至少两个黄金 fixture 人工复核规则解释。

交付物：`difficulty-rules-v1` 和逐事项 DifficultyAssessment。

验收：四级难度稳定；LLM 未参与等级计算；关键反例通过。

预计工作量：3-5 工程日。

### 阶段 4：`gca assess`、Schema 与报告

目标：交付完整 no-LLM 工作评估命令。

RED：

1. CLI 参数互斥、必填、过滤和退出码测试。
2. PERSON/PROJECT WorkAssessmentReport Schema 测试。
3. runs/report dispatch 测试。
4. 目标分支异常和未确认项目身份 warning 测试。

GREEN：

1. 实现 `AssessWork` 用例和 run 生命周期。
2. 新增 `gca assess` CLI、JSON envelope 和 human summary。
3. 实现工作评估 Markdown，包含技术、业务、完成、规模、难度、Evidence 和限制章节。
4. 持久化 WORK_ASSESSMENT run、Snapshot details 和规则版本。

IMPROVE：

1. 抽取 CLI 共享过滤参数解析，避免 analyze/assess/resume 漂移。
2. 对 PROJECT scope 使用稳定 subject 排序，不生成排名。
3. 增加 JSON/Markdown 黄金快照。

交付物：`gca assess --person|--all --no-llm`。

验收：个人和项目命令可回放、可渲染、可 Schema 校验；确定性内容完整。

预计工作量：3-4 工程日。

### 阶段 5：独立 Resume 模型与确定性模板

目标：在无 LLM 时生成合法、保守、有证据的简历候选。

RED：

1. 未确认 Person 被拒绝。
2. 每条 claim 必须同时引用 Item 和 Evidence。
3. pending 默认排除，显式加入后标记 pending 且 strength 上限 CONTRIBUTED。
4. 无 verified outcome 时拒绝结果型数字。
5. 无 ownership evidence 时拒绝 LED。

GREEN：

1. 实现 ResumeReport、ResumeClaim、ClaimStrength 和 deterministic templates。
2. 实现 claim strength 上限、数字和 ownership 校验。
3. 从 completed items 生成 project summary、bullet 和 skill evidence。
4. 生成 omitted claims 和 evidence gaps。

IMPROVE：

1. 中英文模板分离，保持同一事实映射。
2. concise/STAR/XYZ 在 no-LLM 下使用不同结构但不补造 outcome。
3. 将技术/业务总结限制在已选 claim 范围。

交付物：resume domain 和 `--no-llm` 生成服务。

验收：无 LLM 输出通过 resume Schema；无夸大数字和 ownership。

预计工作量：2-3 工程日。

### 阶段 6：`resume-v1` LLM 与 Provider 审计

目标：通过现有 Provider SPI 增强简历表达，不扩大事实权限。

RED：

1. Prompt context 不含 email、源码正文、团队排名。
2. 未知 Item/Evidence/Outcome ID 被拒绝。
3. LLM strength 超上限、LED 无证据、非法数字被拒绝。
4. cache key 区分 semantic-v1、assessment-explanation-v1、resume-v1。
5. Provider timeout 的 fallback/strict 两种行为测试。

GREEN：

1. 实现 assessment explanation 和 resume generation 独立 task builders。
2. 新增 Prompt package、Pydantic 输出和 JSON Schema。
3. 扩展 Mock Provider 和统一 LLM 契约 fixture。
4. 复用 CachedAuditedProvider，记录 prompt/schema/provider/model。

IMPROVE：

1. 统一白名单和 claim validation 公共函数。
2. 限制 context 项目数和 Evidence 数，稳定排序和 hash。
3. 为 Codex CLI/Claude CLI 增加本地 smoke 文档，不在普通 CI 依赖已安装命令。

交付物：两个独立 LLM Task 和审计链路。

验收：Provider 可替换；LLM 不能修改等级或突破 claim 上限；失败可控降级。

预计工作量：2-3 工程日。

### 阶段 7：`gca resume`、Verified outcomes、Schema 与报告

目标：交付完整个人简历命令和外部成果输入。

RED：

1. CLI person/role/language/style/max-bullets 参数测试。
2. outcomes YAML 缺字段、未知字段、重复 ID、非法日期测试。
3. ResumeReport 和 command envelope Schema 测试。
4. Markdown 不泄漏 email、难度比较和其他人员信息。

GREEN：

1. 实现 `GenerateResume` use case 和 RESUME run 生命周期。
2. 新增 `gca resume` CLI。
3. 实现 YAML loader 和 verified outcome 引用。
4. 实现 resume Markdown：项目概述、bullets、skill evidence、omitted claims、Evidence appendix。

IMPROVE：

1. 统一 no-LLM/LLM 后的最终验证和排序。
2. 最大 bullet 数在最终验证后应用，避免截断引用关系。
3. 增加 zh-CN/en-US、concise/STAR/XYZ 黄金输出。

交付物：`gca resume` 完整命令。

验收：confirmed-only、Evidence 引用、outcome 约束、run/report 回放全部通过。

预计工作量：3-4 工程日。

### 阶段 8：兼容、文档、黄金仓库与跨平台验收

目标：完成发布质量门禁和旧功能回归。

RED：

1. 0004 旧数据库升级和旧 run 渲染测试。
2. 旧 PERSON/PROJECT/semantic-v1 Schema 回归。
3. Windows 路径含空格/中文，PowerShell/cmd help 和最小生命周期测试。
4. 构造 merge/revert/duplicate/generated/docs/migration 黄金仓库。

GREEN：

1. 更新 README、CLI、methodology、privacy、Schema 和 CHANGELOG。
2. 增加三平台 CI 命令矩阵。
3. 生成固定黄金 JSON/Markdown。
4. 执行 ruff、mypy、pytest、coverage、build。

IMPROVE：

1. 审计所有 Prompt、日志和报告中的 PII/源码内容。
2. 审计规则说明，确保没有员工总分、跨人排名和成果臆测。
3. 记录性能基线和已知限制。

交付物：可发布的双轨版本、文档和完整回归证据。

验收：全项目覆盖率 >=80%，核心层 >=90%，三平台最小生命周期通过，旧功能无回归。

预计工作量：3-5 工程日。

### 阶段 9：结构复杂度与影响分析 Adapter（MVP 后续）

目标：提高结构复杂度和调用影响维度的置信度，不改变已发布 Schema。

任务：

1. 定义 `ComplexityAnalyzer`、`ImpactAnalyzer` Application Port。
2. 首批实现 Java、Python、JavaScript/TypeScript Adapter。
3. 输出方法复杂度变化、公共 API、调用方和 fan-in/fan-out 信号。
4. 无 Adapter 的语言保持 v1 fallback 和 gap。
5. 使用独立规则版本 `difficulty-rules-v2`，不覆盖旧 run。

验收：Adapter 缺失不影响 v1；新信号只通过新规则版本生效；历史结果可重放。

预计工作量：5-8 工程日，不阻塞阶段 1-8 发布。

## 16. 阶段依赖与发布点

```text
阶段 1 -> 阶段 2 -> 阶段 3 -> 阶段 4 ----> assess MVP
   |                                  |
   +----------> 阶段 5 -> 阶段 6 -> 阶段 7 ----> resume MVP
                                              |
                                              +-> 阶段 8 发布验收

阶段 9 独立后续
```

推荐发布点：

- 阶段 4 完成：发布 `assess` alpha，先校准确定性口径。
- 阶段 7 完成：发布双轨 beta。
- 阶段 8 完成：发布正式双轨版本。

## 17. 具体测试策略

### 17.1 Domain 单元测试

`test_evidence_snapshot.py`：

- `should_generate_same_snapshot_id_when_input_order_changes()`
- `should_change_snapshot_id_when_baseline_or_filters_change()`
- `should_exclude_created_at_from_snapshot_fingerprint()`
- `should_not_include_person_email_in_llm_context()`

`test_workload_rules.py`：

- `should_exclude_authored_only_from_completed_workload()`
- `should_classify_landed_and_released_as_completed()`
- `should_classify_reverted_item_as_rework()`
- `should_separate_merge_commit_as_integration_work()`
- `should_count_duplicate_patch_only_once()`
- `should_ignore_generated_vendor_lockfile_and_binary_lines()`
- `should_use_static_thresholds_when_baseline_sample_is_small()`
- `should_use_repository_percentiles_when_baseline_is_sufficient()`

`test_difficulty_rules.py`：

- `should_mark_small_database_migration_as_high_risk()`
- `should_not_raise_difficulty_for_large_docs_only_change()`
- `should_mark_cross_module_data_compatibility_change_as_complex()`
- `should_mark_single_domain_api_logic_as_standard()`
- `should_mark_local_test_or_config_change_as_routine()`
- `should_lower_confidence_when_structural_adapter_is_unavailable()`

`test_resume_claim_rules.py`：

- `should_require_item_and_evidence_for_every_claim()`
- `should_cap_pending_claim_at_contributed()`
- `should_allow_implemented_for_confirmed_delivered_primary_implementation()`
- `should_reject_led_without_verified_ownership()`
- `should_reject_percentage_without_verified_outcome()`
- `should_allow_technical_version_number_without_outcome()`
- `should_reject_unknown_verified_outcome_id()`

### 17.2 Application 单元测试

`test_assessment_explanation.py`：

- `should_build_task_from_deterministic_assessment_only()`
- `should_reject_llm_reference_to_unknown_evidence()`
- `should_not_accept_llm_difficulty_override()`
- `should_retain_assessment_when_provider_fails()`

`test_resume_generation.py`：

- `should_generate_conservative_template_without_llm()`
- `should_limit_claims_after_validation()`
- `should_reject_llm_claim_above_strength_ceiling()`
- `should_fallback_to_template_when_provider_fails()`
- `should_fail_run_when_fallback_is_disabled()`

### 17.3 SQLite 集成测试

- 从 `0004_llm_audit` 升级后旧 rows 的 `run_type='ANALYSIS'`。
- 新 WORK_ASSESSMENT/RESUME run 可写入、读取、列表和渲染。
- parent run 不存在、跨 repository、RUNNING/FAILED 时拒绝。
- upgrade/downgrade 在空库及仅含旧 run 的数据库通过。
- 事务失败不留下半完成 run details。
- 旧数据库备份恢复后可以重新升级。

### 17.4 CLI 集成测试

- `assess --person --no-llm --json` 通过 command/report Schema。
- `assess --all --no-llm --json` 包含所有身份且不排名。
- `assess --person` 与 `--all` 同时提供返回参数错误。
- Provider 失败时 assess 为 PARTIAL 且 deterministic fields 不变。
- `resume --person --no-llm --json` 通过 Schema。
- 未确认 Person 的 resume 返回 identity exit code。
- `resume --include-pending` 只增加显式 pending claim。
- `resume --verified-outcomes` 允许有来源的结果数字。
- `report --run` 对三种 run type 使用正确 renderer。
- `runs list/show` 对历史 run 补默认 ANALYSIS 类型。

### 17.5 E2E 黄金仓库

固定仓库至少包含：

1. Alice 的 landed feature + test + docs。
2. Alice 的 authored-only feature branch。
3. Bob 的独立 feature，用于 `--all` 和隐私验证。
4. merge commit。
5. cherry-pick duplicate patch。
6. commit + revert。
7. 小型 migration/transaction 高风险变更。
8. 大量 docs-only 低难度变更。
9. generated、binary、lockfile。
10. release tag 和 target branch。

端到端流程：

```text
init -> identities map -> index
     -> analyze --no-llm
     -> assess --person --no-llm
     -> assess --all --no-llm
     -> resume --person --no-llm
     -> resume --person with mock LLM/outcomes
     -> runs list/show -> report markdown/json
```

### 17.6 质量命令

```powershell
uv run ruff check .
uv run mypy src
uv run pytest
uv run pytest --cov=git_contribution_analyzer --cov-report=term-missing
uv build
```

真实 Codex CLI、Claude CLI 和外部 HTTP Provider 只做手动 smoke，不进入无凭证的普通 CI。

## 18. 兼容与版本策略

### 18.1 CLI

- `gca analyze` 参数、默认值和输出结构保持不变。
- 新命令只增加，不复用 `analyze --profile`。
- `runs list/show` 的 JSON 新增字段为兼容性扩展；旧 run 在应用层补默认值。
- 退出码沿用现有错误映射，不新增 Provider 特有退出码。

### 18.2 Schema

- PERSON/PROJECT/analysis v1 不升版，不添加工作量和难度字段。
- Work Assessment、Resume 和两个 LLM task 独立 v1。
- `semantic.resumeBullets` 设置 `deprecated: true`，至少保留整个 1.x。
- 每次规则变化增加 rule version，不覆盖历史 run 的版本字段。

### 18.3 数据

- 迁移为加法变更；历史 run result_json 不重写。
- Git facts 可重建，confirmed identity 和 verified outcomes 引用不可静默丢失。
- 新版发现数据库 schema 高于支持版本时拒绝写入。

## 19. 优雅降级

| 故障 | 行为 |
|---|---|
| LLM 未启用或 `--no-llm` | assess 完整确定性输出；resume 保守模板 |
| LLM timeout/rate limit 且允许 fallback | run PARTIAL，保留确定性或模板输出和 warning |
| LLM 输出非法 | 不写入非法内容，按 Provider output error 降级 |
| verified outcomes 文件非法 | 命令失败，不忽略错误继续生成含数字 claim |
| 目标分支异常 | 输出警告，不生成完成率或完成比例措辞 |
| 结构 Adapter 不可用 | 使用路径/变更规则，增加 gap 并降低 confidence |
| 无 eligible completed item | 生成合法空报告和 limitation，不调用 LLM |
| 历史 run 无 run_type | 读取时视为 ANALYSIS |

## 20. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| 工作量被当成员工价值 | 高 | 高 | 不输出总分/完成率/排名，报告显著写明限制 |
| 大 diff 被误判高难度 | 中 | 高 | size/difficulty 分离，难度规则禁止使用 churn 升级 |
| 规则偏向某语言 | 中 | 中 | MVP 声明 gap；阶段 9 Adapter 和新规则版本 |
| 目标分支错误导致未完成 | 中 | 高 | 输出 baseline/target ref，异常比例触发 warning |
| 身份错误导致归属错误 | 中 | 高 | resume confirmed-only；project 未确认身份独立警告 |
| LLM 夸大结果 | 高 | 高 | ID 白名单、strength 上限、数字/outcome、ownership 校验 |
| Snapshot 与 run 数据漂移 | 低 | 高 | canonical fingerprint、单次命令单 Snapshot、版本字段 |
| SQLite 自关联迁移复杂 | 中 | 中 | v1 使用逻辑关联和索引，不做 batch self-FK |
| 新 Schema 过多 | 中 | 中 | 按产品/LLM task 独立目录和契约测试 |
| Provider 本地命令差异 | 中 | 中 | 继续复用 command provider，普通 CI 使用 Mock |

## 21. 回滚策略

### 21.1 代码回滚

1. 回滚到双轨功能前的应用版本。
2. 保留已升级 SQLite；新增列不会影响旧查询。
3. 验证 `analyze`、`runs` 和旧 `report`。
4. 新类型 run 保留在数据库，待恢复新版后继续读取。

### 21.2 数据库回滚

1. 停止 GCA 写操作。
2. 备份 `.gca/index.sqlite`。
3. 确认无需旧版本读取 WORK_ASSESSMENT/RESUME run。
4. 执行 Alembic downgrade 到 `0004_llm_audit`。
5. 校验旧 ANALYSIS run、identity、Git index 和 LLM audit 数量。

### 21.3 规则回滚

- 不修改历史 run。
- 恢复上一规则版本常量和配置。
- 新建 run 重新计算，报告同时展示 rule version。
- 黄金测试保留 v1/v2 多版本，不用更新快照覆盖历史语义。

### 21.4 Prompt 回滚

- Prompt/Schema 使用新版本号发布，不原地修改已发布版本。
- 切回旧 Prompt 产生新的 invocation/run，不覆盖缓存和审计。

## 22. 文档更新计划

| 文件 | 内容 |
|---|---|
| `README.md` | assess/resume 快速开始、两类用途和免责声明 |
| `doc/cli/cli-reference.md` | 新命令、参数、退出码、示例 |
| `doc/guides/methodology.md` | 完成、规模、难度、claim strength 口径 |
| `doc/guides/privacy.md` | Resume/LLM 的身份和数据边界 |
| `doc/architecture/data-model.md` | Snapshot、run type、0005 迁移 |
| `doc/architecture/llm-provider.md` | 两个新 task 的 Provider 契约 |
| `doc/testing/golden-dataset.md` | 双轨黄金仓库和更新规则 |
| `CHANGELOG.md` | 新功能、迁移、兼容和 deprecated 字段 |

如果上述文档尚不存在，阶段 8 创建；已存在则按当前目录规范更新。

## 23. 完成定义

阶段 1-8 全部满足以下条件后，双轨功能才算完成：

- [ ] `gca analyze` 和历史报告无回归。
- [ ] `gca assess --person|--all` 支持完整 no-LLM 路径。
- [ ] `gca resume --person` 只接受 confirmed Person。
- [ ] 相同 Snapshot/规则版本的确定性输出一致。
- [ ] completed/pending/rework/integration 口径符合提案。
- [ ] merge/revert/generated/binary/duplicate patch 不重复计量。
- [ ] size 与 difficulty 分离且都有 Evidence、version、confidence/gaps。
- [ ] 小 migration 高风险和大 docs 低难度反例通过。
- [ ] 每条 ResumeClaim 引用 Item 和 Evidence。
- [ ] 无 verified outcome 时不存在结果型数字。
- [ ] 无 ownership evidence 时不存在 LED。
- [ ] 两个新 LLM task 可使用任意现有 Provider，并有独立审计。
- [ ] Provider 失败时按配置降级或明确失败。
- [ ] 新旧 JSON Schema 和黄金样例全部通过。
- [ ] 0004 -> 0005 upgrade/downgrade 测试通过。
- [ ] Domain/Application 新代码覆盖率 >=90%，全项目 >=80%。
- [ ] Windows、Linux、macOS 最小 CLI 生命周期通过。
- [ ] README、CLI、methodology、privacy、data model 和 CHANGELOG 已同步。

## 24. 实施顺序

批准本实施方案后，按以下顺序执行：

1. 阶段 1：先建立 Snapshot 和 run type，不改变旧报告。
2. 阶段 2-4：完成确定性 Work Assessment 并发布 alpha 校准规则。
3. 阶段 5：完成 no-LLM Resume，先验证 claim 边界。
4. 阶段 6-7：接入独立 LLM task 和完整 Resume CLI。
5. 阶段 8：完成迁移、兼容、黄金仓库、文档和跨平台验收。
6. 阶段 9：在 MVP 发布后独立推进结构复杂度/影响 Adapter。

任何阶段若需要改变已批准的完成口径、难度权限、Resume claim 上限或兼容策略，必须先更新提案和
本实施方案，再进入对应 GREEN 实现。
