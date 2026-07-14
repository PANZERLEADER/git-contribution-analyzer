# Git 贡献分析器

[English](README.md)

`gca` 是一个以 CLI 为主要入口、以证据为基础的 Git 贡献分析工具。它将可重复验证的
Git 仓库事实，与确定性规则、LLM 辅助解释严格分离。

GCA 0.1.0 提供两条相互隔离但共享证据的数据流水线：

- 工作评估：分析已完成工作、工作规模、工程难度、技术维度和业务维度。
- 简历生成：基于已确认人员的贡献证据，生成可人工审核的简历候选内容。

GCA 不根据提交数或代码行数生成员工总分、排名、工时、绩效等级、薪酬或晋升建议。

## 安装与开发

开发环境安装：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\gca.exe --help
```

也可以从 [v0.1.0 Release](https://github.com/PANZERLEADER/git-contribution-analyzer/releases/tag/v0.1.0)
安装 wheel，或下载 Windows、Linux、macOS standalone 制品。详细步骤见
[中文安装指南](doc/zh-CN/installation.md)。

## 常用 CLI

```powershell
# 初始化仓库本地工作区并建立首个 Git 索引。
gca init D:\path\to\repository

# 重建确定性索引，或增量同步新提交和变化的 ref。
gca index D:\path\to\repository --json
gca sync D:\path\to\repository --json

# 查看规范化身份并确认别名映射。
gca identities list D:\path\to\repository --json
gca identities map D:\path\to\repository `
  --name "Old Name" `
  --email "old@example.com" `
  --person-name "Canonical Name" `
  --person-email "canonical@example.com" `
  --json

# 检查工作区、索引和数据库健康状态。
gca status D:\path\to\repository --json
gca doctor D:\path\to\repository --json

# 对一个已确认人员执行不使用 LLM 的确定性贡献分析。
gca analyze D:\path\to\repository `
  --person alice@example.com `
  --since 2026-01-01 `
  --until 2026-06-30 `
  --no-llm `
  --json

# 分析索引中的全部 Git 身份。
gca analyze D:\path\to\repository --all --no-llm --json

# 评估已完成工作量和确定性工程难度。
gca assess D:\path\to\repository `
  --person alice@example.com `
  --person bob@example.com `
  --since 2026-01-01 `
  --no-llm `
  --json
gca assess D:\path\to\repository --all `
  --exclude-person ci@example.com `
  --no-llm --json

# 为一个已确认人员生成有 Evidence 引用的简历候选内容。
gca resume D:\path\to\repository `
  --person alice@example.com `
  --target-role "Senior Backend Engineer" `
  --language zh-CN `
  --style concise `
  --max-bullets 6 `
  --no-llm `
  --json

# 查看和测试内置 Provider。
gca providers list D:\path\to\repository --json
gca providers test D:\path\to\repository --json

# 查看持久化分析运行并重新生成报告。
gca runs list D:\path\to\repository --json
gca runs show <run-id> D:\path\to\repository --json
gca report D:\path\to\repository --run latest --format markdown
gca report D:\path\to\repository --run latest --format json --output report.json

# 只删除仓库本地的 .gca 工作区。
gca uninit D:\path\to\repository --yes
```

完整参数、退出码和命令组合见 [中文 CLI 参考](doc/zh-CN/cli-reference.md)。

## 数据和索引边界

GCA 索引 ref、提交、父子关系、文件变更、身份、稳定 patch ID、目标分支可达性、发布 tag、
cherry-pick 和 revert。索引存储在被分析仓库的 `.gca/` 目录，并通过
`.git/info/exclude` 在本地忽略。GCA 不修改源码、提交或 Git 历史。

确定性分析不依赖 LLM。每个分析运行会持久化参数、Git 基线、规则版本、Contribution Item、
能力评估、Evidence 和带版本的报告 JSON。相同 Snapshot 与规则版本应得到相同确定性结论。

## LLM Provider

LLM 默认关闭。在被分析仓库的 `.gca/config.yml` 中启用：

```yaml
llm:
  enabled: true
  provider: openai-compatible
  model: gpt-4.1-mini
  baseUrl: https://api.openai.com/v1
  apiKeyEnv: GCA_LLM_API_KEY
  timeoutSeconds: 30.0
  maxRetries: 2
  allowFallbackToRules: true
