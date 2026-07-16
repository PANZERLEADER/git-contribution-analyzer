# 提案：GCA 历史结构难度证据优化（修订版）

## 1. 决策摘要

本提案建议采用**方案二：版本化原始计数缓存与按基线物化**，在 GCA 现有 Python、SQLite、
domain/application/adapters 分层内建立历史结构基线。

本次只借鉴 Hercules 中与工作事项结构上下文直接相关的两类思想：

1. 文件长期共同变更形成的历史结构关联；
2. 文件长期变更频率形成的历史热点。

这两类结果首先是派生信号，不是新的排名维度，也不自动等同于工作难度。它们只有通过预先定义的
人工校准与稳定性门槛后，才允许在新的 `difficulty-rules-v2` 中将 `STANDARD` 工作事项最多提高到
`COMPLEX`。如果质量门槛未通过，结果继续保持 observation-only，不进入 assessment 或 ranking。

推荐方案同时满足以下约束：

- 历史基线严格早于评估周期，避免未来信息泄漏和个人活跃度循环归因；
- 原始文件计数和所有非零稀疏边可增量维护，阈值只用于物化和输出；
- percentile、热点、耦合强度等派生值按不可变 baseline 统一计算；
- lifetime、rolling-window 和可选 decay 只作为 benchmark 候选，不预设时间衰减算法；
- ranking 继续只消费 workload、difficulty 和 delivery，不读取 raw structural signals；
- Hercules 仅作为资料和开发期交叉验证参照，不成为运行时、安装或发布依赖；
- 历史 run 不回写，旧规则和旧报告继续可重放。
- Git trailer 只保留为待覆盖率验证的本地声明式角色 Evidence 候选，不进入本提案；
- Forge evidence、独立项目健康分析和 AI provenance 不进入 GCA 当前产品路线图。

## 2. 问题与目标

### 2.1 当前问题

GCA 当前已经具备确定性的 workload、difficulty、delivery、ranking、Evidence、身份映射和交付
时间口径。现有 `structural-signals-v1` 还能够从当前筛选范围内生成重复文件共同变更和结构热点。

但是，当前结构信号不能直接进入 difficulty：

1. 个人报告使用个人当前范围内的提交，高活跃者天然产生更多热点和边，存在循环归因；
2. 当前范围可能包含被评估周期，造成未来信息泄漏和自我强化；
3. `changeCommits + coChangeCommits` 只是展示排序值，没有跨仓库或跨周期语义；
4. 每次个人、项目和周期报告都重新计算相同事实，无法复用；
5. raw `MULTI_MODULE` 同时影响 workload 和 difficulty，存在重复计分；
6. 仅持久化“已经达到阈值”的边无法正确增量累计未来可能跨过阈值的低频边；
7. percentile 会随全仓库分布变化，不能被当作只追加更新的原始事实。

### 2.2 功能目标

- 从评估周期之前的全仓库历史构建版本化结构基线；
- 生成文件变更计数、热点分位、共同变更计数和耦合强度；
- 识别工作事项对历史热点和强耦合边的暴露；
- 支持个人、团队、项目、周期序列和 GUI/CLI 复用同一基线；
- 支持默认分支新增提交的增量维护；
- 支持任意历史 cutoff 的不可变重建与缓存；
- 为每个结果保留 baseline、规则、阈值、命中路径和 Evidence；
- 只有在质量门槛通过后才启用 `difficulty-rules-v2` 接入；
- 修正 `MULTI_MODULE` 在 workload 与 difficulty 之间的重复使用。

### 2.3 非功能目标

