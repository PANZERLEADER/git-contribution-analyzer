# GCA 历史结构难度证据详细实施方案

## 1. 基本信息

| 项目 | 内容 |
|---|---|
| 功能名称 | 历史结构基线、热点/耦合暴露与条件式 difficulty 接入 |
| 项目 | Git Contribution Analyzer（GCA） |
| 影响模块 | Domain、Application、SQLite Adapter、CLI、GUI、Reporting、Schema、测试与文档 |
| 技术栈 | Python 3.12+、Typer、Pydantic 2、SQLAlchemy 2、Alembic、SQLite、PySide6/QML、pytest、jsonschema |
| 相关提案 | `doc/proposals/hercules-inspired-structural-analysis-proposals.md`（推荐方案二） |
| 推荐架构 | 方案一作为正确性参考实现，方案二作为正式持久化路径 |
| 作者 | Codex |
| 日期 | 2026-07-16 |
| 计划状态 | Observation-only 本地实施与发布验证完成；Phase 4 未启用；三平台 CI 待提交后执行 |

本计划是后续 `implement` 工作流的执行依据。每个阶段必须采用 RED -> GREEN -> IMPROVE：
先写失败测试和固定契约，再实现最小行为，最后在测试保护下重构。阶段 4 的
`difficulty-rules-v2` 是条件阶段；只有采用者明确提出自动提升并完成独立校准时才可实施。

### 1.1 实施结果（2026-07-16）

| 阶段 | 状态 | 结果 |
|---|---|---|
| Phase 0 | 完成 | v1 structural/difficulty/assessment 回归保持不变 |
| Phase 1 | 完成 | 纯 Domain baseline、窗口、hotspot、coupling、exposure 与稳定 ID 已实现 |
| Phase 2 | 社区配置完成、性能通过 | 已冻结保守的 `community-baseline-v1`；10k/100k、真实样本、1/10/100 增量及 7.14% assessment overhead 已记录；人工 calibration 保留为自动提升的可选验证 |
| Phase 3 | 本地完成 | SQLite occurrence/cache、完整状态生命周期、warm hit、CLI、status/doctor、取消、prune、Schema 与 GUI observation 页面已实现；三平台 CI 待执行 |
| Phase 4 | 未实施 | 自动 difficulty 提升关闭，继续使用 `difficulty-rules-v1`，不生成 work-assessment v3 |
| Phase 5 | 本地完成 | 251 tests、87.23% 总覆盖率、95% Application+Domain 覆盖率、ruff、mypy、build、隔离 wheel、Windows CLI/GUI standalone smoke 通过；三平台 CI 待执行 |

实现没有引入 Hercules runtime、Forge API、项目健康、trailer 或 AI provenance。历史结构结果仅为
仓库级观察，不进入个人工作量、难度、交付、排名、简历或 LLM 上下文。社区配置不要求项目专属
人工审核；校准缺失或任一冻结门槛失败时，只对自动 difficulty 提升保持 No-Go。

## 2. 背景与当前状态

### 2.1 当前能力

GCA 已具备以下可复用基础：

- SQLite Git index：`repositories`、`commits`、`commit_parents`、`file_changes`、
  `commit_delivery`、refs 和身份表；
- `structural-signals-v1`：从当前筛选后的 ContributionCommit 计算重复共同变更和热点；
- workload、difficulty、delivery 和 ranking 的确定性规则与版本化报告；
- EvidenceSnapshot、历史 run、work-assessment v1/v2、series/comparison 和 CSV/Markdown 导出；
- `gca index/sync/status/assess/doctor` 与 PySide6/QML GUI facade；
- workspace lock、进度、取消、Alembic migration 和跨平台发布流程。

当前关键文件：

| 关注点 | 文件 | 当前状态 |
|---|---|---|
| 结构观测 | `domain/services/structural_signals.py` | 当前范围内即时计算，无历史 cutoff/cache |
| Difficulty | `domain/services/difficulty_rules.py` | `difficulty-rules-v1`，raw `MULTI_MODULE` 可影响难度 |
| Workload | `domain/services/workload_rules.py` | module span 已影响 workload |
| Assessment | `application/use_cases/assess_work.py` | 每个 Item 直接调用 v1 difficulty |
| 周期评估 | `application/use_cases/assess_work_series.py` | 复用 assessment，但没有结构 baseline |
| Git 同步 | `application/use_cases/index_repository.py` | 增量写入 Git index，没有结构事实阶段 |
| SQLite | `adapters/storage/sqlite/models.py` | 最新迁移为 `0006_identity_merges.py` |
| CLI | `cli/app.py` | 无 `structural` 命令组 |
| 状态/诊断 | `get_status.py`、`run_doctor.py` | 不检查结构缓存 |

仓库没有 `doc/research/`。本计划以已批准提案、当前源码、Schema、迁移和测试为事实依据。

### 2.2 问题陈述

当前结构信号来自被评估者当前周期内的提交，因此不能作为个人 difficulty 的历史上下文：

1. 高活跃者会生成更多边和热点，造成循环归因；
2. 当前周期可能进入基线，造成未来信息泄漏；
3. 原始展示分数没有仓库分位、hub 控制和样本置信度；
4. 多人和多周期评估会重复计算相同结构事实；
5. 只保存已过阈值边会丢失未来跨阈值所需的低频累计；
6. percentile 是全局派生值，不能按单文件只追加；
7. `MULTI_MODULE` 同时影响 workload 和 difficulty。

### 2.3 实施目标