```

密钥值必须通过仓库外部的环境变量提供，不得写入 `.gca/config.yml`。GCA 支持：

- `mock`
- `openai-compatible`
- `anthropic`
- `ollama`
- `codex-cli`
- `claude-cli`

`codex-cli` 和 `claude-cli` 可以复用目标机器上已有的认证状态和模型网关配置。命令 Provider
在独立临时目录中运行，GCA 只通过标准输入传递最小化语义任务，不向模型开放仓库源码、工具、
MCP、Chrome 或会话持久化能力。

LLM 只能解释或改写白名单内的确定性结论，不能修改完成状态、规模、难度、Evidence 或提高简历
claim strength 上限。Provider 失败时，可按配置保留确定性结果并标记为 `PARTIAL`。

详细配置见 [中文 LLM Provider 指南](doc/zh-CN/provider-guide.md)。

## 交付状态语义

- `AUTHORED_ONLY`：提交已索引，但无法从配置的目标分支到达。
- `LANDED`：提交可以从目标分支到达。
- `RELEASED`：提交可以从目标分支到达，且存在对应发布 tag。
- `REVERTED`：已落地或发布的提交存在已落地的 revert 提交。
- 相同稳定 patch ID 会关联 cherry-pick 来源与交付结果，但不会重复计算工作量。

身份只通过精确邮箱、`.mailmap` 和人工映射确定。名称模糊匹配不会自动合并；有歧义时必须使用
`gca identities map` 确认。

## 确定性贡献分析

`gca analyze` 可以分析一个已确认 Person，也可以通过 `--all --no-llm` 分析全部索引身份。
项目报告会保留未确认身份并输出警告，不会静默合并或排除。

个人报告和项目报告均包含独立的技术总结与业务总结：

- 技术维度：模块、变更类型、交付信号和有证据支持的能力标签。
- 业务维度：从 conventional commit scope、issue key 和模块聚类推断的工作领域。

业务维度只表示工作涉及的领域，不证明收入、客户价值、业务所有权或个人绩效。

## 工作量与难度评估

`gca assess` 将活动区分为已完成、待交付、返工和集成工作。工作规模使用
`SMALL`、`MEDIUM`、`LARGE`、`XLARGE`；工程难度使用 `ROUTINE`、`STANDARD`、
`COMPLEX`、`HIGH_RISK`。规模与难度是两个独立维度。

Merge diff、重复 patch、生成目录、vendor/build 输出、lockfile 和二进制行数不会产生重复工作量。
难度由数据迁移、分布式一致性、兼容性、影响范围、关键领域和交付负担等信号决定，原始代码行数
不能单独提高难度。

报告包含 Evidence ID、规则版本、置信度和 gaps，但不输出员工总分、排名、完成率、工时估算、
薪酬或晋升建议。

## 简历生成

`gca resume` 只接受已确认 Person，默认选择 `LANDED` 和 `RELEASED` 工作。每个项目总结和
经历 bullet 都引用 Contribution Item 与 Evidence ID。责任强度只有：

- `CONTRIBUTED`
- `IMPLEMENTED`
- `LED`

仅有 Git 证据时不能得到 `LED`。百分比、收入、用户增长、线上性能等结果数字必须引用经过人工
确认的 verified outcome YAML；否则会被拒绝。简历报告不会包含邮箱、其他人员、团队排名或内部
难度比较。

## 质量检查

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m pytest --cov=git_contribution_analyzer
.\.venv\Scripts\python.exe -m build
```

## 中文文档

- [中文文档索引](doc/zh-CN/README.md)
- [架构](doc/zh-CN/architecture.md)
- [数据模型与迁移](doc/zh-CN/data-model.md)
- [CLI 参考](doc/zh-CN/cli-reference.md)
- [安装、升级与卸载](doc/zh-CN/installation.md)
- [工作评估与简历方法论](doc/zh-CN/methodology.md)
- [隐私与数据边界](doc/zh-CN/privacy.md)
- [LLM Provider 指南](doc/zh-CN/provider-guide.md)
- [黄金数据集](doc/zh-CN/golden-dataset.md)
- [0.1.0 发布说明](doc/zh-CN/release-0.1.0.md)

英文文档仍作为原始技术契约保留。中文文档翻译命令、边界和方法论，不改变程序行为。