- **确定性**：相同 Git 基线、cutoff、过滤器和规则版本产生相同 canonical 结果；
- **防泄漏**：当前评估周期及之后的提交不得进入其历史结构基线；
- **增量正确性**：低频边必须能够在后续 sync 中正确跨过候选阈值；
- **可重放**：历史 assessment 读取持久化结果，不因新算法上线而静默重算；
- **性能**：多人和多周期分析不得重复扫描相同历史；
- **空间边界**：不分配完整 `F x F` 矩阵，不复制每条边的完整 commit hash 集合；
- **可取消**：冷构建、重建和大规模增量任务遵守现有 progress/cancellation port；
- **本地优先**：默认不上传源码、路径、人员关系或结构矩阵；
- **跨平台**：Windows、Linux、macOS 的 CLI、GUI、wheel 和 standalone 行为一致；
- **可替换性**：domain 不直接读取 Git、SQLite、YAML、LLM 或 GUI 状态。

## 3. 当前状态与研究依据

仓库当前没有 `doc/research/` 目录。本提案以以下实现和文档为代码库事实来源：

- `doc/architecture/architecture.md`：分层、EvidenceSnapshot、运行边界和历史 run；
- `doc/architecture/data-model.md`：Git index、analysis run 和可重建数据边界；
- `doc/guides/methodology.md`：workload、difficulty、delivery、ranking 和时间口径；
- `src/git_contribution_analyzer/domain/services/structural_signals.py`：当前组合算法；
- `src/git_contribution_analyzer/domain/services/workload_rules.py`：有效 churn 与模块跨度；
- `src/git_contribution_analyzer/domain/services/difficulty_rules.py`：当前 difficulty signals；
- `src/git_contribution_analyzer/domain/services/ranking_rules.py`：三维排名；
- `src/git_contribution_analyzer/adapters/storage/sqlite/`：现有 SQLite Git index 和 run 存储。

外部方法论参考：

- Hercules README、pipeline 文档以及固定提交
  `68bb211faaedeffb53e799ab89e2aa48d8cb0ad3` 的 couples、burndown 和 shotness 实现；
- Todoctor 的技术债对象生命周期；
- Gitcolombo 的来源分级和 Git trailer 角色证据；
- GitVoyant 的时间序列复杂度与样本置信度；
- git-forks-analysis 的未合并候选证据；
- git-pulse 的 PR/Issue 存量与流量；
- Lucidity MCP 的独立 LLM 审查层；
- LumenCode 的显式 AI provenance event。

后七类概念用于检验 GCA 的产品边界，不进入本提案。调研后的产品结论是：

- Git trailer 与本地、Evidence-first 的方向部分匹配，但必须先验证目标仓库覆盖率；即使未来采用，
  也只生成提交中声明的角色 Evidence，不自动合并 Person，不复制 workload，不改变 difficulty、
  delivery 或 ranking；
- Forge evidence 依赖特定托管平台、网络、权限和外部可变数据，不适合作为面向任意本地 Git 仓库的
  GCA 核心能力；
- 独立项目健康分析评价的是仓库整体状态，与 GCA 评估个人贡献的核心目标不一致；本提案的 repository
  baseline 仅为个人工作事项提供统一 difficulty 上下文，不构成项目健康评分或仪表盘；
- AI provenance 不能稳定说明人的工作量、难度、验证投入或个人价值，不具有足够的个人评估意义；
- 技术债生命周期、fork 网络、独立 LLM 审查等方向同样不进入当前产品路线图。

本地提交 `2076f28 feat: add deterministic structural signals` 已完成阶段 0：

- 从筛选后的 commit facts 计算重复共同变更和热点；
- 排除 merge、generated path、binary-only 和 duplicate patch；
- 在个人和项目 JSON/Markdown 中输出 supporting commit hashes 与 limitations；
- 不改变 assessment、ranking 或 LLM 输入。

## 4. 方法论边界

### 4.1 四层模型

| 层级 | 含义 | 示例 | 是否直接计分 |
|---|---|---|---|
| Git 事实 | 可从提交和 diff 直接观察 | 路径、时间、共同出现、变更类型 | 否 |
| 派生信号 | 对历史事实的版本化归纳 | 热点分位、耦合强度、样本置信度 | 否 |
| 评价维度 | GCA 对工作事项的规范化判断 | workload、difficulty、delivery | 是 |
| 排名 | 对评价维度进行聚合 | 三维排名、显式加权总分 | 是 |