1. 建立严格早于 `periodStart` 的仓库级历史结构 baseline。
2. 建立全量正确性参考实现，作为 SQLite 缓存和增量结果的逐项参照。
3. 持久化所有有效文件出现和全部非零共同变更事实，阈值只用于 materialization。
4. 支持 lifetime、rolling-window 和 dual-window，并默认使用保守 dual-window 配置。
5. 输出热点、耦合、hub 控制、confidence、gaps 和 Evidence。
6. 先以 observation-only 形式发布，不改变 v1 difficulty/ranking。
7. 只有采用者明确要求自动提升，且 holdout 质量门槛和性能门槛同时通过，才启用
   `difficulty-rules-v2`。
8. 历史 run、work-assessment v1/v2 和现有 CLI 行为保持兼容。

### 2.4 非目标

- 不增加 structural 第四排名维度；
- 不建设项目健康评分、bus factor、技术债、复杂度趋势或分支健康产品面；
- 不实现 Git trailer、Forge API、fork 网络、AI provenance 或 LLM 结构评分；
- 不引入 Hercules runtime、Go/Rust worker 或跨进程协议；
- 不以热点、耦合、churn、ownership 或存活时间推断个人价值；
- 不在质量门槛失败时降低门槛或强制启用 v2；
- 不回写历史 assessment result JSON。

## 3. 已确定的设计决策

1. 采用提案方案二；方案一必须先实现并长期保留为测试参考。
2. Domain 只接收结构事实和配置值，不读取 Git、SQLite、CLI 或 GUI。
3. baseline 的历史范围由目标分支在 cutoff 前的最后可达状态决定，不按个人 author 历史构建。
4. 没有显式 `since/periodStart` 时不推断历史 difficulty，输出
   `STRUCTURAL_PERIOD_START_REQUIRED` gap。
5. 结构事实时间以目标分支历史状态为准；assessment 的 AUTHORED/COMMITTED/LANDED/RELEASED
   只决定工作事项周期，不允许未来目标分支状态进入 baseline。
6. 新 baseline ID 使用 canonical JSON 的 SHA-256，输入包含 repository、baseline commit、cutoff
   UTC、branch、scope、filter fingerprint、time strategy、fact/metric/threshold version。
7. 所有出现过的有效文件和非零文件边都保存为提交级 occurrence；阈值不影响事实写入。
8. baseline file/edge counts 是 occurrence 的缓存聚合；percentile、Jaccard、条件概率和 hub 惩罚
   属于 materialization。
9. observation-only 使用独立 `structural-baseline/v1` 契约，不修改 work-assessment v2。
10. 社区配置固定 observation-only；可选自动提升 Go/No-Go 通过后才新增 work-assessment v3，
    v1/v2 继续读取和导出。
11. phase 2 不自动增加每次 assessment 的冷构建成本；用户或 GUI 先执行
    `gca structural rebuild`，后续 sync 增量更新。没有 cache 时 assessment 只输出 gap。
12. `gca structural prune` 只清理可重建 cache，不删除 Git index 或历史 run。
13. 不增加第三方运行时依赖；使用现有 Python 标准库、SQLAlchemy 和 SQLite。
14. `community-baseline-v1` 使用通用保守阈值；自动提升的项目专属阈值必须在 calibration set 上
    选择并冻结后才运行 repo-disjoint holdout。
15. Hercules 只用于固定 fixture 的非阻塞交叉验证；其不可用不能使 CI 失败。

本计划没有留待编码阶段决定的开放架构问题。

## 4. 功能与非功能需求

### 4.1 功能需求

#### FR-01：全量正确性参考

系统必须从有序的有效 commit/path facts 生成原始 file/edge counts 和 materialization。

验收标准：

- 相同输入和 rule config 产生逐字一致的 canonical JSON；
- merge、duplicate patch、generated、binary-only 和 context cap 语义与 v1 一致；
- 边规范化为 `left_path < right_path`；
- 低于候选阈值的非零边仍保留在原始 counts；
- v1 structural report fixture 在共享路径过滤重构后输出不变。

#### FR-02：历史 baseline

- baseline 只包含 cutoff 前目标分支状态中可达的提交；
- baseline 不包含被评估人的身份或 cohort；
- 相同 key 命中已有 COMPLETED baseline；
- FAILED/CANCELLED baseline 不可作为 assessment 输入；
- 任意历史 cutoff 可以重建，结果与相同输入的参考实现一致。

#### FR-03：结构事实增量

- full index rebuild 清理并重建该 repository 的结构 occurrence；
- linear sync 只处理未记录的新 commit；
- force-push、默认分支变化和 filter/rule 变化使相关 baseline 失效；
- 一条边第一次出现后未过阈值，第二/第三次出现时能正确累计过阈值；
- 取消发生时不发布半完成 baseline。

#### FR-04：时间策略

阶段 1 支持：

- `LIFETIME`；
- `ROLLING_WINDOW`，候选窗口为 180、365、730 天；
- `DUAL_WINDOW`，长期 lifetime 加近期 365 天；
- `DECAYED` 仅保留模型接口，不在本计划实现。

开源默认策略固定为 `DUAL_WINDOW`，近期窗口 365 天。项目只有在启用自动 difficulty 提升时，
才需要通过 calibration 选择替代策略并在 holdout 前冻结。

#### FR-05：热点与耦合 materialization

候选指标：

- file change count 和 percentile；
- recent percentile（rolling/dual）；
- co-change count；
- subset ratio；
- left/right conditional probability；
- Jaccard；
- hub frequency/penalty；
- cross-module；
- sample confidence 和 gaps。

社区基础配置：

- 最小 baseline 有效提交：50；
- hotspot percentile：0.95；
- 最小共同变更：3；
- subset ratio：0.80；
- Jaccard：0.30；
- hub penalty：0.50；
- 最大有效路径 context：100；
- automatic difficulty promotion：false。

以下搜索网格只用于可选的自动提升校准：

