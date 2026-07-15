# GCA 0.3.0 发布说明

[中文文档索引](https://github.com/PANZERLEADER/git-contribution-analyzer/blob/v0.3.0/doc/zh-CN/README.md) | [English](https://github.com/PANZERLEADER/git-contribution-analyzer/blob/v0.3.0/doc/releases/0.3.0.md)

## 主要能力

- 一条工作评估命令可以按自然周、月或季度生成持久化子 run 和可重放的序列报告。所有周期共享
  同一工作量基线，并生成环比；请求范围包含上年对应周期时生成同比。
- 支持按 authored、committed、merged、landed、released 五种 Git 时间口径归属工作。
  landed/merged 使用目标分支 first-parent 集成点，released 使用 tag 创建时间。
- `gca runs compare` 可以比较两个历史 `WORK_ASSESSMENT` run，输出总体、规模、难度和人员维度
  的变化，并提示规则版本、时间口径或 cohort 不一致。
- 未带偏移的 `--since/--until` 按运行机器系统时区解释；显式 `Z` 或数字偏移保持优先。自然周期
  使用相同本地日历并处理系统偏移变化。
- 反向时间范围会被拒绝；Git 索引时间和 SQLite 查询绑定统一规范化为 UTC。

## 兼容与升级

- 历史 analysis、`work-assessment/v1`、`work-assessment/v2`、resume 和 series run 保持不可变且
  可重放。尚未记录 `inputTimeZone` 的早期 series 报告按 `LEGACY_UTC` 重放。
- 本版本不需要数据库迁移。升级后对已有工作区执行一次 `gca index <repo>`，以 UTC 规范重新构建
  Git 时间索引，然后运行 `gca doctor <repo> --json`。
- 既有命令保持兼容。周期评估必须同时提供 `--since` 和 `--until`；显式偏移始终优先。

## 解释边界

- 趋势和历史差值只用于同一仓库、cohort、过滤条件和规则版本下的 Git 证据比较，不代表工时、
  员工价值、薪酬或晋升条件。
- 不完整首尾周期会标记 partial，不应与完整周期直接比较。
- LLM Provider 不生成或修改确定性时间归属、工作量、难度和对比数值。

## 发布门禁

发布提交必须通过 Windows、Linux、macOS CI、Git 历史凭据扫描、隔离 wheel 生命周期、pipx 安装、
standalone 冒烟，以及全部版本与 Schema 兼容测试。Tagged workflow 会发布 SHA-256 checksums，
并使用中英文发布说明创建 `v0.3.0` GitHub Release。
