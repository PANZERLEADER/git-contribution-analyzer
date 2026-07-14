# 提案：多人筛选、身份合并与工作评估排序

## 1. 需求摘要

GCA 需要在现有工作评估能力上增加三个按优先级推进的功能：

1. 整体评估支持指定多个用户，或从全部用户中排除指定用户。
2. 支持通过 CLI 将多个 Git 身份合并为现实中的同一个 Person，并保留审计与撤销能力。
3. 工作评估支持按维度排序、可配置权重总分，以及从持久化 run 导出表格。

### 1.1 功能需求

- `--person` 可以重复传入，选择多个 Person。
- `--all` 可以与重复的 `--exclude-person` 组合。
- 选择器支持规范名称、规范邮箱和 Person ID；有歧义时明确失败。
- 排名默认只包含已确认的 `HUMAN` Person。
- 身份合并必须事务化，不能改写历史分析 run。
- 身份合并支持预览、确认、审计和撤销。
- 排名必须由确定性、带版本的规则计算，LLM 不参与分数或名次。
- 输出至少支持 JSON、Markdown 和 CSV；表格应能从已持久化 run 重建。
- 支持多维排序和可选的权重总分。

### 1.2 非功能需求

- 兼容性：已发布的 `work-assessment/v1` 和历史 run 保持可读。
- 可审计：人员范围、排除原因、身份合并和排名公式均可回溯。
- 可重复：相同 Snapshot、选择范围、规则版本和权重配置产生相同结果。
- 隐私：CSV/Markdown 默认不输出邮箱，可通过显式选项允许内部导出。
- 性能：人员筛选在读取 commit 前完成；不为被排除人员构建 SnapshotSubject。
- 可维护性：筛选、身份归属、排名和渲染保持独立边界。

## 2. 当前状态

### 2.1 人员列表

当前已经提供：

```powershell
gca identities list <repo>
gca identities list <repo> --json
gca identities list <repo> --unresolved --json
```

输出包含 Person ID、规范名称、规范邮箱、类型、确认状态和 aliases。实现位于：

- `application/use_cases/list_identities.py`
- `adapters/storage/sqlite/git_index.py#list_identities`
- `cli/app.py#identities_list_command`

### 2.2 身份映射

`gca identities map` 已能把一个 alias 移动到指定规范邮箱对应的 Person。重复执行该命令，可以将
多个 alias 指向同一 Person，但存在以下不足：

- 命令表达的是单 alias 映射，不是 Person 合并。
- 没有批量预览和冲突检查。
- 没有合并事件记录和撤销命令。
- 当前实现可能删除没有剩余 alias 的旧 Person；若旧 Person 已被历史 run 引用，兼容风险较高。
- 用户无法清晰区分“修改规范名称”和“合并两个现实身份”。

### 2.3 整体工作评估

当前 `gca assess` 只允许：

```powershell
gca assess <repo> --person <one-person>
gca assess <repo> --all
```

`--person` 与 `--all` 互斥，没有多选和排除参数。`WORK_ASSESSMENT v1` 明确不包含 ranking 或
score，现有集成测试也固定了该行为。

## 3. 排名边界

排名可以作为团队复盘和绩效输入，但不能把 Git 数据包装成绝对员工价值。新功能需要区分：

- 多维排序：按照可解释的单一维度排序，默认提供。
- 综合总分：按照用户显式配置的权重计算，默认关闭。
- 最终绩效结论：仍需人工结合业务结果、共同所有权和 Git 外部证据。

以下指标不得直接作为默认排名依据：

- commit 数量；
- 原始新增/删除行数；
- 在线时长或提交时间分布；
- LLM 生成的能力描述；
- 未验证的业务成果。

## 4. 方案一：最小扩展现有 `assess`

### 4.1 概述

直接将 `--person` 改为可重复参数，增加 `--exclude-person`、`--rank-by` 和 `--format csv`，继续
使用现有 identity map 和 `WORK_ASSESSMENT v1`。

### 4.2 CLI 示例

```powershell
gca assess <repo> --person alice@example.com --person bob@example.com --no-llm
gca assess <repo> --all --exclude-person ci@example.com --rank-by workload --json
```

### 4.3 优点

- 改动范围小，交付速度快。
- 用户学习成本低。
- 可以复用现有 Snapshot 和报告结构。

### 4.4 缺点

- 给已发布 v1 Schema 增加 ranking 字段会破坏版本语义。
- 身份合并继续依赖多次 map，没有完整审计和撤销。
- 筛选、团队比较和个人评估继续混在同一用例中。
- CSV 直接从命令临时输出，难以从历史 run 稳定重放。

复杂性：低。

风险：中高。

工作量：小到中。

## 5. 方案二：版本化团队评估与可逆身份合并

### 5.1 概述