- 最小 baseline 有效提交：50、100、200；
- hotspot percentile：0.85、0.90、0.95；
- 最小共同变更：2、3、5；
- subset ratio：0.60、0.75、0.90；
- Jaccard：0.10、0.20、0.30；
- 最大有效路径 context：100、200、400。

自动提升组合只允许在 calibration set 上选择；holdout 不得调参。Observation-only 项目可以覆盖
社区阈值，但覆盖必须进入 baseline fingerprint，且不能启用个人 difficulty 提升。

#### FR-06：Observation-only

- `gca structural status/rebuild/show/prune` 输出版本化 JSON；
- GUI 可查看 baseline 状态、概要、热点和耦合候选；
- observation-only 不改变 size、difficulty、delivery、ranking、LLM prompt 或 resume；
- assessment 不读取 structural baseline，因此既不提升也不回退到个人当前期信号；
- structural baseline JSON 和 GUI 显示 gaps/limitations。

#### FR-07：条件式 difficulty v2

仅在采用者明确启用自动提升且 Go/No-Go 通过后：

- 新增 `HISTORICAL_HOTSPOT_EXPOSURE`；
- 新增 `HISTORICAL_COUPLING_EXPOSURE`；
- 单个 Item 最多从 STANDARD 提升为 COMPLEX；
- 结构信号不能产生 HIGH_RISK；
- 移除 raw `MULTI_MODULE` difficulty，module span 继续属于 workload；
- ranking 只读取最终 difficulty level；
- 发布新 rule/cohort fingerprint。

#### FR-08：诊断与清理

- top-level `status/v2` 返回 structural cache 摘要，历史 `status/v1` 保持不变；
- doctor 验证 migration、FAILED/RUNNING 残留、orphan rows、baseline commit 可达性和磁盘容量；
- rebuild 支持 cutoff、branch、scope 和 time strategy；
- prune 默认保留最新 8 个非历史 run 引用 baseline；被历史 run 引用的 baseline 不删除；
- prune 必须显式 `--yes`。

### 4.2 非功能需求

| 编号 | 要求 | 指标 |
|---|---|---|
| NFR-01 | 确定性 | 相同 baseline key 输出相同 ID、counts 和 materialization hash |
| NFR-02 | 防泄漏 | fixture 中当前期/未来 commit 进入 baseline 的数量必须为 0 |
| NFR-03 | 增量一致 | 增量与同 cutoff 全量参考结果逐项一致 |
| NFR-04 | Warm 性能 | warm assessment 相对 v1 总耗时增加不得超过 20% |
| NFR-05 | Sync 性能 | 结构处理只随新 commits 及其有效 path pairs 增长 |
| NFR-06 | 空间 | 不分配完整 F x F；所有表均可按 repository/baseline 清理 |
| NFR-07 | 质量 | 新 Domain/Application 代码覆盖率 >= 90%，全项目 >= 80% |
| NFR-08 | 隐私 | 不上传路径、人员、矩阵或源码；不进入 LLM prompt |
| NFR-09 | 兼容 | 旧 run/schema/CLI/CSV/Markdown 可继续读取 |
| NFR-10 | 跨平台 | Windows、Linux、macOS wheel/standalone smoke 通过 |

## 5. 总体架构

```text
Git index facts
  commits / parents / file_changes / delivery
          |
          v
Structural fact extraction (pure domain)
  file occurrences / edge occurrences / exclusions
          |
          +-----------------------+
          |                       |
          v                       v
Full reference builder      SQLite occurrence ledger
                                  |
                                  v
                         Baseline aggregation cache
                                  |
                                  v
                         Versioned materialization
                         hotspot / coupling / confidence
                                  |
                    +-------------+-------------+
                    |                           |
                    v                           v
             observation-only report     conditional difficulty v2
                                                |
                                                v
                                      existing ranking dimensions
```

依赖方向保持：

```text
Domain <- Application <- Adapters <- CLI / GUI
```

## 6. Domain 设计

### 6.1 新模型

新建 `src/git_contribution_analyzer/domain/models/structural_baseline.py`：

```text
StructuralTimeStrategy
  LIFETIME | ROLLING_WINDOW | DUAL_WINDOW

StructuralBaselineStatus
  BUILDING | COMPLETED | FAILED | CANCELLED | STALE

StructuralBaselineKey
  repository_id
  baseline_commit
  cutoff_utc
  branch
  scope
  filter_fingerprint
  time_strategy
  fact_rule_version
  metric_rule_version
  threshold_version

StructuralCommitFacts
  commit_hash
  occurred_at
  paths
  edges
  excluded_reason
  context_capped

StructuralFileCount
  path
  change_count
  recent_change_count

StructuralEdgeCount
  left_path
  right_path
  co_change_count
  recent_co_change_count

StructuralFileMetric
  path
  percentile
  recent_percentile
  hotspot
  confidence

StructuralEdgeMetric
  left_path / right_path
  co_change_count
  subset_ratio
  left_conditional / right_conditional
  jaccard
  hub_penalty
  cross_module
  candidate
  confidence

StructuralMaterialization
  baseline_id
  metric_version
  threshold_version
  summary
  file_metrics
  edge_metrics
  gaps
  limitations

WorkItemStructuralContext
  baseline_id
  hotspot_exposures
  coupling_exposures
  confidence
  gaps
```

所有 dataclass 使用 `frozen=True, slots=True`；枚举使用 `StrEnum`；集合在构造时排序为 tuple。

### 6.2 新服务

新建 `domain/services/structural_baseline.py`：

- `extract_structural_commit_facts(commits, rule_config)`
- `aggregate_structural_counts(facts, window)`
- `materialize_structural_metrics(file_counts, edge_counts, rule_config)`
- `match_work_item_structural_context(item, materialization)`
- `canonical_baseline_id(key)`
- `canonical_materialization_hash(materialization)`

