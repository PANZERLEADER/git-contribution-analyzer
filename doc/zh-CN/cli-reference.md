# GCA CLI 参考

[中文文档索引](README.md) | [English](../cli/cli-reference.md)

## 全局选项

| 选项 | 含义 |
|---|---|
| `--help` | 显示命令或子命令帮助 |
| `--version` | 显示已安装的 GCA 版本 |

仓库路径可省略，默认使用当前目录。包含空格或 Unicode 的 Windows 路径应作为一个带引号参数传入。

## 仓库生命周期

| 命令 | 用途 |
|---|---|
| `gca init [PATH]` | 创建 `.gca`、迁移 SQLite 并执行首次索引 |
| `gca index [PATH]` | 重建确定性索引 |
| `gca sync [PATH]` | 增量同步 ref 和 commit |
| `gca status [PATH] [--json]` | 查看工作区、基线和身份健康状态 |
| `gca doctor [PATH] [--json]` | 诊断 Git、工作区、数据库和锁状态 |
| `gca uninit [PATH] [--yes]` | 只删除仓库本地 GCA 工作区 |

`gca status --json` 当前输出 `status/v2`，新增 structural cache 摘要；原始
`schemas/status/v1.json` 保持不变，用于历史重放和兼容性检查。

## 结构观察

```powershell
gca structural status <repo> --json
gca structural rebuild <repo> --cutoff 2026-07-01T00:00:00Z `
  --branch main --scope src --time-strategy dual-window --json
gca structural show <repo> --baseline <baseline-id> --json
gca structural prune <repo> --keep 8 --yes --json
```

`--cutoff` 是排他边界；省略时使用当前时刻。`--branch` 默认读取仓库配置，`--scope` 是可选路径
前缀，`--time-strategy` 可选 `lifetime`、`rolling-window`、`dual-window`；省略时使用
`.gca/config.yml`（`community-baseline-v1` 默认为 `DUAL_WINDOW`）。Rebuild 只发布完成的不可变
baseline。Prune 必须带 `--yes`，且只删除旧的可重建 baseline cache。

输出是仓库级 observation 数据，不会改变工作评估、难度、排名或简历结果。`status` 和 `doctor`
会包含 cache 诊断。

## 身份

```powershell
gca identities list <repo> --json
gca identities map <repo> --name Alice --email alice@example.com `
  --person-name Alice --person-email alice@example.com
```

精确邮箱和 `.mailmap` 只生成候选建议，在显式映射前仍未确认。简历命令会拒绝未确认身份。

## 贡献分析

```powershell
gca analyze <repo> --person alice@example.com --no-llm --json
gca analyze <repo> --all --no-llm --json
```

通用过滤器包括 `--since`、`--until`、`--branch`、`--release`、`--scope` 和
`--delivery`。`--person` 与 `--all` 互斥。

## 工作评估

```powershell
gca assess <repo> --person alice@example.com --no-llm --json
gca assess <repo> --person alice@example.com --person bob@example.com --no-llm --json
gca assess <repo> --all --exclude-person ci@example.com --no-llm --json
gca assess <repo> --all --rank-by workload --rank-by difficulty --no-llm --json
gca assess <repo> --all --ranking-config team-ranking.yml --no-llm --json
gca assess <repo> --all --since 2025-01-01 --until 2026-12-31 `
  --period quarter --time-basis released --no-llm --json
gca report <repo> --run latest --format csv --output team.csv
```

结果分别展示已完成、待交付、返工和集成活动。`--person` 与 `--exclude-person` 均可重复；
`--exclude-person` 只能与 `--all` 组合。全员模式默认只纳入 active、已确认的 `HUMAN` 身份，
并在报告中记录其他身份的排除原因。CSV 默认不包含邮箱，只有显式提供 `--include-email` 才加入。

`--time-basis` 可选 `authored`、`committed`、`merged`、`landed`、`released`。
`--period` 可选 `week`、`month`、`quarter`，并要求同时提供合法且顺序正确的 `--since`、
`--until`。周期命令为每个自然周期保存一个工作评估 run，并额外保存包含环比/同比的 series run。
同比仅在请求范围包含上年对应自然周期时生成。周从周一开始，不完整首尾周期标记为 partial。
未带时区的日期和时间使用运行机器的系统时区；带 `Z` 或数字偏移的输入使用显式时区。报告保留
输入偏移，索引查询在内部转换为 UTC。

身份维护支持可逆合并：

```powershell
gca identities merge <repo> --source old@example.com --target person-id --dry-run --json
gca identities merge <repo> --source old@example.com --target person-id --yes --json
gca identities merges <repo> --json
gca identities unmerge <repo> --merge-id <id> --yes --json
```

合并不会删除 source Person 或改写历史报告；它只把 alias 移到 target 供后续分析使用，并记录
可撤销事件。若 alias 在合并后被再次映射，撤销会整体失败，避免部分恢复。

## 简历生成

```powershell
gca resume <repo> --person alice@example.com --language zh-CN `
  --style concise --max-bullets 6 --no-llm --json
```

可选参数包括 `--target-role`、`--include-pending` 和 `--verified-outcomes <yaml>`。
语言为 `zh-CN` 或 `en-US`；风格为 `concise`、`star` 或 `xyz`。Verified outcome 必须包含
`id`、`text`、`source`、`verifiedBy` 和 `verifiedAt`。

## Runs 与报告

```powershell
gca runs list <repo> --json
gca runs show <run-id> <repo> --json
gca runs compare <base-run-id> <target-run-id> <repo> --json
gca report <repo> --run <run-id> --format markdown --output report.md
gca report <repo> --run <run-id> --format json --output report.json
```

`runs compare` 只接受两个持久化 `WORK_ASSESSMENT` run，并报告总体指标、规模/难度分布和人员
维度的变化；规则版本、时间口径或 cohort 不一致时会输出可比性警告。

`report` 重放已持久化结果，并根据 run type 选择对应渲染器。

## Provider

```powershell
gca providers list <repo> --json
gca providers test <repo> --json
```

内置 Provider：`mock`、`openai-compatible`、`anthropic`、`ollama`、`codex-cli`、
`claude-cli`。凭据从环境变量解析，永远不会写入 `.gca/config.yml`。

## 退出码

| 代码 | 含义 |
|---:|---|
| 0 | 成功 |
| 2 | CLI 参数或用法错误 |
| 3 | Git/仓库错误 |
| 4 | 工作区/配置错误 |
| 5 | 身份错误 |
| 6 | LLM/Provider 错误 |
| 7 | 报告/Schema 错误 |
| 8 | 操作被中断 |
