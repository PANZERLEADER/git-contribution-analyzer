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
模块跨度。规模不等于工期，也不等于难度。GCA 输出分布和事项列表，不会聚合成员工总分。

## 工程难度

`ROUTINE`、`STANDARD`、`COMPLEX`、`HIGH_RISK` 是确定性规则结果。信号包括结构变化、
影响范围、数据迁移、分布式一致性、业务关键路径、兼容性和交付负担。每个结果都包含规则版本、
Evidence、置信度和 gaps。结构分析器缺失时应降低置信度，不能虚构信号。

## 简历 Claim

- `CONTRIBUTED`：存在贡献证据，但责任边界不完整。
- `IMPLEMENTED`：已确认 Person 拥有主要交付实现证据，且不存在所有权冲突。
- `LED`：需要显式所有权或人工验证证据；仅有 Git 证据不能授予该等级。

百分比、收入、增长和线上结果数字必须引用严格的 verified-outcome YAML。待交付工作默认排除；
显式包含时必须标记为 pending。

## LLM 的角色

LLM 可以解释或改写白名单内的确定性 claim，但不能修改规模/难度、引入未知 Item/Evidence ID、
突破 claim strength 上限、增加无依据数字或推断团队排名。Provider 输出经过 Schema 和 Evidence
校验；失败时可以安全降级为确定性内容。

## 人工审核

工作评估应作为结构化复盘输入，而不是自动绩效决策。比较不同周期前，需要处理身份警告、确认
目标分支并审核 Evidence gaps。简历草稿必须补充 Git 无法提供的背景，尤其是业务结果、共同所有权
和团队协作边界。