规则常量：

- `STRUCTURAL_FACT_RULE_VERSION = "structural-facts-v1"`
- `STRUCTURAL_METRIC_RULE_VERSION = "structural-metrics-v1"`
- 社区配置使用 `STRUCTURAL_THRESHOLD_VERSION = "structural-thresholds-community-v1"`；未来自动
  提升配置必须使用独立版本，不能复用该 observation-only 标识。

修改 `domain/services/structural_signals.py`：

- 只提取共享的 path eligibility helper；
- 保留 `structural-signals-v1` 常量、阈值、排序和输出完全不变；
- 以 golden test 证明重构前后 JSON 相同。

### 6.3 Difficulty v2（条件文件）

只有 Go/No-Go 通过后新建
`domain/services/difficulty_rules_v2.py`：

- 不修改 `difficulty_rules.py` 的 v1 公开行为；
- 复用 v1 的 migration、distributed、critical、compatibility 等事实判断；
- 不生成 raw `MULTI_MODULE`；
- 接受 `WorkItemStructuralContext | None`；
- context 缺失或 confidence 不足时保持 STANDARD 并输出 gap；
- 合格 exposure 最多增加一个 SUBSTANTIAL signal；
- HIGH_RISK 仍只能由现有 critical rules 产生。

## 7. Application 设计

### 7.1 Port

新建 `application/ports/structural_baseline.py`：

```python
class StructuralBaselineStore(Protocol):
    def replace_repository_facts(...) -> None: ...
    def append_commit_facts(...) -> None: ...
    def processed_commit_hashes(...) -> frozenset[str]: ...
    def find_completed_baseline(...) -> StructuralMaterialization | None: ...
    def begin_baseline(...) -> None: ...
    def complete_baseline(...) -> None: ...
    def fail_baseline(...) -> None: ...
    def mark_stale(...) -> int: ...
    def status(...) -> StructuralStoreStatus: ...
    def prune(...) -> StructuralPruneResult: ...
```

Port 不暴露 SQLAlchemy Row、Connection 或 JSON string。

### 7.2 Use cases

实现采用与现有项目一致的 use-case composition，不按命令机械拆文件：

1. `application/use_cases/manage_structural_baselines.py`
   - `get_structural_status()`
   - `rebuild_structural_baseline()`
   - `show_structural_baseline()`
   - `prune_structural_baselines()`
   - 解析 repository、cutoff、branch、scope；
   - 构造 key、查询 cache，并编排 BUILDING/COMPLETED/FAILED/CANCELLED 生命周期。

2. `application/use_cases/index_repository.py`
   - full rebuild replace；
   - incremental append；
   - force-push 后把不可达 baseline 标记为 STALE；
   - default branch/filter/rule 变化通过 branch/fingerprint/version 防止错误复用；
   - 通过现有 progress/cancellation port 报告阶段。

修改：

- `index_repository.py`：Git index transaction 成功后调用 structural fact sync；
- `assess_work.py` / `assess_work_series.py`：phase 4 前不读取 structural baseline；
- `get_status.py`：加入 structural summary；
- `run_doctor.py`：加入结构表一致性和 stale/building 检查；
- `application/facades/gui.py` 与 `application/dto/gui.py`：增加 rebuild/show/prune 请求 DTO。

## 8. SQLite 数据模型

### 8.1 Migration

新建：

`src/git_contribution_analyzer/adapters/storage/sqlite/migrations/versions/0007_structural_baselines.py`

新增七张表。

#### `structural_commit_facts`

| 字段 | 类型 | 约束 |
|---|---|---|
| repository_id | String(36) | PK/FK repositories |
| commit_hash | String(64) | PK |
| fact_rule_version | String(40) | PK |
| occurred_at | DateTime UTC | not null |
| path_count | Integer | not null |
| edge_count | Integer | not null |
| context_capped | Boolean | not null |
| excluded_reason | String(40) | nullable |
| processed_at | DateTime UTC | not null |

#### `structural_file_occurrences`

主键：`repository_id, commit_hash, fact_rule_version, path`。

每个有效 commit/path 一行。即使文件最终不是 hotspot 也必须保存。

#### `structural_edge_occurrences`

主键：`repository_id, commit_hash, fact_rule_version, left_path, right_path`。

约束：`left_path < right_path`。每个 commit/edge 最多一行，不能只保存已过阈值边。

#### `structural_baselines`

| 字段 | 类型 | 说明 |
|---|---|---|
| id | String(64) PK | canonical SHA-256 |
| repository_id | String(36) FK | repository |
| baseline_commit | String(64) | cutoff 前目标分支状态 |
| cutoff_at | DateTime UTC | 严格上界 |
| branch | Text | 目标 ref |
| scope | Text nullable | path prefix |
| filter_fingerprint | String(64) | branch/path/noise |
| time_strategy | String(24) | lifetime/rolling/dual |
| fact_rule_version | String(40) | facts |
| metric_rule_version | String(40) | metrics |
| threshold_version | String(40) | calibrated thresholds |
| status | String(20) | lifecycle |
| eligible_commit_count | Integer | summary |
| eligible_file_count | Integer | summary |
| raw_edge_count | Integer | summary |
| created_at/completed_at | DateTime UTC | lifecycle |
| error_message | Text nullable | sanitized |

唯一索引覆盖 baseline key 的全部字段；另建
`repository_id, cutoff_at, status` 索引。

#### `structural_file_counts`

主键：`baseline_id, path`；字段为 `change_count, recent_change_count`。

#### `structural_edge_counts`