Hercules 提供的是 Git 事实处理和派生信号，不提供可直接移植到 GCA 的 difficulty 或绩效分数。
任何结构结果都必须先通过 GCA 的 Evidence、校准、规则版本和评价边界。

### 4.2 唯一主维度

每个事实或派生信号必须指定唯一主维度：

- churn、有效文件数和模块跨度属于 workload；
- 经过校准的历史热点暴露和强耦合暴露属于 difficulty；
- landed、released、reverted 和明确返工属于 delivery。

同一事实不得在多个维度重复加分。`difficulty-rules-v2` 不再因为
`len(modules) > 1` 单独生成 `MULTI_MODULE` 难度信号。跨模块只在历史基线证明工作事项跨越
强耦合边时，才可能形成结构 difficulty 候选。

### 4.3 不允许的推断

- 共同变更不等同于运行时依赖；
- 热点不等同于低质量代码、高价值代码或高难度工作；
- 文件活跃度不等同于工作时长或个人价值；
- overwrite 不等同于错误、冲突或返工责任；
- ownership/stewardship 不等同于领导力或独占所有权；
- 代码存活时间不等同于工程质量或业务价值；
- 任意结构信号不得直接决定晋升、薪酬或员工价值。

## 5. 信号语义与偏差控制

### 5.1 历史基线边界

结构基线必须：

- 使用符合目标分支口径的全仓库历史，而不是被评估者个人历史；
- 只包含严格早于 `periodStart` 的有效提交；
- 复用 generated、binary、merge、duplicate patch 和路径过滤语义；
- 以 repository、baseline commit、cutoff、filter fingerprint、time strategy 和 rule version
  共同确定 baseline ID；
- 不把人员、团队、cohort 或当前交付状态写入结构 fingerprint；
- 在默认分支改写、force-push、过滤规则变化或索引重建后生成新 baseline，不原地篡改旧 baseline；
- 在样本不足时输出 gap，不推断结构难度。

offset-free 周期边界继续按系统时区解释，查询前转换为 UTC。历史 result JSON 不因结构缓存更新而
改变。

### 5.2 时间策略候选

阶段 1 必须比较以下策略，不预先指定固定半衰期：

| 策略 | 优点 | 风险 |
|---|---|---|
| `LIFETIME` | 稳定、完整、最容易重放 | 可能放大已长期稳定的旧热点 |
| `ROLLING_WINDOW` | 更接近当前维护上下文 | 窗口边界敏感，稀疏仓库样本不足 |
| `DUAL_WINDOW` | 同时保留长期结构和近期活跃度 | 输出和校准更复杂 |
| `DECAYED` | 平滑降低旧历史权重 | 参数解释困难，增量和重放成本更高 |

推荐先以 `LIFETIME` 作为正确性参照，同时把 `ROLLING_WINDOW` 和 `DUAL_WINDOW` 纳入
benchmark。只有验证数据证明 decay 带来稳定收益时才实现 `DECAYED`。

### 5.3 热点候选指标

原始事实：

- `fileChangeCount`：文件在 baseline 中的有效变更提交数。

按 baseline 物化的派生值：

- `fileChangePercentile`：相对当前 baseline 文件分布的变更频率分位；
- 可选 `recentFileChangePercentile`：近期窗口分位；
- `sampleConfidence`：基于有效提交、有效文件和时间覆盖的置信度。

percentile 不是增量原始事实。任一文件计数变化都可能改变全体文件的相对分位，因此必须在 baseline
物化时统一计算或重算。

### 5.4 耦合候选指标

原始事实：

- `changeCount(path)`；
- `coChangeCount(left, right)`。

派生候选：

- `subsetCouplingRatio = coChangeCount / min(changeCount(left), changeCount(right))`；
- `leftConditional = coChangeCount / changeCount(left)`；
- `rightConditional = coChangeCount / changeCount(right)`；
- `jaccard = coChangeCount / (changeCount(left) + changeCount(right) - coChangeCount)`；
- 可选 `lift` 或仓库级高频 hub 惩罚；
- `crossModule`：边是否跨越模块边界。

