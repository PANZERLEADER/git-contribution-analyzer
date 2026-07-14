# GCA 多人筛选、身份合并与工作评估排序实施方案

## 1. 基本信息

| 项目 | 内容 |
|---|---|
| 功能名称 | 多人筛选、可逆身份合并与工作评估排序 |
| 目标版本 | `0.2.0` |
| 技术栈 | Python 3.12/3.13、Typer、Pydantic、SQLAlchemy、Alembic、SQLite |
| 相关提案 | `doc/proposals/team-selection-identity-merge-ranking-proposals.md`（推荐方案二） |
| 方案类型 | CLI、领域规则、数据库迁移、Schema 和报告导出 |
| 日期 | 2026-07-15 |

## 2. 背景和目标

### 2.1 当前状态

GCA 0.1.0 已具备：

- `gca identities list/map`：列出 Person/alias，并将一个 alias 映射到规范 Person。
- `gca assess --person`：评估一个已确认 Person。
- `gca assess --all`：评估索引中的全部 Person。
- `WORK_ASSESSMENT v1`：输出完成状态、规模、难度、技术/业务总结和 Evidence。
- `gca report --format markdown|json`：从持久化 run 重建报告。

当前限制：

- `--person` 只能出现一次。
- `--all` 不能排除指定人员。
- `identities map` 是单 alias 操作，没有 Person merge、审计或撤销。
- `WORK_ASSESSMENT v1` 明确不输出 ranking/score。
- `report` 不支持 CSV。

### 2.2 问题陈述

团队使用者需要控制整体评估的人员范围，处理同一现实人员使用多个 Git 身份的情况，并对选定
cohort 进行透明、可配置的排序和表格导出。现有功能无法安全支持这些工作流。

### 2.3 目标

1. 支持重复 `--person` 选择多个 Person。
2. 支持 `--all` 配合重复 `--exclude-person`。
3. 增加可预览、可审计、可撤销的 Person merge。
4. 保留历史 Person 和历史 run，不改写已持久化结果。
5. 新增 `work-assessment/v2`，提供多维排名和可选权重总分。
6. 新增 CSV renderer，从持久化 run 重建团队评估表格。
7. 保持 LLM 无权修改 selector、raw score、weight、total score 或 rank。

### 2.4 非目标

- 不回写或修改 `work-assessment/v1` Schema。
- 不移动或重写已发布的 `v0.1.0` tag。
- 不按 commit 数、原始代码行数、提交时间或 LLM 文案排名。
- 不在 0.2.0 中把业务领域标签转成绩效分数。
- 不实现 Excel `.xlsx`；0.2.0 提供 CSV、Markdown 和 JSON。
- 不自动做跨仓库、跨团队的绝对排名。
- 不删除被合并 Person，也不改写历史 run 的 `person_id` 或 `result_json`。

## 3. 功能需求和验收标准

### FR-01：多人显式选择

`gca assess` 的 `--person` 改为可重复参数：

```powershell
gca assess <repo> `
  --person alice@example.com `
  --person bob@example.com `
  --no-llm `
  --json
```

验收标准：

- 一个 `--person` 保持个人评估语义，`scopeType=PERSON`。
- 两个及以上不同 Person 时，`scopeType=PROJECT`。
- selector 支持 Person ID、规范邮箱、唯一规范名称。
- 名称匹配多个 Person 时返回 identity error，不能任意选择。
- 不同 selector 解析到同一 Person 时返回参数错误。
- 显式选择只接受 active、confirmed、`HUMAN` Person。
- 选择在读取 commit 之前完成。

### FR-02：全员排除

```powershell
gca assess <repo> `
  --all `
  --exclude-person ci@example.com `
  --exclude-person former-member@example.com `
  --no-llm `
  --json
```

验收标准：

- `--exclude-person` 可重复。
- `--exclude-person` 只允许与 `--all` 同时使用。
- `--all` 默认只选择 active、confirmed、`HUMAN` Person。
- 未确认 Person、非 HUMAN Person 和无时间范围内 commit 的 Person 记录排除原因。
- 排除 selector 可通过源 Person redirect 到合并后的 target Person。
- 排除全部人员时明确失败，不创建 run。
- 报告记录请求 selector、最终 included Person ID、excluded Person ID 和 reason。

### FR-03：选择范围模型

新增不可变领域模型 `PersonSelection`：

```text
PersonSelection
  mode: EXPLICIT | ALL
  requestedSelectors
  includedPersonIds
  exclusions
  confirmedOnly: true
  allowedKinds: [HUMAN]
  warnings

PersonExclusion
  selector nullable
  personId nullable
  reason