主键：`baseline_id, left_path, right_path`；字段为
`co_change_count, recent_co_change_count`。保存全部非零聚合边。

#### `structural_materializations`

主键：`baseline_id, metric_rule_version, threshold_version`；字段为
`content_hash, result_json, created_at`。result JSON 只保存报告候选和限制，不复制原始 occurrence。

### 8.2 Adapter

新建 `adapters/storage/sqlite/structural_baseline.py` 实现 Port。

要求：

- occurrence 使用批量 `sqlite_insert(...).on_conflict_do_nothing()`；
- baseline 发布使用单一 transaction：BUILDING -> counts/materialization -> COMPLETED；
- 读取大 commit hash 集合时分批，避免 SQLite bind limit；
- prune 按 FK cascade 删除 counts/materialization，不删除 occurrence；
- error message 不包含源码、邮箱或完整命令输出；
- connection 和 engine 必须在异常路径释放。

修改 `adapters/storage/sqlite/models.py` 添加 Table 定义。

### 8.3 Downgrade

`0007` downgrade 按以下顺序删除：

1. `structural_materializations`
2. `structural_edge_counts`
3. `structural_file_counts`
4. `structural_baselines`
5. `structural_edge_occurrences`
6. `structural_file_occurrences`
7. `structural_commit_facts`

所有表均为可重建派生数据，downgrade 不修改 Git index 和 `analysis_runs`。

## 9. CLI、GUI 与报告契约

### 9.1 CLI

在 `cli/app.py` 新增 `structural_app = typer.Typer(...)`：

```text
gca structural status [PATH] [--json]
gca structural rebuild [PATH]
  [--cutoff ISO-8601]
  [--branch REF]
  [--scope PATH]
  [--time-strategy lifetime|rolling-window|dual-window]
  [--json]
gca structural show [PATH] --baseline BASELINE_ID [--json]
gca structural prune [PATH] [--keep 8] --yes [--json]
```

错误语义：

- 无 workspace：现有 WORKSPACE_ERROR；
- 无 baseline：NOT_FOUND；
- 无 `--yes`：USAGE_ERROR；
- cancelled：现有 cancellation exit code；
- FAILED baseline：命令失败但保留诊断 ID。

### 9.2 Schema

新建：

- `schemas/structural-baseline/v1.json`
- `schemas/commands/structural-status-v1.json`
- `schemas/commands/structural-prune-v1.json`
- `schemas/status/v2.json`；`schemas/status/v1.json` 保持原契约。

phase 4 条件新增：

- `schemas/work-assessment/v3.json`
- 必要时新增 `work-assessment-series/v2.json` 和
  `work-assessment-comparison/v2.json`，旧版本不修改。

work-assessment v3 每个 item 增加可选 `structuralContext`，包含 baseline 引用、exposures、
confidence 和 gaps；raw count 全集不嵌入 assessment result。

### 9.3 Reporting

修改：

- `adapters/reporting/work_assessment_markdown.py`
- `adapters/reporting/work_assessment_csv.py`
- `adapters/reporting/markdown.py`（如 structural show 复用）

Observation Markdown 只显示 top candidates、baseline、threshold version 和 limitations。
CSV 只增加稳定的 baseline/exposure 摘要列，不展开边矩阵。

### 9.4 GUI

修改：

- `adapters/gui/controller.py`
- `gui/qml/Main.qml`
- `application/facades/gui.py`
- `application/dto/gui.py`

新增：

- structural cache 状态；
- rebuild/cancel/prune 控件；
- hotspot/coupling 表；
- observation-only 标签；
- phase 4 前不显示“难度已提升”文案。

GUI 不查询 SQLite，不解析 CLI JSON，继续只调用 facade。

## 10. 社区配置与可选 Promotion Go/No-Go

### 10.1 社区配置

新增 `config/structural-community-baseline-v1.json`，并由 `write_default_config()` 将同一组值写入
新工作区 `.gca/config.yml`。该配置的验收条件为：

- `automaticDifficultyPromotion` 固定为 `false`；
- 所有结构阈值进入 baseline/cache fingerprint；
- 项目覆盖阈值后仍保持 observation-only；
- 规范 JSON 与运行时默认值由测试逐字段校验。

### 10.2 可选自动提升数据集

以下内容不是社区 observation-only 发布的前置条件，只适用于未来自动改变个人 difficulty 的规则。

新建：

- `tests/fixtures/structural-calibration/calibration.json`
- `tests/fixtures/structural-calibration/holdout.json`
- `doc/testing/structural-calibration.md`

最低规模：

- 总计至少 120 个 Work Item；
- calibration 至少 80 个，holdout 至少 40 个；
- holdout 与 calibration repository 不重叠；
- 至少覆盖 6 个 repository；
- 至少包含 20 个机械/hub negative controls；
- 至少包含新仓库、成熟仓库、monorepo、稀疏仓库各一组；
- 每个样本由两个复核者独立标注。

标签只回答：

- 历史 hotspot 是否为本次工作提供可解释的额外 difficulty 上下文；
- 历史 coupling 是否为跨文件/模块工作提供可解释的额外 difficulty 上下文；
- 是否属于机械、hub、批量 rename 或其他 false-positive 类型。

不得标注员工价值、工时、质量或最终绩效。

### 10.3 自动提升冻结门槛

在打开 holdout 前，calibration 必须冻结 metric config，并记录 SHA-256。

Go 条件全部满足：

- 两名复核者 Cohen's kappa >= 0.75；
- hotspot exposure holdout precision >= 0.85；
- coupling exposure holdout precision >= 0.85；
- 机械/hub negative controls false-positive rate <= 0.05；
- 样本不足仓库 abstain rate = 1.0，不允许猜测；
- 同一 baseline 重复 materialization 稳定性 = 1.0；
- v2 promoted items 占 completed STANDARD items 的比例 <= 0.15；
- 任一 repository promoted 比例 <= 0.20；
- 每个 promotion 都有 baseline、路径/边、阈值和 Evidence。

