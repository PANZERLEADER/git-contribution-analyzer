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
gca assess <repo> --all --no-llm --json
```

结果分别展示已完成、待交付、返工和集成活动。规模与难度是带版本的分布，不是员工总分或排名。

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
gca report <repo> --run <run-id> --format markdown --output report.md
gca report <repo> --run <run-id> --format json --output report.json
```

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
