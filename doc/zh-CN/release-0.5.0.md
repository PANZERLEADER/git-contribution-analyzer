# GCA 0.5.0

[中文文档索引](https://github.com/PANZERLEADER/git-contribution-analyzer/blob/v0.5.0/doc/zh-CN/README.md) | [English](https://github.com/PANZERLEADER/git-contribution-analyzer/blob/v0.5.0/doc/releases/0.5.0.md)



## 主要变化

- 基于本地已索引 Git 历史新增 observation-only 结构 Baseline，包括仓库内相对热点、重复共同变更、
  条件比例、Jaccard 和显式 hub 过滤。
- 新增 `gca structural status/rebuild/show/prune` 以及桌面端 Structure 页面。
- 提供保守的 `community-baseline-v1`。自动 difficulty 提升固定为 `false`，结构结果不影响工作量、
  难度、交付、排名、简历结论或 LLM 上下文。
- 原子发布已完成 Baseline，同时保留脱敏的 BUILDING、FAILED、CANCELLED 和 STALE 诊断状态。

## 兼容与升级

- `status --json` 升级为带结构缓存摘要的 `status/v2`，原始 `schemas/status/v1.json` 契约保持不变。
- 现有 work-assessment v1/v2、排名、简历和历史 run 数据保持不变。
- 升级后运行 `gca index <repo>` 填充结构提交事实；需要历史 Baseline 时再运行
  `gca structural rebuild <repo> --cutoff <排他边界>`。
- `0007_structural_baselines` 只保存可重建派生数据，降级不会修改 Git 历史或已持久化分析 run。

## 验证

- Windows 本地验证覆盖增量/全量等价、warm cache、force-push stale、失败/取消诊断、迁移升降级
  和 Schema 兼容。
- 正式发布前继续由现有 Windows/Linux/macOS CI matrix 验证 wheel、CLI 和 GUI。
- 提交 `fe1f4a4` 的 Windows/Linux/macOS quality、GUI 和 secrets 共 10 项 required jobs 全部通过：
  `https://github.com/PANZERLEADER/git-contribution-analyzer/actions/runs/29519431090`。
