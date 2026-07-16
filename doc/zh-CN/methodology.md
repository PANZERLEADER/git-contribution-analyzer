# 工作评估与简历生成方法论

[中文文档索引](README.md) | [English](../guides/methodology.md)

## Evidence 边界

GCA 观测 Git commit、ref、父提交关系、patch ID、文件变更、发布 tag 和显式身份映射。
所有派生结论都必须引用可回溯到这些事实的 Evidence。Git 不能证明实际工时、唯一所有权、
业务成果或员工价值。

## 完成状态分组

- `COMPLETED`：事项在评估目标上属于 `LANDED` 或 `RELEASED`。
- `PENDING`：证据只存在于作者分支，不计入已完成工作量。
- `REWORK`：revert 或重复修复证据，独立于已完成工作量保留。
- `integrationWork`：merge/release 集成活动，与功能工作分开展示。

当带版本规则认定其为噪声时，merge diff、重复 patch、二进制行数、generated/vendor 内容和
lockfile 不计入有效工作量。

## 工作规模

`SMALL`、`MEDIUM`、`LARGE`、`XLARGE` 描述相对于仓库基线的有效文件数、有效 churn 和
模块跨度。规模不等于工期，也不等于难度。

## 工程难度

`ROUTINE`、`STANDARD`、`COMPLEX`、`HIGH_RISK` 是确定性规则结果。信号包括结构变化、
影响范围、数据迁移、分布式一致性、业务关键路径、兼容性和交付负担。每个结果都包含规则版本、
Evidence、置信度和 gaps。结构分析器缺失时应降低置信度，不能虚构信号。

## 结构信号

`structural-signals-v1` 从当前筛选后的提交集合中推导重复共同变更关系和结构热点。只有至少两个非
merge 提交同时修改两个有效路径时，才形成 coupled pair；两个提交为 `MEDIUM` 置信度，三个及以上
为 `HIGH`。热点至少需要两个变更提交，观察分数为 `changeCommits + coChangeCommits`，其中后者只
统计达到重复阈值的共同变更边。结果使用稳定排序，每个条目最多保留 50 个支持提交哈希。

计算会排除 generated 路径、纯二进制提交、重复 patch ID 和 merge 提交。共同变更不证明运行时依赖，
热点也不证明代码质量差、难度高、所有权、员工价值或个人绩效。当前规则版本只展示这些结构信号，
不会修改工作量、难度或排名分数。

历史 `structural-baseline/v1` 只使用目标 ref 上严格早于排他 cutoff 的索引历史，绝不读取被评估
当期。计算排除 merge commit、重复 patch、generated 路径和纯二进制提交。Context cap 用于防止
文件对数量平方膨胀，命中时会记录 gap。所有非零文件和规范文件对 occurrence 都会保存，即使尚未
达到候选展示阈值。

Baseline 支持 lifetime、rolling-window 和 dual-window 计数。Hotspot 使用仓库内相对 percentile；
coupling 报告 subset ratio、双向 conditional、Jaccard、跨模块状态和 hub penalty，不把共同变更
标记为依赖。Baseline 身份包含仓库、目标 ref、范围、cutoff 和规则配置，不能跨不兼容上下文复用。

历史 baseline 当前是 observation-only，不参与工作量、交付、排名、简历、LLM prompt 或
`difficulty-rules-v1`。开源默认配置为保守的 `community-baseline-v1`，其自动 difficulty 提升固定为
`false`，因此无需项目专属审核即可用于结构观察。启用独立 difficulty 新版本前，仍必须按公开
calibration 协议，在仓库互斥 holdout 上通过冻结的 precision、误报率、abstain、稳定性和 promotion
cap 全部门槛。校准缺失或失败只阻止自动提升，不阻止 observation-only 报告。

## 排名

排名默认关闭。`workload` 只把已完成事项的规模映射为 `1/3/6/10` 分；`difficulty` 映射为
`1/2/4/6` 分；`delivery` 使用已完成事项数并施加最高 30% 的返工惩罚。计算使用 Decimal、固定
四位小数和 dense ranking。可选 YAML 配置使用 cohort-max 归一化，权重和必须精确为 `1.0`。
不同 cohort 或不同配置下的分数不可直接横向比较。

## 时间口径与周期

- `AUTHORED`：作者提交时间；`COMMITTED`：committer 写入提交对象的时间。
- `LANDED`：提交首次由目标分支 first-parent 集成点包含的时间。
- `MERGED`：提交由目标分支 merge commit 引入的时间；直接提交不属于该口径。
- `RELEASED`：首次关联发布 tag 的 creatordate；annotated tag 使用 tagger date，轻量 tag 使用
  目标 commit 时间。

周从周一开始，月和季度使用自然日历。首尾不完整周期必须标记 partial。环比使用前一个输出周期；
同比只在同一序列包含上年相同周/月/季度时计算。比较前必须保持仓库、人员 cohort、过滤条件和规则
版本一致。Git 时间戳统一规范化为 UTC；升级已有工作区后应执行一次 `gca index`。

CLI 中未带时区的日期或时间按系统时区解释，带 `Z` 或数字偏移时以显式偏移为准。周/月/季度
边界在同一系统本地日历上计算，包括系统存在夏令时变化的情况；写入索引和执行 SQLite 时间过滤时
才转换为 UTC。

## 简历 Claim

- `CONTRIBUTED`：存在贡献证据，但责任边界不完整。
- `IMPLEMENTED`：已确认 Person 拥有主要交付实现证据，且不存在所有权冲突。
- `LED`：需要显式所有权或人工验证证据；仅有 Git 证据不能授予该等级。

百分比、收入、增长和线上结果数字必须引用严格的 verified-outcome YAML。待交付工作默认排除；
显式包含时必须标记为 pending。

## LLM 的角色

LLM 可以解释或改写白名单内的确定性 claim，但不能看到或修改排名分数、不能修改规模/难度、
不能引入未知 Item/Evidence ID、
突破 claim strength 上限、增加无依据数字或推断团队排名。Provider 输出经过 Schema 和 Evidence
校验；失败时可以安全降级为确定性内容。

## 人工审核

工作评估应作为结构化复盘输入，而不是自动绩效决策。比较不同周期前，需要处理身份警告、确认
目标分支并审核 Evidence gaps。简历草稿必须补充 Git 无法提供的背景，尤其是业务结果、共同所有权
和团队协作边界。