```

验收标准：

- canonical JSON 序列化顺序稳定。
- Snapshot ID 包含最终 Person 范围，但不包含用户输入顺序。
- run `parameters_json` 保留原始 selector 顺序和最终 ID。
- 相同人员集合即使 selector 顺序不同，Snapshot ID 和确定性结果一致。

### FR-04：身份合并预览

```powershell
gca identities merge <repo> `
  --source <selector> `
  --source <selector> `
  --target <selector> `
  --dry-run `
  --json
```

预览输出：

- target Person；
- source Person 列表；
- 将移动的 alias；
- source 历史 run 数；
- selector redirect；
- kind/confirmed/冲突检查；
- 是否可以安全执行。

验收标准：

- `--source` 至少一个，可重复。
- source 和 target 必须属于同一仓库。
- target 必须 active、confirmed、`HUMAN`。
- source 必须 active、`HUMAN`；允许未确认 source。
- source 不得包含 target，也不得重复。
- inactive/已合并 source 明确失败并提示现有 target。
- dry-run 不写数据库。

### FR-05：执行身份合并

```powershell
gca identities merge <repo> `
  --source <selector> `
  --target <selector> `
  --yes `
  --json
```

验收标准：

- 必须显式提供 `--yes`；`--dry-run` 和 `--yes` 互斥。
- 所有 source alias 在一个 SQLite 事务中移动到 target。
- source Person 标记 `active=false`，设置 `merged_into_person_id=target.id`。
- source Person 不删除。
- 创建状态为 `ACTIVE` 的 merge event，保存 alias 和 source 快照。
- commit 仍引用原 alias ID；通过 alias 的新 person_id 归入 target。
- 历史 run 和 report 内容完全不变。
- 合并完成后，新 `identities list` 清楚显示 inactive source 和 target redirect。

### FR-06：合并历史和撤销

```powershell
gca identities merges <repo> --json
gca identities unmerge <repo> --merge-id <id> --yes --json
```

验收标准：

- merges 按创建时间倒序列出 ACTIVE/REVERTED 事件。
- unmerge 只允许撤销 ACTIVE event。
- 每个 alias 必须仍在该 event 的 target 下；任何冲突导致整个事务失败。
- alias 恢复到原 source Person。
- source Person 恢复 `active=true`，清空 redirect。
- event 更新为 `REVERTED` 并写入 `reverted_at`。
- target 在合并后新增或人工映射的 alias 不受影响。
- 撤销后新分析恢复原人员归属，历史分析仍不改变。

### FR-07：现有 `identities map` 兼容

验收标准：

- 命令参数和 JSON envelope 保持兼容。
- Alias reassignment 复用新的事务原语。
- 不再物理删除 alias 数为零的旧 Person。
- 当 map 使旧 Person 无 alias 时，旧 Person 标记 inactive 并 redirect 到 target。
- 创建 `eventType=ALIAS_MAP` 的 merge event，允许通过 unmerge 恢复。

### FR-08：工作评估 Schema v2

新增 `work-assessment/v2`，保留 v1 不变。

顶层新增：

```text
schemaVersion: "2.0"
selection: PersonSelection
ranking:
  enabled
  ruleVersion nullable
  cohortFingerprint nullable
  dimensions
  composite nullable
  config nullable
```

验收标准：

- 0.2.0 新创建的 WORK_ASSESSMENT run 使用 v2。
- 历史 v1 run 继续支持 `runs show` 和 Markdown/JSON report。
- v1 renderer 不依赖 v2 字段。
- v2 在 ranking 未启用时输出 `enabled=false` 和空 dimensions。
- `run.ruleVersion=work-assessment-v2`。

### FR-09：多维排名

```powershell
gca assess <repo> --all `
  --rank-by workload `
  --rank-by difficulty `
  --rank-by delivery `
  --no-llm `
  --json
```

支持维度：`workload`、`difficulty`、`delivery`。

验收标准：

- `--rank-by` 可重复，重复维度报参数错误。
- 排名只针对 included Person。
- 每个维度输出 raw value、rank、tie key、Evidence IDs、confidence 和 gaps。
- 使用 dense ranking。
- 排序稳定：raw value 降序，Person ID 升序作为最终稳定键。
- 相同 raw value 共享 rank。
- LLM 不接收 ranking raw values，不参与名次计算。

### FR-10：排名确定性规则

规则版本：`performance-ranking-v1`。

工作量原始值：

```text
SMALL=1, MEDIUM=3, LARGE=6, XLARGE=10
workloadRaw = sum(completed item size points)
```

难度原始值：

```text
ROUTINE=1, STANDARD=2, COMPLEX=4, HIGH_RISK=6
difficultyRaw = sum(completed item difficulty points)
```

交付原始值：

```text
if completedItems == 0:
  deliveryRaw = 0
else:
  reworkRatio = reworkItems / completedItems
  penaltyRatio = min(reworkRatio * 0.15, 0.30)
  deliveryRaw = completedItems * (1 - penaltyRatio)