`subsetCouplingRatio` 适合发现“较少变化的一方几乎总与另一方同时变化”的关系，可以保留为第一
候选；但它可能把每次提交都变化的公共配置文件识别为强耦合。阶段 1 必须用 hub、机械提交和
monorepo fixture 比较 Jaccard、lift 或双条件概率，选择能够控制误报的版本化规则。

### 5.5 工作事项暴露

候选信号：

- `HISTORICAL_HOTSPOT_EXPOSURE`：工作事项命中经过校准的历史热点；
- `HISTORICAL_COUPLING_EXPOSURE`：工作事项跨越满足支持度、强度和 hub 控制条件的历史边。

结果必须包含：

- baseline ID、cutoff、time strategy 和 rule version；
- 阈值和指标版本；
- 命中文件、命中边和模块边界；
- supporting Evidence 引用；
- confidence、gaps 和 limitations。

机械提交、批量生成、rename-only、vendor、lockfile、格式化和超大 context 必须具有版本化排除或
降置信度语义。

## 6. 社区基础配置与自动接入门槛

### 6.1 社区基础配置

GCA 作为开源、本地仓库分析工具，不要求每个使用者先完成主观且难以复现的双人审核。项目提供
`community-baseline-v1` 作为通用保守配置：

- `DUAL_WINDOW`，近期窗口 365 天；
- 最少 50 个历史有效提交；
- hotspot percentile 0.95；
- 最少 3 次共同变更；
- subset ratio 0.80、Jaccard 0.30、hub penalty 0.50；
- 单次 context 最多 100 个有效路径；
- `automaticDifficultyPromotion: false`。

该配置是 observation-only 的产品默认值，不声称对每个仓库都具有统计最优性。项目可以在
`.gca/config.yml` 覆盖阈值，但覆盖只改变结构观察结果，并必须进入 baseline fingerprint。

### 6.2 自动 difficulty 的 Go/No-Go 规则

只有采用者希望让结构信号自动改变个人 difficulty 时，才需要建立 calibration/holdout 数据、双人
独立标注、配置冻结和一次性 holdout 验证。详细实施计划必须在查看 holdout 结果前确定：

- 最低样本覆盖和可接受的误报上限；
- 最低复核者一致性和跨周期稳定性；
- 机械提交、公共 hub 和短历史仓库的专项误报上限；
- `difficulty-rules-v1/v2` 等级分布允许漂移范围。

如果任一自动提升门槛未通过：

- 社区配置和结构结果继续 observation-only 可用；
- 不发布会改变 difficulty 的默认规则；
- ranking 和历史 run 不变；
- 可以继续收集匿名化结果和人工反馈，但不得降低门槛以适配现有输出。

### 6.3 difficulty-rules-v2 约束

只有自动 difficulty 的 Go/No-Go 通过后才允许：

1. 两个信号的唯一主维度为 difficulty；
2. 单一工作事项无论命中多少热点或边，最多提高一个等级；
3. 结构信号只能将 `STANDARD` 提高到 `COMPLEX`；
4. 结构信号不能单独产生 `HIGH_RISK`；
5. 数据迁移、分布式一致性、关键域和兼容性规则保持更高优先级；
6. workload 不因结构信号改变；
7. ranking 不读取 raw structural signals，只读取最终 difficulty level；
8. 缺少有效 baseline 时输出 gap，不回退到个人当前期结构信号；
9. 新规则发布新的 cohort fingerprint，不与 v1 分数跨版本比较。

删除 raw `MULTI_MODULE` 前必须比较 v1/v2 分布，特别验证新仓库和短历史仓库不会系统性低估
difficulty。

## 7. 数据正确性模型

### 7.1 原始计数与派生物化分离