保持 `gca assess` 作为工作评估入口，但引入明确的人员范围模型、可逆 Person merge、
`work-assessment/v2` 和独立排名规则。CSV 通过 `gca report` 从持久化 run 导出。

这是推荐方案。

### 5.2 多人选择

```powershell
# 指定多人。
gca assess <repo> `
  --person alice@example.com `
  --person bob@example.com `
  --no-llm `
  --json

# 全部已确认 HUMAN，排除指定人员。
gca assess <repo> `
  --all `
  --exclude-person ci@example.com `
  --exclude-person former-member@example.com `
  --no-llm `
  --json
```

选择规则：

1. `--person` 可重复；一个参数时保持现有个人评估兼容行为。
2. `--all` 与 `--person` 互斥。
3. `--exclude-person` 只允许与 `--all` 组合，避免“同时包含又排除”的不透明优先级。
4. 排名模式默认只接受 confirmed `HUMAN`；未确认或非 HUMAN 身份进入 warnings。
5. 所有 selector 在创建 run 前解析，报告记录 selected/excluded Person ID 和排除原因。

领域模型建议：

```text
PersonSelection
  mode: EXPLICIT | ALL
  includedPersonIds
  excludedPersonIds
  confirmedOnly
  allowedKinds
  selectionWarnings
```

### 5.3 身份合并

建议增加：

```powershell
# 预览多个 source Person 合并到 target Person。
gca identities merge <repo> `
  --source <person-id-or-email> `
  --source <person-id-or-email> `
  --target <person-id-or-email> `
  --dry-run `
  --json

# 执行合并。
gca identities merge <repo> `
  --source <person-id-or-email> `
  --target <person-id-or-email> `
  --yes `
  --json

# 查看和撤销合并。
gca identities merges <repo> --json
gca identities unmerge <repo> --merge-id <id> --yes --json
```

数据库迁移建议新增：

```text
persons
  merged_into_person_id nullable
  active boolean

identity_merge_events
  id
  repository_id
  target_person_id
  source_person_ids_json
  moved_alias_ids_json
  status
  created_at
  reverted_at nullable
```

合并语义：

- 移动 source Person 的 alias 到 target Person。
- 不删除 source Person；将其标为 inactive，并设置 redirect。
- 历史 run 继续引用原 Person 和原 result JSON，不做重写。
- 新 run 将 source selector 解析到 target，并输出 redirect warning。
- 撤销只恢复该 merge event 记录的 alias，不覆盖合并后新增的人工映射。
- `--dry-run` 输出 alias 数、历史 run 数、冲突和最终规范身份。

### 5.4 多维排序

默认支持以下排序维度：

| 维度 | 默认依据 | 说明 |
|---|---|---|
| `workload` | 已完成事项的 size points | 衡量有效变更范围，不代表工时 |
| `difficulty` | 已完成事项的 difficulty points | 衡量工程挑战信号，不代表业务价值 |
| `delivery` | completed、rework 和 pending 的版本化规则 | 返工扣减必须有上限 |
| `business` | 人工 verified outcomes | 缺失时标记 N/A，不按零分处理 |

建议的基础点值必须带版本，并写入报告：

```yaml
ruleVersion: performance-ranking-v1
sizePoints:
  SMALL: 1
  MEDIUM: 3
  LARGE: 6
  XLARGE: 10
difficultyPoints:
  ROUTINE: 1
  STANDARD: 2
  COMPLEX: 4
  HIGH_RISK: 6
delivery:
  reworkPenaltyRatio: 0.15
  maxReworkPenaltyRatio: 0.30
```

默认只输出各维度原始点值、名次和并列关系，不自动产生综合总分：

```powershell
gca assess <repo> --all --rank-by workload --rank-by difficulty --json
```

### 5.5 可选权重总分

综合总分需要显式权重文件：

```yaml
schemaVersion: "1.0"
rankingRuleVersion: performance-ranking-v1
weights:
  workload: 0.45
  difficulty: 0.35
  delivery: 0.20
  business: 0.00
normalization: cohort-max
ties: dense
```

```powershell
gca assess <repo> --all `
  --ranking-config team-ranking.yml `
  --json
```

规则：

- 权重之和必须为 `1.0`。
- 每个维度先在本次 cohort 内归一化为 `0-100`，报告保存 cohort fingerprint。
- 缺失业务 outcome 时，`business` 权重必须为 `0`，否则命令失败。
- 使用 dense ranking；相同总分和相同分项分数并列。
- 报告同时输出 raw、normalized、weight、weightedValue，不能只输出最终分数。
- LLM 不参与 raw value、normalization、weight 或 rank。

### 5.6 表格导出

排名应先持久化到 run，再由报告命令导出：

```powershell
gca report <repo> --run latest --format csv --output team-assessment.csv
gca report <repo> --run latest --format markdown --output team-assessment.md
gca report <repo> --run latest --format json --output team-assessment.json
```

CSV 建议字段：

