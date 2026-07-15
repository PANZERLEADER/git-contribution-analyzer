# GCA 0.2.0 发布说明

[中文文档索引](https://github.com/PANZERLEADER/git-contribution-analyzer/blob/v0.2.0/doc/zh-CN/README.md) | [English](https://github.com/PANZERLEADER/git-contribution-analyzer/blob/v0.2.0/doc/releases/0.2.0.md)

## 主要能力

- 可以重复指定多个已确认人员，也可以选择全部 active、confirmed、HUMAN 身份并显式排除人员。
- 身份合并支持预览、执行、查询和撤销，不删除 Person，也不改写历史 run。人工 alias 映射现在会
  记录可撤销的 `ALIAS_MAP` 事件。
- workload、difficulty、delivery 使用确定性 dense ranking；只有显式提供 YAML 权重配置时，
  才生成 cohort 内归一化的 Decimal 综合分。
- `work-assessment/v2` 报告可持久化并导出 UTF-8 BOM CSV；除非指定 `--include-email`，默认不含邮箱。

## 兼容与升级

- 已冻结的 `work-assessment/v1` JSON 和 Markdown 报告仍可重放。
- `0006_identity_merges` 迁移增加可撤销身份状态；撤销全部 active merge event 后可以降级。
- `identities map` 的参数和 JSON envelope 保持兼容。
- 历史 analysis 和 assessment run 内容保持不可变。

## 隐私与解释边界

- 排名字段完全由确定性规则生成，不发送给 LLM Provider，也不允许 LLM 修改。
- CSV 默认不含邮箱；被排除人员只记录排除原因，不会进入报告 cohort。
- 排名只用于同一 cohort 内的结构化复盘，不能证明员工价值、工时、薪酬、晋升条件或业务成果。

## 发布门禁

发布提交必须通过 Windows、Linux、macOS CI、Git 历史凭据扫描、隔离 wheel 生命周期、pipx 安装和
standalone 冒烟。Tagged workflow 会发布 SHA-256 checksums，并使用本文档作为 `v0.2.0` 发布说明。