```

补充规则：

- pending 不扣分，独立展示。
- integrationWork 不加分也不扣分。
- raw line count 和 commit count 不参与。
- raw value 使用 Decimal，序列化为四位小数。

验收标准：

- 小型高风险迁移可以在 difficulty 上高于大型文档事项。
- 大量纯文档不会因行数提高 difficulty。
- duplicate patch、merge diff、generated/binary/lockfile 不重复增加 workload。
- rework penalty 最大为 30%。
- 相同输入跨 Windows/Linux/macOS 得到相同四位小数。

### FR-11：可选权重总分

```powershell
gca assess <repo> --all `
  --ranking-config team-ranking.yml `
  --no-llm `
  --json
```

配置文件：

```yaml
schemaVersion: "1.0"
rankingRuleVersion: performance-ranking-v1
weights:
  workload: 0.45
  difficulty: 0.35
  delivery: 0.20
normalization: cohort-max
ties: dense
```

计算规则：

```text
normalizedDimension = raw / cohortMax * 100
cohortMax == 0 时 normalizedDimension = 0
weightedValue = normalizedDimension * weight
totalScore = sum(weightedValue)
```

验收标准：

- 权重字段只允许 workload/difficulty/delivery。
- 权重均在 `[0,1]`，总和必须精确为 `1.0`。
- config 使用 Decimal 解析，拒绝 NaN/Infinity。
- 总分和分项值量化到四位小数。
- `cohortFingerprint` 包含 Snapshot ID、排序规则版本、sorted Person IDs 和规范配置 JSON。
- 同分时比较 workload、difficulty、delivery normalized value；全部相同则并列。
- 未提供 config 时不生成 totalScore/totalRank。
- 业务总结保留，但 0.2.0 不把业务领域标签转换为分数。

### FR-12：CSV 导出

```powershell
gca report <repo> --run latest --format csv --output team-assessment.csv
gca report <repo> --run latest --format csv --include-email --output internal.csv
```

默认 CSV 字段：

```text
personId,personName,workloadRank,workloadRaw,difficultyRank,difficultyRaw,
deliveryRank,deliveryRaw,totalRank,totalScore,completedItems,pendingItems,
reworkItems,confidence,gaps
```

验收标准：

- 只支持 WORK_ASSESSMENT v2；v1 请求 CSV 返回 report error。
- 使用标准库 `csv`，UTF-8 with BOM，兼容常见表格软件。
- 默认不含邮箱。
- `--include-email` 仅影响 CSV，不修改持久化 run。
- CSV 行顺序：totalRank（有总分）或第一个 rank-by 维度，其后 Person ID。
- CSV 从 `result_json` 重建，不重新访问 Git。
- Markdown v2 增加排名表；JSON 保持完整审计字段。

### FR-13：LLM 边界

验收标准：

- 新增 `assessment-explanation-v2` Prompt/Schema。
- Provider 上下文可包含选择范围摘要和确定性工作事项。
- Provider 上下文不包含 weight、raw score、normalized score、total score 或 rank。
- Provider 输出只能写入 explanation，不能修改 selection/ranking。
- Provider fallback 不影响任何排名结果。

## 4. 非功能需求

| 编号 | 要求 |
|---|---|
| NFR-01 | v1 历史 run、Schema 和 renderer 不回归 |
| NFR-02 | Merge/Unmerge 使用单 SQLite 事务 |
| NFR-03 | 所有人员解析和排除在加载 commit 前完成 |
| NFR-04 | Snapshot、ranking 和 CSV 跨平台确定性 |
| NFR-05 | 新 Domain/Application 代码覆盖率 >=90%，全项目 >=80% |
| NFR-06 | 所有 merge event、selection、rule version 和 config 可审计 |
| NFR-07 | CSV/Markdown 默认不暴露邮箱和其他未选择人员 |
| NFR-08 | 普通 CI 覆盖 Windows/Linux/macOS × Python 3.12/3.13 |
| NFR-09 | 数据库 upgrade/downgrade 和备份流程有集成测试 |
| NFR-10 | 15,000 commit/200 ref 基准中，selector 过滤额外开销 <5% |

## 5. 技术设计

### 5.1 总体流程

```text
CLI selectors
  -> ResolvePersonSelection
      -> active/confirmed/HUMAN validation
      -> redirect resolution
      -> included/excluded Person IDs
          -> BuildEvidenceSnapshot
              -> WorkAssessment v2
                  -> RankingRules (optional)
                      -> persisted result_json
                          -> JSON/Markdown/CSV renderer
```

身份合并流程：

```text
identities merge --dry-run
  -> resolve source/target
  -> build MergePreview

identities merge --yes
  -> BEGIN IMMEDIATE transaction
  -> revalidate preview preconditions
  -> insert identity_merge_events
  -> move aliases
  -> mark source inactive + redirect
  -> COMMIT

identities unmerge --yes
  -> BEGIN IMMEDIATE transaction
  -> validate event and alias ownership
  -> restore aliases and source status
  -> mark event REVERTED
  -> COMMIT
```