```text
StructuralBaseline
  id / repositoryId / baselineCommit / cutoff
  filterFingerprint / timeStrategy / structuralRuleVersion
  status / eligibleCommitCount / createdAt / completedAt

StructuralFileCount
  baselineId / path / changeCount

StructuralEdgeCount
  baselineId / leftPath / rightPath / coChangeCount

StructuralMaterialization
  baselineId / metricVersion / thresholdVersion
  filePercentiles / candidateEdges / confidence / gaps
```

关键原则：

- `StructuralFileCount` 和 `StructuralEdgeCount` 保存可增量维护的原始计数；
- 所有出现过的非零边均属于稀疏集合 `E`，不能因为尚未达到输出阈值而丢弃；
- 阈值只作用于 materialization、查询和报告；
- percentile、Jaccard、条件概率、hub 惩罚和 confidence 都是可重建派生值；
- supporting commit 明细从现有 Git index 按需回查，不为每条边复制完整 hash 集合；
- materialization 失败不能污染最后一个已完成 baseline。

如果实际仓库的非零边数量仍超过空间目标，必须通过 context 上限、分块、压缩计数或经验证的近似
结构解决，不能静默丢弃低频边后继续宣称严格增量。

### 7.2 增量与失效

默认分支线性前进时：

1. 读取新增的有效非重复提交；
2. 更新受影响文件的 changeCount；
3. 更新每个提交产生的全部非零 edge count；
4. 生成新的不可变 baseline 身份；
5. 重新物化受规则影响的 percentile 和候选边；
6. 原子发布新 baseline。

以下情况不允许盲目增量，必须失效或重建：

- force-push 或默认分支可达集合改写；
- baseline commit 不再可达；
- generated/noise/filter/time strategy/rule version 变化；
- Git index rebuild；
- context 上限或路径模块规则变化；
- 数据库迁移无法证明旧计数语义兼容。

任意历史 cutoff 首次构建后作为不可变缓存复用。默认 HEAD baseline 不能替代更早评估周期要求的
cutoff baseline。

## 8. 提议方案

### 8.1 方案一：按需重建不可变基线

**概述**：每次首次请求某个 cutoff 时，从 SQLite 查询之前的全部有效提交，在内存中构建原始计数
和派生结果；完成后可保存最终 baseline，但不做增量维护。

**实现**：

1. 定义 baseline port、DTO、fingerprint 和 canonical ID；
2. 从现有 Git index 批量读取有效提交与路径；
3. 构建全部非零文件和边计数；
4. 物化候选指标并匹配工作事项；
5. 持久化不可变 baseline 和结果。

**优点**：

- 语义最简单，容易建立正确性参考结果；
- 任意历史 cutoff 都能精确重建；
- 没有增量失效和部分更新问题；
- 适合 fixture、校准和 benchmark。

**缺点**：

- 多人、多周期会重复扫描相同历史；
- 大仓库冷启动和内存不可控；
- 不满足长期默认使用的性能目标；
- GUI 交互体验较差。

**复杂性**：中
**风险**：低到中
**工作量**：中
**定位**：必须实现的正确性参考，不推荐作为最终默认路径。

### 8.2 方案二：版本化原始计数缓存与按基线物化

**概述**：持久化全部非零稀疏原始计数，并为每个不可变 baseline 计算版本化 materialization。
默认分支线性前进时增量更新计数；历史 cutoff 首次构建后复用。

**实现**：

1. 先以方案一建立正确性参考实现、fixture 和校准协议；
2. 增加 baseline、file count、edge count 和 materialization 存储；
3. 实现线性前进增量与分支改写失效；
4. 统一为 CLI、GUI、个人、项目和周期序列提供 application port；
5. 增加 status、rebuild、doctor、清理和容量诊断；
6. 质量门槛通过后再发布 `difficulty-rules-v2`。

**优点**：

- 复用 GCA 现有 SQLite、Git index、锁和 run replay；
- 多人、多周期共享同一结构事实；
- sync 成本主要随新增提交及其有效路径组合增长；
- 原始事实与阈值解耦，可以重新物化而不回扫 Git；
- 能正确处理低频边未来跨阈值；
- 不需要第二语言或跨进程协议。

**缺点**：

