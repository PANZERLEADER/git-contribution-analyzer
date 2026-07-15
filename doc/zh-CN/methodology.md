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