```text
rank,personId,personName,workloadScore,difficultyScore,deliveryScore,
businessScore,totalScore,completedItems,reworkItems,confidence,gaps
```

邮箱默认不导出；内部使用时可增加显式 `--include-email`。

### 5.7 Schema 和兼容性

- 保留 `schemas/work-assessment/v1.json` 不变。
- 新增 `schemas/work-assessment/v2.json`，增加 selection、rankings 和 rankingConfig。
- 新增 `schemas/ranking-config/v1.json`。
- 历史 v1 run 使用旧 renderer；v2 run 支持 CSV renderer。
- `scopeType` 继续支持 `PERSON` 和 `PROJECT`；多人显式选择属于 `PROJECT`。

### 5.8 优点

- 满足三个需求，同时保留 v1 历史兼容。
- 身份合并可审计、可撤销，不破坏历史报告。
- 多维排名默认透明，综合总分必须显式配置。
- CSV 从持久化 run 重放，便于团队归档和复核。
- 能按阶段独立交付，不要求一次上线全部功能。

### 5.9 缺点

- 需要数据库迁移、Schema v2 和新 renderer。
- 权重总分需要团队明确价值判断，无法由 GCA 自动决定。
- Cohort 归一化使不同人员范围的总分不能直接横向比较。

复杂性：中高。

风险：中。

工作量：中到大。

## 6. 方案三：独立 Team Comparison 子系统

### 6.1 概述

保持 `gca assess` 完全不变，新增 `gca compare`、`TEAM_COMPARISON` run type、独立 Schema、
权重策略和 Excel/CSV 导出。

### 6.2 优点

- 团队排名与个人工作评估边界最清晰。
- 可以独立演进权限、业务 outcome 和更多组织指标。
- 不需要改变 `WORK_ASSESSMENT` 的无排名语义。

### 6.3 缺点

- 与 `assess --all` 产生较多重复模型和用例。
- 用户需要理解 analyze、assess、compare 三个相邻入口。
- 初期开发和维护成本最高。

复杂性：高。

风险：中。

工作量：大。

## 7. 比较矩阵

| 标准 | 方案一：最小扩展 | 方案二：版本化团队评估 | 方案三：独立 Compare |
|---|---|---|---|
| 多人包含/排除 | 支持 | 支持 | 支持 |
| 身份合并审计/撤销 | 弱 | 完整 | 完整 |
| v1 兼容性 | 较差 | 最佳 | 最佳 |
| 多维排名 | 基础 | 完整 | 完整 |
| 权重总分 | 简化 | 显式配置 | 策略化 |
| CSV 重放 | 较弱 | 完整 | 完整 |
| CLI 一致性 | 最佳 | 良好 | 一般 |
| 实施复杂性 | 低 | 中高 | 高 |
| 长期维护性 | 一般 | 最佳 | 良好 |

## 8. 推荐方案

推荐方案二：版本化团队评估与可逆身份合并。

理由：

1. 用户需求仍然属于工作评估领域，没有必要立即增加第三条顶层产品流水线。
2. `work-assessment/v2` 可以保持 v1 不变，同时引入人员范围和排名。
3. 身份合并必须优先解决历史 run 和 alias 可逆性，不能只增加一个批量 update 命令。
4. 默认多维排序满足透明比较；可选权重文件满足需要总分的团队，但不会把组织价值判断硬编码到 GCA。
5. CSV 通过 `gca report` 导出，符合现有“分析一次、持久化、重复渲染”的架构。

## 9. 推荐实施顺序

### 阶段 1：多人包含与排除

- `--person` 改为可重复。
- 增加重复 `--exclude-person`。
- 新增 `PersonSelection` 和选择审计字段。
- 保持无 ranking 的现有输出。

验收：多人显式选择、全员排除、歧义/重叠/空 cohort 错误和未确认身份警告全部通过。

### 阶段 2：可逆身份合并

- 新增数据库迁移和 merge event。
- 新增 `identities merge/merges/unmerge`。
- 历史 run 不改写，新 run 使用 redirect 后身份。

验收：dry-run、事务回滚、历史 run 重放、合并后新分析和撤销均通过。

### 阶段 3：多维排序和 CSV

- 新增 `work-assessment/v2`。
- 实现 workload/difficulty/delivery 排序和 dense ties。
- 新增 CSV renderer。

验收：同一 cohort 排名稳定，排序字段和 Evidence 可审计，CSV 可从历史 run 重建。

### 阶段 4：可选权重总分

- 新增 ranking config Schema。
- 实现归一化、权重校验、综合总分和业务 outcome 边界。
- 更新方法论、隐私和中文文档。

验收：权重和为 1、缺失业务 evidence、并列、cohort fingerprint 和可重复性测试通过。

## 10. 版本建议

该功能改变团队评估语义和 Schema，建议作为 `0.2.0` 开发，不回写或移动已发布的 `v0.1.0`。