### 5.2 Domain 模型

新建 `domain/models/person_selection.py`：

```text
SelectionMode
PersonExclusion
PersonSelection
PersonResolution
```

新建 `domain/models/identity_merge.py`：

```text
IdentityMergeStatus: ACTIVE | REVERTED
IdentityMergeEventType: PERSON_MERGE | ALIAS_MAP
IdentityMergePreview
IdentityMergeEvent
```

新建 `domain/models/ranking.py`：

```text
RankingDimension: WORKLOAD | DIFFICULTY | DELIVERY
RankingRuleConfig
DimensionScore
PersonRanking
CompositeRanking
RankingResult
```

修改 `domain/models/work_assessment.py`：

- 保留现有模型。
- 增加 Person 级聚合输入对象，避免 ranking service 直接解析 dict。
- 不在 WorkItemAssessment 中保存 rank。

### 5.3 Application 服务和用例

新建 `application/services/person_selection.py`：

- `resolve_person_selection(...) -> PersonSelection`
- 负责 selector 解析、redirect、去重、类型和确认状态校验。

修改 `application/use_cases/assess_work.py`：

- 接受 `person_selectors: tuple[str, ...]` 和 `excluded_selectors: tuple[str, ...]`。
- 移除内部单 selector/布尔选择分支。
- 使用 PersonSelection 加载 subjects。
- 构建 v2 report。
- ranking 参数只传给确定性 ranking service。

新建身份用例：

- `application/use_cases/preview_identity_merge.py`
- `application/use_cases/merge_identities.py`
- `application/use_cases/list_identity_merges.py`
- `application/use_cases/unmerge_identities.py`

新建 `application/services/ranking_config.py`：

- 读取 UTF-8 YAML。
- 使用 Pydantic + JSON Schema 校验。
- 输出不可变 RankingRuleConfig。

修改 `application/use_cases/generate_report.py`：

- 增加 `csv`。
- 接受 `include_email`。
- 根据 report schema/version 选择 renderer。

### 5.4 Storage Adapter

修改 `adapters/storage/sqlite/models.py`：

`persons` 新增：

```text
active Boolean NOT NULL default true
merged_into_person_id String(36) nullable
```

新增 `identity_merge_events`：

| 字段 | 类型 | 约束 |
|---|---|---|
| `id` | String(36) | PK |
| `repository_id` | String(36) | FK repositories，非空 |
| `event_type` | String(20) | PERSON_MERGE/ALIAS_MAP |
| `target_person_id` | String(36) | FK persons，非空 |
| `source_person_ids_json` | Text | 非空 |
| `moved_alias_ids_json` | Text | 非空 |
| `source_snapshots_json` | Text | 非空 |
| `status` | String(20) | ACTIVE/REVERTED |
| `created_at` | DateTime TZ | 非空 |
| `reverted_at` | DateTime TZ | 可空 |

索引：

- `(repository_id, status, created_at)`
- `(repository_id, target_person_id)`
- `persons(repository_id, active, canonical_name, canonical_email)`
- `persons(merged_into_person_id)`

新建 `adapters/storage/sqlite/identity_merge.py`：

- selector 查询和 redirect 查询。
- merge preview 查询。
- merge/unmerge 事务。
- merge event list/get。
- history run count。

修改 `adapters/storage/sqlite/git_index.py`：

- list identities 增加 active、mergedIntoPersonId。
- map_identity 复用 alias reassignment primitive，不删除 Person。

修改 `adapters/storage/sqlite/analysis.py`：

- 新增批量 `load_people_for_selection(person_ids)`。
- resolve confirmed person 时处理 redirect，并返回 resolution metadata。
- `list_people_for_analysis` 默认过滤 active；兼容内部显式 include inactive 查询。

### 5.5 Alembic 迁移

新建：

`adapters/storage/sqlite/migrations/versions/0006_identity_merges.py`

Upgrade：

1. `persons.active`，server default `true`。
2. `persons.merged_into_person_id` nullable。
3. 创建 indexes。
4. 创建 `identity_merge_events`。
5. 现有 Person 全部 active=true。

Downgrade：

1. 检查 ACTIVE merge event 数量；非零时抛出明确维护错误，要求先 unmerge。
2. 删除 merge event 表和 indexes。
3. 删除 persons 新列。

SQLite 自关联 FK 不加到 `merged_into_person_id`，由应用事务校验，避免 batch alter 和降级复杂度。

### 5.6 CLI 契约

修改 `cli/app.py`：