Recall 只报告，不设最低值；本功能优先避免误报。

任一条件失败即自动提升 No-Go：

- 社区 observation-only 配置继续可发布和使用；
- phase 4 不实施；
- `difficulty-rules-v1` 保持默认；
- 失败结果写入 `doc/reports/structural-calibration-report.md`；
- 修改门槛必须重新走 calibration 和新的 repo-disjoint holdout。

## 11. 实施阶段

### 阶段 0：契约锁定与 v1 回归

目标：冻结现有行为，防止结构重构影响已发布结果。

RED：

1. 扩充 `tests/unit/test_structural_signals.py` golden cases；
2. 扩充 `tests/unit/test_difficulty_rules.py`，锁定 MULTI_MODULE v1；
3. 扩充 `tests/unit/test_work_assessment_compatibility.py`，锁定 v1/v2；
4. 增加 current-period leakage 的失败测试。

GREEN/IMPROVE：

- 只添加 fixture 和测试工具；
- 不改变 production 输出。

交付物：

- v1 canonical golden；
- baseline key 和结构规则常量草案；
- 测试数据构造器。

验收：

- [x] 现有测试全绿；
- [x] v1 report JSON/Markdown 无差异；
- [x] 历史 `status/v1` 保持原契约，新增 `status/v2` 承载 structural summary。

工作量：中。

### 阶段 1：纯 Domain 正确性参考与指标实验

目标：不依赖 SQLite 实现全量 baseline 和 materialization。

RED：

- 新增 `tests/unit/test_structural_baseline.py`；
- 新增 `tests/unit/test_structural_exposure.py`；
- 覆盖 cutoff、排序、duplicate、merge、binary、generated、context cap、hub 和时间窗口。

GREEN：

- 创建 `domain/models/structural_baseline.py`；
- 创建 `domain/services/structural_baseline.py`；
- 重构共享 path eligibility，保持 v1 golden；
- 实现 canonical ID/hash；
- 实现候选指标网格。

IMPROVE：

- 消除不必要的 commit hash 全集驻留；
- 所有输出稳定排序；
- mypy strict 无 Any 泄漏。

交付物：

- 全量正确性参考实现；
- structural-baseline/v1 Domain serializer；
- calibration fixture 格式。

验收：

- [x] 相同输入结果逐字一致；
- [x] 当前期 commit 不进入 baseline；
- [x] 低频边保留；
- [x] hub fixture 可区分 subset ratio、Jaccard 与显式 hub penalty；
- [x] Domain 新代码覆盖率 >= 90%。

工作量：大。

### 阶段 2：社区配置、可选 Calibration 与性能基线

目标：冻结通用保守的 observation-only 配置并完成性能基线；保留可选 calibration 流程用于决定
是否允许后续 difficulty 自动接入。

任务：

1. 创建 `config/structural-community-baseline-v1.json` 并接入 `.gca/config.yml`；
2. 创建 `scripts/benchmark_structural_baseline.py`；
3. 创建 `doc/testing/structural-calibration.md`；
4. 运行 10k/100k commit synthetic 和至少两个真实本地仓库 benchmark；
5. 测试所有有效阈值进入 cache fingerprint；
6. 可选：在 calibration 上选择自动提升配置并冻结 config hash；
7. 可选：运行 holdout 一次；
8. 生成：
   - `doc/reports/structural-calibration-report.md`
   - `doc/reports/structural-baseline-performance.md`

验收：

- [x] 社区配置与运行时默认值逐字段一致；
- [x] 社区配置固定 observation-only；
- [x] 自动提升验证未启用，calibration/holdout 不构成 observation-only 前置条件；
- [x] 自动提升参数保持关闭，不执行 holdout 调参；
- [x] benchmark 记录冷构建、warm、增量、内存、边数和 SQLite 估算。

工作量：大。

### 阶段 3：SQLite occurrence、baseline cache 与 observation-only

目标：实现方案二，但不改变 difficulty。

RED：

- 新增 `tests/integration/test_structural_baseline_cli.py`；
- 覆盖 migration upgrade/downgrade、rebuild、warm hit、低频边累计、cancel、force-push、
  default branch 变化、prune 和 doctor；
- 扩充 `tests/integration/test_git_index_cli.py` 验证结构 sync；
- 扩充 GUI facade/controller 测试。

GREEN：

- 创建 migration 0007；
- 修改 models；
- 创建 SQLite adapter 和 application port/use cases；
- 新增 structural CLI group；
- 接入 index/sync、status、doctor；
- 新增 schema/report/GUI observation surface；
- 所有 baseline 原子发布。

IMPROVE：

- 批量 insert、SQLite bind 分块；
- 取消检查点；
- cache prune；
- 错误信息脱敏。

验收：

- [x] 增量和全量参考逐项一致；
- [x] warm hit 不扫描历史；
- [x] FAILED/CANCELLED 不可消费，并保留脱敏诊断 ID；
- [x] observation-only 不改变 work-assessment v2；
- [x] doctor 可识别 orphan/stale/building/failed；
- [ ] 三平台测试通过。

工作量：大。

### 阶段 4：条件式 difficulty-rules-v2

前置条件：采用者明确要求自动提升、阶段 2 可选 promotion gate 为 Go，且阶段 3 warm overhead
<= 20%。

当前 `automaticDifficultyPromotion=false`，本阶段未触发，不计入 observation-only 完成条件。

RED：

