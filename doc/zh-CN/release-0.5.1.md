# GCA 0.5.1

[中文文档索引](https://github.com/PANZERLEADER/git-contribution-analyzer/blob/v0.5.1/doc/zh-CN/README.md) | [English](https://github.com/PANZERLEADER/git-contribution-analyzer/blob/v0.5.1/doc/releases/0.5.1.md)

## 修复内容

- `status`、`doctor`、`sync` 或 `index` 打开现有工作区时自动执行增量 SQLite 迁移。由
  0.2.0 至 0.4.1 创建的工作区无需重新运行 `gca init`，即可填充 0.5.x 结构事实。
- 增量同步和全量索引重建均保留已确认身份与活动中的可撤销身份合并。再次读取已知 Git Author
  时，不再覆盖显式别名归属。
- 索引成功后刷新 `toolVersion`、`updatedAt` 和 `lastSync` 元数据。
- 使用显式 UTF-8 校验生成 GitHub Release 合并说明，并使用绑定 tag 的中英文绝对链接，确保
  Release 页面中的英文和简体中文内容均可正常访问。

## 兼容与升级

- 本版本是 0.5.0 的增量补丁，不改变 CLI 命令、报告 Schema、结构规则版本以及评估、排名、
  简历行为。
- 升级后运行 `gca index <repo>`。重建结构事实时会保留现有身份映射和可撤销合并事件。
- 历史结构 Baseline 继续保持 observation-only，不影响难度或简历结论。

## 验证

- 回归测试覆盖 `status`、`doctor`、`index` 迁移，以及 `sync` 和全量 `index` 对身份合并的保留。
- 正式发布前仍要求 Windows/Linux/macOS quality、GUI、凭据历史和发布制品检查全部通过。