- 数据库迁移、原子发布和失效规则更复杂；
- percentile 仍可能需要 baseline 级重算；
- 大型机械提交会产生平方级边，需要明确 context 上限；
- 任意 cutoff 会增加缓存数量，需要容量策略。

**复杂性**：中到高
**风险**：中
**工作量**：大
**定位**：推荐的正式产品路径。

### 8.3 方案三：外部流式分析 worker

**概述**：通过 Hercules 或窄接口 Go/Rust worker 遍历 Git 历史和计算结构结果，GCA 只负责调用、
转换、校准和持久化。

**实现**：

1. 定义稳定的输入、输出、取消和错误协议；
2. 对齐身份、路径、merge、duplicate patch、时间和过滤语义；
3. 构建多平台二进制、安装和 standalone 打包；
4. 与 Python 参考实现做跨实现一致性测试；
5. 维护 worker 版本与 GCA schema compatibility。

**优点**：

- 可能降低大仓库热循环的常数成本；
- 适合流式处理、紧凑内存结构和磁盘 spill；
- 可复用 Hercules 的部分工程经验。

**缺点**：

- Hercules 的现有语义与 GCA 不一致且维护活跃度有限；
- 引入第二语言、跨进程协议和多平台发布复杂度；
- 不能自然复用 GCA 已有 SQLite 派生事实；
- 性能收益在同仓库 benchmark 前不成立；
- 增加供应链、诊断和兼容性风险。

**复杂性**：高
**风险**：高
**工作量**：大
**定位**：仅在方案二通过正确性验证但未达到性能门槛时重新评估。

## 9. 比较矩阵

| 标准 | 方案一：按需重建 | 方案二：计数缓存与物化 | 方案三：外部 worker |
|---|---|---|---|
| 正确性可验证性 | 最好 | 好，需与方案一对照 | 中，存在跨实现语义差异 |
| 冷构建 | 中到慢 | 首次中，后续可复用 | 潜在快，尚无证据 |
| warm 复用 | 有限 | 最好 | 取决于额外缓存设计 |
| 增量正确性 | 不适用 | 好，保留全部非零计数 | 需重新设计协议 |
| 任意 cutoff | 精确但昂贵 | 首次构建后复用 | 取决于 worker |
| SQLite/架构一致性 | 好 | 最好 | 一般 |
| 多平台发布 | 简单 | 简单到中 | 复杂 |
| 运维和诊断 | 简单 | 中 | 复杂 |
| 复杂性 | 中 | 中到高 | 高 |
| 风险 | 低到中 | 中 | 高 |
| 工作量 | 中 | 大 | 大 |
| 推荐结论 | 正确性参考/原型 | 正式路径 | 性能证据不足时暂缓 |

## 10. 推荐方案

推荐**方案二：版本化原始计数缓存与按基线物化**，但实施顺序必须先经过方案一正确性参考实现和
质量校准。

理由：

1. 它解决相同结构事实被个人、项目和周期重复计算的问题；
2. 它保留 GCA 的身份、交付、噪声过滤、系统时区、Evidence 和历史 run 语义；
3. 原始计数与阈值分离后，可以修正规则而不重新读取完整 Git 历史；
4. 保存全部非零边能够保证严格增量，而不只对当前强边增量；
5. 它不引入 Hercules 二进制、Go runtime 或输出转换协议；
6. 如果未来需要第二语言，baseline application port 仍可替换底层实现；
7. quality gate 失败时可以安全停留在 observation-only，不迫使结构信号进入绩效结论。

Hercules 仅作为开发期交叉验证参照：在固定 fixture 上比较共同变更计数、rename/merge 行为和大 context
边界。它不进入安装依赖、CLI 默认路径、GUI、Schema 或发布物。

## 11. 分阶段交付

### 阶段 0：现有观测基线，已完成

- 保留 `structural-signals-v1` 报告字段和限制；
- 明确其描述当前筛选范围，不是历史 difficulty 基线；
- 不改变 assessment、ranking 或 LLM 输入。

### 阶段 1：正确性参考实现、指标实验与社区配置