- 新增 `tests/unit/test_difficulty_rules_v2.py`；
- 扩充 assessment/period/series/comparison/ranking 测试；
- 增加新仓库、短历史、hub、机械提交和 v1/v2 分布回归。

GREEN：

- 创建 `difficulty_rules_v2.py`；
- 修改 WorkItemAssessment 增加 structural context；
- 修改 assess_work/series 选择 v2；
- 新增 work-assessment v3 及必要的 series/comparison 新版本；
- 更新 Markdown/CSV/GUI；
- 发布新 cohort fingerprint。

验收：

- [ ] 只允许 STANDARD -> COMPLEX；
- [ ] 无 baseline 时不提升；
- [ ] HIGH_RISK 语义不变；
- [ ] workload/delivery 不变；
- [ ] ranking 不读取 raw exposure；
- [ ] promotion 分布满足冻结门槛；
- [ ] 历史 v1/v2 run 完整可读。

工作量：中到大。

### 阶段 5：发布、文档与回归

任务：

- 更新 `README.md`、`README.zh-CN.md`；
- 更新 architecture、data-model、methodology、CLI reference 及中文镜像；
- 更新 performance baseline、privacy、golden dataset；
- 更新 CHANGELOG 和 release note；
- 运行完整质量门；
- 运行 wheel、CLI standalone、GUI standalone 三平台 smoke；
- 执行最终代码审查。

验收：

- [x] 文档明确 observation-only/Go/No-Go；
- [x] 安装升级和 downgrade 流程可复现；
- [x] 所有 Schema fixture 通过；
- [x] 当前 Windows wheel/CLI/GUI artifacts 不包含 Hercules 或第二语言 runtime；
- [x] 本地最终审查无 Critical/High finding；
- [ ] 当前变更提交后，Windows/Linux/macOS CI matrix 全绿。

工作量：中。

## 12. 文件影响清单

### 12.1 新建文件

| 文件 | 阶段 | 用途 |
|---|---|---|
| `domain/models/structural_baseline.py` | 1 | Domain 模型 |
| `domain/services/structural_baseline.py` | 1 | 参考计算、指标和 exposure |
| `application/ports/structural_baseline.py` | 3 | Store port |
| `application/use_cases/manage_structural_baselines.py` | 3 | build/status/rebuild/show/prune |
| `adapters/storage/sqlite/structural_baseline.py` | 3 | SQLite adapter |
| `migrations/versions/0007_structural_baselines.py` | 3 | 数据迁移 |
| `schemas/structural-baseline/v1.json` | 3 | baseline contract |
| `schemas/commands/structural-status-v1.json` | 3 | status contract |
| `schemas/commands/structural-prune-v1.json` | 3 | prune contract |
| `schemas/status/v2.json` | 3 | 带 structural summary 的 repository status contract |
| `config/structural-community-baseline-v1.json` | 2 | 社区 observation-only 规范配置 |
| `tests/unit/test_structural_baseline.py` | 1 | Domain tests |
| `tests/unit/test_structural_config.py` | 2 | 默认值、转换和 fingerprint tests |
| `tests/unit/test_structural_exposure.py` | 1 | exposure tests |
| `tests/integration/test_structural_baseline_cli.py` | 3 | E2E/storage/CLI |
| `tests/fixtures/structural-calibration/calibration.json` | 2 | calibration |
| `tests/fixtures/structural-calibration/holdout.json` | 2 | holdout |
| `scripts/benchmark_structural_baseline.py` | 2 | benchmark |
| `doc/testing/structural-calibration.md` | 2 | 标注协议 |
| `doc/reports/structural-calibration-report.md` | 2 | Go/No-Go 结果 |
| `doc/reports/structural-baseline-performance.md` | 2 | 性能结果 |
| `domain/services/difficulty_rules_v2.py` | 4 条件 | v2 difficulty |
| `tests/unit/test_difficulty_rules_v2.py` | 4 条件 | v2 tests |
| `schemas/work-assessment/v3.json` | 4 条件 | v3 report |

以上 Python 路径均相对于 `src/git_contribution_analyzer/`。

### 12.2 修改文件

| 文件 | 变更 |
|---|---|
| `domain/services/structural_signals.py` | 共享 eligibility，锁定 v1 输出 |
| `domain/models/work_assessment.py` | phase 4 增加 structural context |
| `domain/services/difficulty_rules.py` | 只提取可复用 helper，v1 行为不变 |
| `application/use_cases/index_repository.py` | 结构 facts sync |
| `application/use_cases/assess_work.py` | phase 4 前保持不读取 structural baseline |
| `application/use_cases/assess_work_series.py` | phase 4 前保持历史行为 |
| `application/use_cases/get_status.py` | structural summary |
| `application/use_cases/run_doctor.py` | structural checks |
| `application/facades/gui.py` | structural operations |
| `application/dto/gui.py` | structural DTO |
| `adapters/storage/sqlite/models.py` | 新表 |
| `adapters/workspace/config.py` | 社区 structural 配置与项目覆盖 |
| `adapters/reporting/work_assessment_markdown.py` | exposure output |
| `adapters/reporting/work_assessment_csv.py` | 稳定摘要列 |
| `adapters/gui/controller.py` | GUI commands/state |
| `gui/qml/Main.qml` | structural panel |
| `cli/app.py` | structural command group |
| `schemas/work-assessment-series/*` | phase 4 新版本兼容 |
| `schemas/work-assessment-comparison/*` | phase 4 新版本兼容 |
| `tests/unit/test_structural_signals.py` | v1 golden |
| `tests/unit/test_difficulty_rules.py` | v1 golden |
| `tests/unit/test_work_assessment_compatibility.py` | schema replay |
| `tests/integration/test_git_index_cli.py` | sync/rewrite |
| `tests/integration/test_assessment_cli.py` | observation/v2 |
| `tests/integration/test_assessment_periods_cli.py` | cutoff reuse |
| `tests/unit/test_gui_facade.py` | GUI facade |
| `tests/unit/test_gui_controller.py` | GUI state |
| README/architecture/data-model/methodology/CLI/中文镜像 | 用户和维护文档 |