```text
assess:
  --person TEXT       repeatable
  --all
  --exclude-person    repeatable, only with --all
  --rank-by           repeatable enum
  --ranking-config    Path

identities merge:
  --source            repeatable
  --target
  --dry-run | --yes
  --json

identities merges:
  --status ACTIVE|REVERTED|ALL
  --json

identities unmerge:
  --merge-id
  --yes
  --json

report:
  --format markdown|json|csv
  --include-email
```

CLI 参数验证在打开 Provider 或创建 run 前执行。

### 5.7 Ranking Service

新建 `domain/services/ranking_rules.py`：

- 常量和版本号。
- Person 聚合。
- workload/difficulty/delivery raw score。
- dense rank。
- cohort-max normalization。
- weighted composite。
- cohort fingerprint。

实现约束：

- 使用 `Decimal`，不使用二进制 float 参与最终分数。
- 所有映射按固定 enum 顺序。
- 所有 Person 按 ID 排序后计算 fingerprint。
- ties 基于量化后的值，不使用显示字符串。
- score 只引用 completed item 和明确 rework count。

### 5.8 报告和 Schema

新建：

- `schemas/work-assessment/v2.json`
- `schemas/commands/assess-v2.json`
- `schemas/ranking-config/v1.json`
- `schemas/commands/identity-merge-v1.json`
- `schemas/commands/identity-merges-v1.json`
- `schemas/commands/identity-unmerge-v1.json`
- `schemas/llm/assessment-explanation-v2.json`
- `adapters/reporting/work_assessment_csv.py`

修改：

- `adapters/reporting/work_assessment_markdown.py`：按 schemaVersion 分派 v1/v2。
- `adapters/reporting/markdown.py`：保持 reportType 分派，传递 v2。
- `application/services/assessment_explanation.py`：使用 v2 allowlist。
- `src/git_contribution_analyzer/prompts/assessment/v2/explanation.txt`：不包含 ranking 数据。

CSV 使用 `utf-8-sig`，换行使用 `\r\n`，字段顺序固定。

## 6. 文件影响清单

### 6.1 新建文件

| 文件 | 用途 |
|---|---|
| `domain/models/person_selection.py` | 人员选择和排除模型 |
| `domain/models/identity_merge.py` | merge preview/event 模型 |
| `domain/models/ranking.py` | 排名和配置模型 |
| `domain/services/ranking_rules.py` | 确定性排名公式 |
| `application/services/person_selection.py` | selector 解析编排 |
| `application/services/ranking_config.py` | YAML 配置加载和校验 |
| `application/use_cases/preview_identity_merge.py` | merge dry-run |
| `application/use_cases/merge_identities.py` | 执行 merge |
| `application/use_cases/list_identity_merges.py` | merge 历史 |
| `application/use_cases/unmerge_identities.py` | 撤销 merge |
| `adapters/storage/sqlite/identity_merge.py` | merge storage adapter |
| `adapters/storage/sqlite/migrations/versions/0006_identity_merges.py` | 数据库迁移 |
| `adapters/reporting/work_assessment_csv.py` | CSV renderer |
| `src/git_contribution_analyzer/prompts/assessment/v2/__init__.py` | Prompt package |
| `src/git_contribution_analyzer/prompts/assessment/v2/explanation.txt` | v2 解释 Prompt |
| `schemas/work-assessment/v2.json` | v2 正式报告 |
| `schemas/commands/assess-v2.json` | assess envelope |
| `schemas/ranking-config/v1.json` | 权重配置 |
| `schemas/commands/identity-merge-v1.json` | merge envelope |
| `schemas/commands/identity-merges-v1.json` | merge list envelope |
| `schemas/commands/identity-unmerge-v1.json` | unmerge envelope |
| `schemas/llm/assessment-explanation-v2.json` | LLM 解释输出 |
| `tests/unit/test_person_selection.py` | selector 规则 |
| `tests/unit/test_ranking_rules.py` | 排名公式和 ties |
| `tests/unit/test_ranking_config.py` | YAML/权重校验 |
| `tests/integration/test_identity_merge_cli.py` | merge 生命周期 |
| `tests/integration/test_team_selection_cli.py` | 多人选择/排除 |
| `tests/integration/test_assessment_ranking_cli.py` | 排名 CLI/Schema |
| `tests/integration/test_work_assessment_csv.py` | CSV 重放和隐私 |

### 6.2 修改文件

