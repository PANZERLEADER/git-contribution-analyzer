# Code Intelligence Tools

[Simplified Chinese](../zh-CN/code-intelligence.md)

This repository supports two complementary local code-intelligence tools:

| Tool | Use it for | Local output |
|---|---|---|
| CodeGraph | Fast symbol search, callers/callees, change impact, and MCP-backed agent queries | `.codegraph/` |
| Understand-Anything | A browsable architecture graph, layers, relationships, and a guided code tour | `.understand-anything/` |

Both output directories are ignored by Git. They are derived local state and must not be included
in pull requests.

## Prerequisites

- Node.js 22 or newer.
- CodeGraph installed on `PATH`: `npm install -g @colbymchenry/codegraph`.
- The Understand-Anything plugin installed in Codex. Its build also requires pnpm 10 or newer.

On Windows, use `codegraph.cmd` and `pnpm.cmd` if PowerShell blocks the corresponding `.ps1`
shims. The repository helper handles the CodeGraph command selection automatically.

To expose CodeGraph through Codex MCP, install the machine-local integration once:

```powershell
codegraph.cmd install -t codex -l global -y
```

This modifies the user's Codex configuration, not the repository.

## Repository Workflow

Initialize both tools from the repository root:

```powershell
.\scripts\code-intelligence.ps1 codegraph-init
.\scripts\code-intelligence.ps1 understand-prepare
```

After source changes, synchronize and query CodeGraph:

```powershell
.\scripts\code-intelligence.ps1 codegraph-sync
.\scripts\code-intelligence.ps1 codegraph-query -Query "IndexRepository" -Limit 5
.\scripts\code-intelligence.ps1 status
```

In Codex, generate and open the Understand-Anything graph with:

```text
/understand . --language zh-CN --no-auto-update
/understand-dashboard .
```

The preparation action creates a project-specific `.understandignore` that excludes virtual
environments, caches, build output, local GCA workspaces, databases, and tool-generated indexes.
Source, tests, and documentation remain in scope so architecture and behavior relationships stay
visible.

Run `codegraph-sync` after meaningful code changes. Re-run `/understand` after architecture or
cross-module relationships change; it will use the existing graph for incremental analysis.