## 13. 测试策略

### 13.1 Unit

- baseline canonical ID 对字段顺序不敏感；
- cutoff 严格使用 `< periodStart`；
- path normalization；
- duplicate patch 只计一次；
- merge/generated/binary-only 排除；
- context cap 产生 gap；
- 一次边保留但非 candidate；
- 多次边跨阈值；
- hub 文件被 Jaccard/hub penalty 控制；
- lifetime/rolling/dual 结果正确；
- exposure 只匹配 Item paths；
- v2 最多提升一级；
- v2 不产生 HIGH_RISK；
- v1 golden 不变。

### 13.2 Integration

- 0006 -> 0007 upgrade；
- 0007 downgrade -> upgrade；
- full rebuild、incremental sync；
- force-push/default branch change；
- historical cutoff cache hit；
- concurrent rebuild 被 workspace lock 串行化；
- cancellation 无半成品；
- prune 保留历史 run 引用；
- status/doctor JSON schema；
- assessment 无 baseline gap；
- phase 4 v3 run 与 v2 replay；
- GUI facade 不绕过 application。

### 13.3 Performance

运行：

```powershell
.\.venv\Scripts\python.exe scripts\benchmark_structural_baseline.py --commits 10000
.\.venv\Scripts\python.exe scripts\benchmark_structural_baseline.py --commits 100000
```

记录：

- occurrence 构建时间；
- baseline 聚合时间；
- materialization 时间；
- warm lookup；
- incremental 1/10/100 commits；
- peak RSS；
- file/edge occurrence rows；
- SQLite bytes/commit；
- assessment overhead。

### 13.4 Quality gates

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m pytest --cov=git_contribution_analyzer --cov-report=term
.\.venv\Scripts\python.exe -m build
.\.venv\Scripts\python.exe scripts\verify_wheel.py --wheel <wheel-path>
.\.venv\Scripts\python.exe scripts\verify_standalone.py
.\.venv\Scripts\python.exe scripts\verify_gui_standalone.py
```

## 14. 回滚与降级

### 14.1 Observation-only 回滚

- 停止调用 structural use cases；
- 保留 0007 表或执行 Alembic downgrade；
- 旧 analyze/assess/resume 行为不受影响；
- 删除 cache 后可从 Git index 重建；
- historical result JSON 不修改。

### 14.2 Difficulty v2 回滚

- 新 run 恢复 `difficulty-rules-v1`；
- v3 historical run 继续由兼容 reader 渲染；
- 不将 v3 值重写为 v2；
- ranking fingerprint 阻止跨规则比较；
- 如果发布后发现误报，立即停止生成 v2，不静默调阈值。

### 14.3 Migration 失败

- transaction 失败时 Alembic revision 不前进；
- 删除部分新表后重新运行 upgrade；
- Git index 和 analysis_runs 不受影响；
- doctor 给出 structural migration failure，不把数据库整体误报为可用。

## 15. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| 大 commit 产生 O(k²) 边 | 高 | 高 | versioned context cap、gap、benchmark |
| 公共 hub 伪耦合 | 高 | 高 | Jaccard/conditional/hub negative controls |
| 旧热点长期占优 | 中 | 中 | lifetime/rolling/dual calibration |
| 低频边丢失 | 中 | 高 | 保存全部 non-zero occurrence，测试跨阈值 |
| percentile 增量错误 | 中 | 高 | 每 baseline 统一 materialize |
| force-push 复用旧 cache | 中 | 高 | baseline reachability/fingerprint/stale |
| 多 cutoff 数据膨胀 | 中 | 中 | keep=8、历史引用保护、prune |
| v2 系统性抬高难度 | 中 | 高 | repo-disjoint holdout、promotion cap |
| SQLite 锁等待 | 中 | 中 | workspace lock、短 transaction、WAL |
| Hercules 不可运行 | 高 | 低 | 非阻塞交叉验证，不作为 CI 依赖 |

## 16. 已解决问题

1. **是否自动构建缺失 baseline？**
   - 决策：phase 2 不自动冷构建；显式 rebuild。phase 4 仍要求已完成 cache，无 cache 只输出 gap。

2. **是否保存阈值以下的边？**
   - 决策：保存所有 non-zero occurrence 和 aggregate count。

3. **是否实现时间衰减？**
   - 决策：本计划不实现 DECAYED，只比较 lifetime/rolling/dual。

4. **是否直接修改 difficulty v1？**
   - 决策：不修改；通过条件文件和新 schema/version 引入 v2。

5. **是否增加项目健康、Forge、trailer 或 AI 分析？**
   - 决策：不增加，保持提案产品边界。

6. **是否引入第二语言？**
   - 决策：本计划不引入；只有方案二正确但性能不达标时重新提案。

## 17. 参考资料

- `doc/proposals/hercules-inspired-structural-analysis-proposals.md`
- `doc/architecture/architecture.md`
- `doc/architecture/data-model.md`
- `doc/guides/methodology.md`
- `doc/testing/golden-dataset.md`
- `doc/reports/performance-baseline.md`
- `src/git_contribution_analyzer/domain/services/structural_signals.py`
- `src/git_contribution_analyzer/domain/services/difficulty_rules.py`
- `src/git_contribution_analyzer/domain/services/workload_rules.py`
- `src/git_contribution_analyzer/application/use_cases/assess_work.py`
- `src/git_contribution_analyzer/application/use_cases/index_repository.py`