| 文件 | 修改内容 |
|---|---|
| `pyproject.toml` | 开发版本切换到 `0.2.0.dev0` |
| `uv.lock` | 同步项目版本 |
| `src/git_contribution_analyzer/__init__.py` | 同步版本 |
| `cli/app.py` | 新参数和身份命令 |
| `domain/models/work_assessment.py` | Person 聚合输入 |
| `application/use_cases/assess_work.py` | selection、v2、ranking |
| `application/use_cases/generate_report.py` | CSV/include-email |
| `application/services/assessment_explanation.py` | v2 allowlist |
| `adapters/storage/sqlite/models.py` | Person 状态和 merge event |
| `adapters/storage/sqlite/git_index.py` | list/map 兼容 |
| `adapters/storage/sqlite/analysis.py` | selection 和 redirect |
| `adapters/reporting/markdown.py` | v2 分派 |
| `adapters/reporting/work_assessment_markdown.py` | v2 排名表 |
| `tests/integration/test_assessment_cli.py` | v1 断言迁移和兼容 |
| `tests/integration/test_run_types.py` | 0006 和 v2 run |
| `tests/helpers/golden_repository.py` | 增加身份 alias/合并场景 |
| `tests/e2e/test_dual_track_golden_lifecycle.py` | 团队评估/CSV 生命周期 |
| `README.md`、`README.zh-CN.md` | 新 CLI 和排名边界 |
| `doc/cli/cli-reference.md`、`doc/zh-CN/cli-reference.md` | 命令参考 |
| `doc/guides/methodology.md`、`doc/zh-CN/methodology.md` | 排名公式和限制 |
| `doc/guides/privacy.md`、`doc/zh-CN/privacy.md` | CSV/身份合并隐私 |
| `doc/architecture/data-model.md`、`doc/zh-CN/data-model.md` | 0006 和表结构 |
| `CHANGELOG.md` | 0.2.0 开发变更 |

## 7. 实施阶段

### 阶段 0：兼容基线和 v2 骨架

目标：在不改变现有行为的前提下建立版本和 Schema 基础。

RED：

- 新增版本测试，期望 `0.2.0.dev0`。
- 新增 v1 历史 fixture replay 测试。
- 新增 `work-assessment/v2` Schema 契约测试，初始失败。

GREEN：

1. 更新项目版本。
2. 新增 v2 Schema，selection/ranking 使用 disabled 空结构。
3. 修改 renderer 支持读取 v1/v2。
4. 新 assess run 输出 v2；历史 run 不变。

验收：

- v1 golden JSON/Markdown 无变化。
- v2 no-ranking 报告通过 Schema。
- 121+ 现有测试无回归。

预计工作量：2-3 工程日。

### 阶段 1：多人包含与排除

目标：按用户要求优先交付人员范围控制。

RED 测试：

- 两个 `--person` 返回两个 subjects。
- selector 顺序不同 Snapshot ID 相同。
- 重复 selector 解析同一 Person 失败。
- `--all --exclude-person` 正确排除。
- `--exclude-person` 与显式 `--person` 组合失败。
- 未确认/BOT 默认排除并记录 reason。
- 空 cohort 不创建 run。
- 排除在 load_commits 前完成（mock/spy）。

GREEN：

1. 实现 PersonSelection 模型和服务。
2. 增加 storage 批量 resolver。
3. 修改 CLI 参数。
4. 修改 assess_work 使用 selection。
5. 将 selection 写入 parameters_json 和 v2 report。

IMPROVE：

- 提取稳定 selector normalization。
- 人类输出增加 included/excluded 数量。
- 更新中英文 CLI 文档。

验收：FR-01、FR-02、FR-03 全部通过。

预计工作量：3-4 工程日。

### 阶段 2：可逆身份合并的数据层

目标：建立不删除历史 Person 的 merge 基础。

RED 测试：

- 0005 -> 0006 upgrade 默认 active=true。
- ACTIVE event 阻止 downgrade。
- 无 event 时 0006 -> 0005 downgrade 成功。
- dry-run 无写入。
- merge 事务移动 aliases、保留 Person、保留历史 run。
- 中途异常完整回滚。
- redirect 解析稳定，循环 redirect 被拒绝。

GREEN：

1. 新增 migration/models。
2. 实现 identity_merge storage adapter。
3. 实现 preview/merge/list/unmerge use cases。
4. 重构 map_identity 使用 alias reassignment primitive。

IMPROVE：

- 对 JSON 快照采用 canonical serialization。
- 增加 event 查询 indexes。
- 所有数据库错误映射为稳定 Workspace/Identity error。

验收：FR-04 至 FR-07 的数据和用例层通过。

预计工作量：4-6 工程日。

### 阶段 3：身份合并 CLI 和黄金生命周期

目标：让用户安全操作 merge/unmerge。

RED 测试：

- merge 缺少 dry-run/yes 失败。
- source/target 冲突、重复、kind 不符失败。
- dry-run JSON 通过 Schema。
- merge 后 identities list 显示 redirect。
- merge 后新 assess 合并贡献。
- 历史 assess report 不变。
- unmerge 后新 assess 恢复归属。
- alias 被后续 remap 时 unmerge 事务失败。

GREEN：

1. 新增 Typer 子命令。
2. 新增 command Schemas。
3. 扩展 identities human/JSON 输出。
4. 扩展黄金仓库 identity 场景。