- 实现方案一的 baseline port、fingerprint、cutoff 和 canonical ID；
- 建立 lifetime、rolling 和 dual-window 对比；
- 比较 subset ratio、双条件概率、Jaccard 和 hub 控制；
- 固化 `community-baseline-v1` 及 observation-only 边界；
- 保留 calibration/holdout 与盲审协议作为自动提升的可选验证路径；
- 对 1 万、10 万提交级仓库记录冷构建、峰值内存和边数量；
- 固化 quality/performance go/no-go 门槛。

### 阶段 2：原始计数缓存与 observation-only 物化

- 增加 baseline、file count、edge count 和 materialization 迁移；
- 保存全部非零稀疏边；
- 实现线性前进增量、force-push 失效和原子发布；
- 增加 status、rebuild、doctor 和容量清理；
- CLI、GUI 和报告继续 observation-only；
- 与方案一逐 baseline 对比 canonical 结果。

### 阶段 3：有条件启用 difficulty-rules-v2

只有采用者明确启用自动提升，且 holdout quality gate 与性能门槛同时通过时：

- 接入两个历史结构 exposure signals；
- 删除 raw `MULTI_MODULE` difficulty 信号；
- 比较并记录 v1/v2 等级分布漂移；
- 发布新的 rule version、schema compatibility 和 cohort fingerprint；
- 保持历史 run 不变。

未通过时，本阶段不实施，阶段 2 仍可独立发布。

### 阶段 4：按性能证据决定是否继续优化

仅在方案二正确但性能不达标时评估：

- SQL 聚合和批处理；
- 更紧凑的计数编码；
- 分块构建与磁盘 spill；
- 经窄协议隔离的 Go/Rust worker。

没有 benchmark 证据时不启动第二语言子系统。

## 12. 验收标准

### 12.1 正确性

- 当前评估周期内提交不得进入其历史 baseline；
- 个人 assessment 使用同一仓库级 baseline，不使用个人提交自建 baseline；
- 相同输入产生相同 baseline ID、原始计数和 canonical materialization；
- 增量结果与同 cutoff 的方案一全量重建逐项一致；
- 一次共同变更的边在后续再次出现后能够正确跨过两次阈值；
- percentile 与同 baseline 的全量分布计算一致；
- force-push、默认分支切换和过滤规则变化不会复用失效计数；
- merge、generated、binary-only、duplicate patch 和超大 context 语义一致；
- `difficulty-rules-v1` 和历史 run 输出不变；
- 单一事实不得同时增加 workload 和 difficulty；
- 缺少 baseline 时不得回退到当前个人结构信号；
- offset-free 周期边界继续使用系统时区，查询与存储使用 UTC。

### 12.2 质量

- 社区配置固定 observation-only，且所有阈值进入 fingerprint；
- 自动提升验证中的 calibration 与 holdout 分离；
- 自动提升复核协议可由不同复核者重复应用；
- 公共 hub、机械提交、短历史仓库和 monorepo 有专项结果；
- 自动提升阈值、误报上限、一致性和分布漂移门槛在 holdout 前确定；
- 未达到任一自动提升门槛时保持 observation-only；
- 结构信号最多将 `STANDARD` 提高到 `COMPLEX`；
- 结构信号不能直接进入 LLM prompt、ranking raw input 或个人价值结论。

### 12.3 性能与容量

- warm baseline 复用不重新扫描历史 commits；
- 同一 cutoff 的多人 assessment 只构建一次 baseline；
- 线性前进 sync 的 Git 读取量随新增提交增长，不随完整历史增长；
- 不分配完整 `F x F` 矩阵；
- benchmark 分别记录冷构建、warm 读取、增量、物化、峰值内存和 SQLite 增长；
- context 上限触发时输出显式 gap 和诊断计数；
- 任意 cutoff 缓存具备容量上限和安全清理策略；
- warm 复用使 assessment 总耗时增加超过 20% 时，不默认启用 difficulty 接入。

### 12.4 兼容性

