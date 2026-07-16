# 代码智能工具

[English](../guides/code-intelligence.md) | [中文文档索引](README.md)

当前仓库支持两个互补的本地代码智能工具：

| 工具 | 适用场景 | 本地输出 |
|---|---|---|
| CodeGraph | 符号检索、调用关系、变更影响分析，以及通过 MCP 为 Agent 提供代码查询 | `.codegraph/` |
| Understand-Anything | 可浏览的架构图、分层、依赖关系和代码导览 | `.understand-anything/` |

两个输出目录都已加入 Git 忽略规则。它们属于可重建的本地状态，不应进入 Pull Request。

## 前置条件

- Node.js 22 或更高版本。
- CodeGraph 已加入 `PATH`：`npm install -g @colbymchenry/codegraph`。
- Codex 已安装 Understand-Anything 插件；插件构建还需要 pnpm 10 或更高版本。

Windows PowerShell 如果拦截 `.ps1` shim，请使用 `codegraph.cmd` 和 `pnpm.cmd`。仓库脚本会自动
选择可用的 CodeGraph 命令。

如需让 Codex 通过 MCP 使用 CodeGraph，只需在当前机器执行一次：

```powershell
codegraph.cmd install -t codex -l global -y
```

该命令修改的是用户级 Codex 配置，不会修改仓库文件。

## 仓库工作流

在仓库根目录初始化两个工具：

```powershell
.\scripts\code-intelligence.ps1 codegraph-init
.\scripts\code-intelligence.ps1 understand-prepare
```

源码变更后同步并查询 CodeGraph：

```powershell
.\scripts\code-intelligence.ps1 codegraph-sync
.\scripts\code-intelligence.ps1 codegraph-query -Query "IndexRepository" -Limit 5
.\scripts\code-intelligence.ps1 status
```

在 Codex 中生成并打开 Understand-Anything 图谱：

```text
/understand . --language zh-CN --no-auto-update
/understand-dashboard .
```

`understand-prepare` 会创建项目专用的 `.understandignore`，排除虚拟环境、缓存、构建产物、
本地 `.gca` 工作区、数据库和工具生成的索引。源码、测试和文档仍会参与分析，以保留架构和
行为关系。

有实质代码变更时执行 `codegraph-sync`。架构或跨模块关系变化后重新执行 `/understand`；
Understand-Anything 会基于已有图谱进行增量分析。