IMPROVE：

- dry-run 人类输出按 source 分组。
- unmerge 错误提供冲突 alias ID。
- 更新隐私和数据模型文档。

验收：完整 merge CLI 生命周期跨平台通过。

预计工作量：3-4 工程日。

### 阶段 4：多维排序

目标：交付透明的 workload/difficulty/delivery 排名。

RED 测试：

- size/difficulty 点值映射。
- completed only 计分。
- duplicate/noise 不重复。
- rework penalty 和 30% 上限。
- dense ties。
- raw value 跨平台四位小数一致。
- 排名启用/禁用 Schema。
- LLM Provider 输入不含 score/rank。

GREEN：

1. 实现 ranking models/rules。
2. 增加 `--rank-by`。
3. 将 ranking 写入 v2 result_json。
4. Markdown 增加多维排名表。
5. 实现 assessment-explanation-v2。

IMPROVE：

- 提取 Person aggregate builder。
- Evidence IDs 去重并排序。
- 排名限制说明进入 report limitations。

验收：FR-09、FR-10、FR-13 通过。

预计工作量：4-5 工程日。

### 阶段 5：权重总分

目标：通过显式配置生成可审计 composite score/rank。

RED 测试：

- 权重缺失、额外字段、负数、总和非 1 失败。
- cohort-max normalization。
- max=0 处理。
- Decimal 四位小数。
- total ties 和稳定排序。
- cohort fingerprint 对 selector 顺序不敏感，对权重变化敏感。
- 无 config 时不出现 total score。

GREEN：

1. 新增 config Schema/Pydantic loader。
2. 实现 normalization 和 composite。
3. 增加 CLI `--ranking-config`。
4. 将规范配置和 fingerprint 写入报告。

IMPROVE：

- 配置错误包含 JSON path。
- 人类输出展示公式版本和权重。
- 文档明确 cohort 分数不可跨范围比较。

验收：FR-11 通过。

预计工作量：3-4 工程日。

### 阶段 6：CSV 导出和报告重放

目标：从持久化 v2 run 输出可用表格。

RED 测试：

- CSV UTF-8 BOM、CRLF 和固定 header。
- 默认无 email。
- include-email 显式输出。
- total rank/第一 rank-by 排序。
- 逗号、引号、中文名称正确 escaping。
- v1 run 请求 CSV 明确失败。
- 导出不调用 Git。

GREEN：

1. 实现 CSV renderer。
2. 扩展 generate_report 和 CLI。
3. Markdown v2 排名表完善。
4. JSON/CSV golden fixture。

IMPROVE：

- CSV gaps 使用稳定分隔符。
- 文档提供 Excel/LibreOffice 打开说明。

验收：FR-12 通过。

预计工作量：2-3 工程日。

### 阶段 7：E2E、性能、隐私和发布就绪

目标：完成 0.2.0 候选验收。

任务：

1. 黄金生命周期加入多人选择、merge/unmerge、ranking、CSV。
2. 15,000 commit 基准测 selector 过滤和 ranking 开销。
3. 检查 CSV/Markdown 邮箱和排除人员泄漏。
4. 升级/降级数据库 smoke。
5. 更新 README、中英文 CLI、methodology、privacy、data model、CHANGELOG。
6. Wheel、pipx、三平台 standalone 生命周期。
7. Gitleaks、Ruff、mypy、全量覆盖率。

验收：

- 全项目覆盖率 >=80%，Domain/Application 新代码 >=90%。
- Windows/Linux/macOS × Python 3.12/3.13 CI 全绿。
- Release workflow 三平台全绿。
- 无 tracked 私有邮箱、本机路径或真实团队排名报告。
- `0.2.0.dev0` 在正式制品审核前不改为 `0.2.0`。

预计工作量：3-4 工程日。

## 8. 测试策略

### 8.1 单元测试

`test_person_selection.py`：

- selector ID/email/name 解析。
- 名称歧义。
- redirect。
- include/exclude 冲突。
- stable canonical selection。

`test_ranking_rules.py`：

- size/difficulty 映射。
- delivery penalty。
- dense rank。
- normalization。
- composite 和 fingerprint。
- Decimal rounding。

`test_ranking_config.py`：

- YAML/Schema/Pydantic 错误。
- 权重和。
- extra forbidden。
- canonical JSON。

### 8.2 集成测试

`test_team_selection_cli.py`：

- repeated person。
- all/exclude。
- empty cohort。
- v2 Schema。

`test_identity_merge_cli.py`：

- dry-run -> merge -> list -> assess -> unmerge -> assess。
- 历史 run replay。
- transaction rollback。
- map compatibility。

`test_assessment_ranking_cli.py`：

- multi-rank。
- config composite。
- no LLM mutation。
- fallback。