- 已发布 report/work-assessment schema 保持可读；
- 新字段向后兼容或使用新 schema version；
- 历史 result JSON 不被重算；
- CLI 与 GUI 消费同一 application DTO；
- wheel、standalone 和三平台行为一致；
- rebuild/doctor 能说明 baseline 状态、规则版本、容量和失效原因。

## 13. 非目标与产品路线边界

本提案不包含：

- structural 第四排名维度；
- 以 churn、热点或代码存活时间直接评价个人价值；
- ownership、stewardship、overwrite、burndown 或 survival；
- 人员协作网络、组织知识集中度或多仓库汇总；
- AST/UAST 级复杂度轨迹或函数热点；
- TODO/FIXME 技术债对象生命周期；
- Git trailer 角色证据和外部身份 OSINT；
- GitHub/GitLab PR、review、issue 或 CI evidence provider；
- fork 网络候选贡献发现；
- AI provenance、AI 行数、AI ROI 或效率排名；
- LLM 直接评分、安全判断或绩效结论；
- Hercules runtime 适配器；
- 在没有 benchmark 的情况下引入 Go/Rust。

### 13.1 Git trailer 的条件保留结论

Git trailer 不会因本提案实施而失去全部价值，因为它描述的是提交中声明的参与角色，而历史结构
baseline 描述的是工作事项所处的结构上下文，两者并不重复。但 trailer 与 GCA 当前以 author commit
归属为中心的计分模型并不直接兼容：同一 commit 可能声明 author、co-author、reviewer 和 tester，
不能把完整 churn、workload 或 difficulty 重复分配给所有人。

因此 trailer 只保留为低优先级、条件式研究候选：

- 仅解析本地 commit message，不访问平台 API 或进行外部身份 OSINT；
- 实施前先统计真实目标仓库中标准 trailer 的覆盖率和角色分布；
- `Co-authored-by` 最多形成 `DECLARED_CO_AUTHOR` Evidence，不自动复制 workload；
- `Reviewed-by`、`Tested-by`、`Reported-by` 和 `Suggested-by` 只能 observation-only；
- `Signed-off-by` 默认视为流程或 DCO 声明，不视为实现贡献；
- trailer 不自动合并 Person，不改变 workload、difficulty、delivery、ranking 或 claim-strength ceiling；
- 覆盖率或证据一致性不足时不创建实施提案。

### 13.2 不进入当前路线图的方向

- **Forge evidence**：GCA 面向任意本地 Git 仓库，仓库可能没有 remote、位于企业内部服务、使用
  自建平台或无法访问 API。平台依赖会破坏离线性、可重放性和跨仓库可比性，因此不作为当前核心或
  默认扩展方向。
- **独立项目健康分析**：bus factor、技术债存量、总体复杂度趋势、分支健康等评价仓库整体，而不是
  个人贡献。GCA 只保留能够作为个人工作事项 difficulty 上下文的仓库级历史事实，不建设独立项目
  健康评分或仪表盘。
- **AI provenance**：AI 使用记录不能证明节省时间、工作难度、人工验证投入、交付质量或个人价值，
  且不同工具记录覆盖不一致，因此不进入个人 assessment 或当前产品路线图。
- **技术债生命周期、fork 网络和独立 LLM 审查**：同样不能在不扩大产品目标和证据边界的情况下
  提高个人评估可靠性，当前不立项。

## 14. 下一步

提案确认后，详细实施计划只覆盖：

1. 方案一 baseline 正确性参考实现、fingerprint、cutoff 和 canonical ID；
2. 时间策略、热点与 coupling 指标实验；
3. 社区基础配置，以及自动提升可选的 calibration/holdout 协议和 go/no-go 门槛；
4. 原始 file/edge count 与 materialization Schema；
5. 线性增量、force-push 失效、原子发布和容量清理；
6. status/rebuild/doctor、CLI/GUI DTO 和历史 run 兼容；
7. observation-only 发布；
8. quality/performance gate 通过后的 `difficulty-rules-v2` 条件实施。