`test_work_assessment_csv.py`：

- persisted run export。
- privacy。
- Unicode/escaping。

### 8.3 E2E

黄金仓库完整路径：

```text
init -> identities list
     -> assess explicit multiple
     -> assess all/exclude
     -> merge dry-run/execute
     -> assess merged cohort
     -> rank dimensions/composite
     -> report json/markdown/csv
     -> unmerge
     -> replay pre-merge and post-merge runs
```

### 8.4 覆盖率和静态检查

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m pytest --cov=git_contribution_analyzer
.\.venv\Scripts\python.exe -m build
```

## 9. 迁移和兼容策略

### 9.1 Upgrade

- 打开工作区自动从 0005 升级 0006。
- 所有现有 Person active=true。
- 历史 run/result_json 不修改。
- 新 assess run 使用 v2。

### 9.2 Downgrade

- 无 ACTIVE merge event 时允许 0006 -> 0005。
- 存在 ACTIVE event 时阻止 downgrade，要求先执行 unmerge 并备份数据库。
- v2 run 不删除；降级应用可能无法渲染 v2，因此代码回滚前必须确认无 v2 run，或继续使用
  具备 v2 reader 的兼容修复版本。

### 9.3 Schema

- v1 文件和 golden fixture 永久保留。
- v2 只通过新文件发布，不原地修改 v1。
- Prompt/LLM Schema 同样使用 v2 新目录。

## 10. 回滚策略

### 10.1 阶段 1 回滚

- 恢复单 person CLI；v2 reader 保留，避免新 run 无法读取。
- selection 参数仍保存在历史 run，不删除。

### 10.2 身份合并回滚

- 先执行 `identities unmerge` 撤销所有 ACTIVE event。
- 备份 `.gca/index.sqlite`。
- 执行 Alembic downgrade 0005。
- 不使用手工 SQL 直接移动 alias。

### 10.3 Ranking 回滚

- 停止生成 ranking，但保留 v2 renderer。
- 已持久化 ranking result_json 保持可读。
- 不重算或删除历史 score。

### 10.4 CSV 回滚

- 移除 CSV CLI 暴露，但保留历史 JSON/Markdown。
- CSV 是派生输出，不影响数据库。

## 11. 风险和缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| 错误身份合并 | 高 | dry-run、显式 yes、事务、event、unmerge |
| 合并后历史 run 归属混乱 | 高 | 不删除 Person、不改历史 result_json |
| 排名被当作最终绩效 | 高 | 多维默认、总分显式配置、limitations |
| 权重掩盖原始事实 | 高 | 输出 raw/normalized/weight/weightedValue |
| Cohort 改变导致分数漂移 | 中 | cohort fingerprint、禁止跨 cohort 比较声明 |
| CSV 泄漏邮箱 | 高 | 默认无邮箱、显式 include-email、隐私测试 |
| v1 客户端回归 | 高 | v1 Schema/fixture/renderer 冻结 |
| SQLite self-FK 迁移复杂 | 中 | merged_into 使用逻辑引用和应用校验 |
| LLM 改写排名 | 高 | Provider context 排除 ranking，结果只写 explanation |
| 大团队性能下降 | 中 | selector 先过滤、批量查询、基准门禁 |

## 12. 完成定义

- [ ] 重复 `--person` 和 `--all --exclude-person` 全部可用。
- [ ] selection 写入 v2 report，Snapshot 对 selector 顺序稳定。
- [ ] merge dry-run/execute/list/unmerge 全部可用。
- [ ] 合并不删除 Person、不改写历史 run。
- [ ] map 命令兼容并使用可撤销事件。
- [ ] v1 历史报告无变化且可重放。
- [ ] workload/difficulty/delivery 多维 dense ranking 可用。
- [ ] 权重配置可选，所有计算透明且带版本。
- [ ] LLM 不接触或修改任何排名字段。
- [ ] CSV 从持久化 v2 run 导出，默认不含邮箱。
- [ ] 0005/0006 upgrade/downgrade 测试通过。
- [ ] 黄金 E2E 覆盖筛选、合并、排名和 CSV。
- [ ] Domain/Application 新代码覆盖率 >=90%，全项目 >=80%。
- [ ] Windows/Linux/macOS CI 和 release workflow 全部通过。
- [ ] 中英文文档、CHANGELOG 和隐私边界同步。

## 13. 实施顺序

严格按阶段 0 -> 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 执行。

用户优先级对应：

1. 阶段 1：多人指定/排除。
2. 阶段 2-3：可逆身份合并。
3. 阶段 4：多维排序。
4. 阶段 5：可选权重总分。
5. 阶段 6：CSV 表格导出。

任何阶段如果需要修改已冻结的 v1 Schema、删除历史 Person、让 LLM 影响分数，必须先更新提案和
本实施方案，不能直接进入实现。

