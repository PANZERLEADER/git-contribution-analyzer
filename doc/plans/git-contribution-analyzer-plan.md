# 实施计划：Git Contribution Analyzer MVP

## 1. 基本信息

**功能名称**：Git Contribution Analyzer MVP
**项目目录**：`D:/CodeWorkspace/git-contribution-analyzer`
**目标版本**：`0.1.0`
**实施方案**：提案方法一，Python 模块化单体 + PyDriller/原生 Git + `gca` CLI + LLM Provider SPI
**技术栈**：Python 3.12、Typer、Rich、Pydantic 2、SQLAlchemy 2、Alembic、SQLite、PyDriller、httpx、Jinja2、pytest
**相关提案**：`doc/proposals/git-contribution-analyzer-proposals.md`
**计划日期**：2026-07-13

## 2. 决策摘要

以下决策作为实施基线，编码阶段不再重复讨论：

| 决策项 | 决定 |
|---|---|
| 产品入口 | CLI-first，主命令固定为 `gca` |
| 架构 | 模块化单体，Domain/Application/Adapters/CLI 四层 |
| Git 解析 | PyDriller 负责结构化遍历，原生 Git 命令负责可达性、patch-id、mailmap 等精确语义 |
| 本地存储 | SQLite + SQLAlchemy + Alembic |
| 本地工作区 | 被分析仓库根目录下 `.gca/` |
| LLM 边界 | 仅做语义分类、摘要、能力解释和简历候选，不计算 Git 事实和最终绩效 |
| Provider | 固定 `LlmProvider` 端口，首批实现 Mock、OpenAI-compatible、Anthropic、Ollama |
| 报告 | Markdown 和 JSON 为 MVP 必选，HTML 为后续增强 |
| API/UI/MCP | 不进入 0.1.0，实现时只预留 Application 复用边界 |
| 默认分析范围 | 索引配置 refs 下的提交，交付结论默认以目标分支可达性为准 |
| 默认绩效输出 | 多维证据和置信度，不生成单一员工总分 |
| 密钥管理 | 仅环境变量或用户级安全配置，不写入 `.gca/config.yml` 和日志 |

## 3. 背景和目标

### 3.1 当前状态

当前独立项目只有提案文档，没有代码、包管理、数据库、测试和发布配置。匿名规模基准和生成式
fixture 已验证以下现实问题：

- 大型仓库无法逐 commit 人工分析。
- 同一开发者可能存在多个作者名和邮箱。
- Merge、机器人、共享账号、cherry-pick、squash 和废弃分支会扭曲贡献统计。
- 一个工作事项可能跨 Service、API、Admin、SQL、测试和文档多个目录。
- LLM 可以解释语义，但不能替代确定性 Git 事实和人工绩效判断。

### 3.2 问题陈述

需要一个可安装、可重复运行和可审计的 CLI 工具，将 Git 历史转换为个人工作事项、能力证据和简历候选描述，同时保持 LLM 厂商可替换，并在 LLM 不可用时仍能产出基础报告。

### 3.3 MVP 目标

1. 在 Windows、Linux 和 macOS 上提供可执行的 `gca` 命令。
2. 对任意本地 Git 仓库完成初始化、全量索引、增量同步和状态检查。
3. 归一化 Git 身份并明确未确认身份。
4. 区分开发过、进入目标分支、进入发布标签、被 revert 和重复提交的变更。
5. 在无 LLM 模式下生成确定性的个人贡献 Markdown/JSON 报告。
6. 通过统一 Provider 接入四类 LLM，并保证 Provider 失败可降级。
7. 对每个语义结论保存证据、模型、Prompt 和 Schema 版本。
8. 使用黄金仓库覆盖复杂 Git 历史并建立跨平台回归测试。

### 3.4 非目标

以下内容不属于 `0.1.0`：

- 多租户、团队权限和企业 SSO。
- Web 管理后台和长期运行的 REST 服务。
- DevLake、Jira、TAPD、GitHub/GitLab PR 的正式连接器。
- Codex/Claude Code MCP 安装器。
- 自动决定绩效等级、奖金或晋升结论。
- 自动抓取线上业务指标并推断收益。
- 支持非 Git 版本控制系统。

## 4. 需求与验收标准

### 4.1 功能需求

#### FR-001：CLI 安装与帮助

安装包必须注册 `gca` 命令，并提供 `--help`、`--version` 和子命令帮助。

**验收标准**：

- `gca --help` 在 Windows、Linux、macOS CI 中退出码为 `0`。
- `gca --version` 输出语义化版本。
- Windows 不能只依赖 `.ps1` shim，必须能通过 `.exe` 或 `.cmd` 调用。

#### FR-002：仓库初始化

`gca init [path]` 验证 Git 仓库，创建 `.gca/`、配置、SQLite 数据库和首次索引。

**验收标准**：

- 非 Git 目录返回退出码 `3`。
- 重复执行保持幂等，不破坏现有索引。
- `.gca/` 默认加入 `.git/info/exclude`。
- `gca status --json` 可以读取初始化结果。

#### FR-003：全量索引和增量同步

`gca index` 重建索引，`gca sync` 只处理 refs 变化和新增提交。

**验收标准**：

- 全量索引结果与删除 `.gca/` 后重新 `init` 一致。
- 新增 1 个 commit 后 `sync` 只新增对应事实记录。
- force-push 或 ref 删除后更新 ref 状态，不误删仍被其他 ref 引用的 commit。
- 中断或异常不留下部分提交事务。

#### FR-004：状态与诊断

`gca status` 和 `gca doctor` 输出仓库、索引、身份、Provider、锁和最近运行状态。

**验收标准**：

- `status --json` 符合版本化 Schema。
- `doctor` 能识别 Git 不可用、数据库损坏、陈旧锁、Provider 配置缺失。
- 人类输出不得泄露 API Key。

#### FR-005：身份归一化

支持 Git name/email、`.mailmap`、配置映射和人工确认。

**验收标准**：

- 同邮箱多名称可以生成别名候选。
- `.mailmap` 的明确映射自动应用并记录来源。
- 模糊候选不得自动合并。
- `gca identities map` 后能够稳定定位 Person。
- `gca analyze --person` 命中多个 Person 时返回退出码 `5`。

#### FR-006：交付状态判断

对 commit 判断目标分支可达性、发布标签、Merge、revert 和重复 patch。

**验收标准**：

- 未进入目标分支的提交标记为 `AUTHORED_ONLY`。
- 进入目标分支的提交标记为 `LANDED`。
- 被目标 release tag 包含的提交标记为 `RELEASED`。
- revert commit 与被撤销 commit 建立关系。
- 相同 patch-id 的 cherry-pick 不重复计算净交付。

#### FR-007：确定性贡献分析

`gca analyze --no-llm` 按人员、时间、分支、发布和路径范围生成贡献事实。

**验收标准**：

- 输出提交类型、模块、文件、变更量、活跃区间、交付状态和证据列表。
- Merge、二进制、生成文件和排除路径单独统计。
- 所有计数可由 Git 命令复核。
- 相同索引和配置重复运行得到相同 JSON。

#### FR-008：工作事项聚合

规则引擎将相关 commit 聚合为 Contribution Item，LLM 可在此基础上增强摘要。

**验收标准**：

- Issue/PR 编号相同的 commit 优先聚合。
- 分支、scope、路径邻近和时间窗口作为次级聚合信号。
- 每个工作事项保留所有 commit 证据。
- 不确定聚合必须标记低置信度，不得隐藏原始提交。

#### FR-009：可替换 LLM Provider

Application 层仅依赖 `LlmProvider` 协议。

**验收标准**：

- 更换 Provider 不修改 Domain/Application。
- Mock Provider 可在测试中完整运行语义流水线。
- OpenAI-compatible、Anthropic、Ollama Provider 通过契约测试。
- Provider 不可用且允许降级时生成确定性报告并记录警告。

#### FR-010：能力与简历候选

LLM 根据规则证据生成能力标签、贡献解释和简历候选。

**验收标准**：

- 每条输出引用 Evidence ID。
- 输出包含置信度和证据缺口。
- 没有指标证据时不得生成百分比提升。
- “主导”“负责”“参与”根据证据强度选择。

#### FR-011：报告与运行记录

保存 AnalysisRun，并导出 Markdown、JSON。

**验收标准**：

- 每次运行保存参数、Git 基线、规则版本、Provider、模型、Prompt 和 Schema 版本。
- `gca report --run latest --format markdown|json` 可重建报告。
- Markdown 和 JSON 中的工作事项、证据数量一致。

#### FR-012：清理与卸载

`gca clean` 清理缓存/指定运行，`gca uninit` 删除 `.gca/`。

**验收标准**：

- 默认不删除身份映射和配置。
- `uninit` 要求显式确认或 `--yes`。
- 不修改被分析仓库的源码和 Git 历史。

### 4.2 非功能需求

#### NFR-001：性能

参考环境：8 核 CPU、16 GB 内存、NVMe SSD、Git 仓库约 15,000 commits。

- 首次确定性索引目标小于 15 分钟。
- 已索引仓库新增 100 commits 的同步目标小于 30 秒。
- 单用户半年范围的无 LLM 分析目标小于 60 秒。
- 峰值内存目标小于 2 GB。
- LLM 网络耗时不计入确定性性能门禁。

#### NFR-002：可重复性

- Git 事实结果必须完全确定。
- LLM 结果必须保存所有影响重放的版本信息。
- 相同 Provider 不保证文本逐字相同，但 Schema、Evidence 引用和安全规则必须稳定。

#### NFR-003：安全与隐私

- API Key 不进入仓库级配置、数据库明文字段、报告和日志。
- `.gcaignore` 默认排除常见密钥、证书、依赖和生成目录。
- 发送 LLM 前执行路径过滤、内容长度限制和敏感模式检测。
- 支持 `--no-llm` 完全离线分析。

#### NFR-004：兼容性

- Python 3.12 为首版运行时。
- Git 2.30+。
- Windows 10/11、当前 Ubuntu LTS、当前 macOS runner。
- SQLite 文件使用向前迁移，不保证新版本数据库被旧版本读取。

#### NFR-005：测试质量

- Domain/Application 行覆盖率不低于 90%。
- 全项目行覆盖率不低于 80%。
- 所有 CLI 命令至少有成功和失败路径测试。
- 所有 Provider 必须通过统一契约测试。

## 5. 总体架构

```text
                           +-----------------------+
                           |       gca CLI         |
                           | Typer + Rich + JSON   |
                           +-----------+-----------+
                                       |
                           +-----------v-----------+
                           |  Application Use Cases|
                           | init/index/sync/...   |
                           +-----------+-----------+
                                       |
              +------------------------+------------------------+
              |                        |                        |
    +---------v---------+    +---------v---------+    +---------v---------+
    | Domain Services   |    | Application Ports |    | DTO / Schemas     |
    | identity/delivery |    | git/store/llm/... |    | command/report    |
    +---------+---------+    +---------+---------+    +-------------------+
              |                        |
              +------------------------+------------------------------+
                                       |                              |
                 +---------------------v-----+            +-----------v--------+
                 | Adapters                  |            | Report Adapters     |
                 | Git/SQLite/LLM/Workspace  |            | Markdown/JSON       |
                 +---------------------------+            +--------------------+
```

### 5.1 依赖规则

```text
cli -> application -> domain
adapters -> application ports + domain
domain -> Python standard library only
```

- Domain 不导入 Typer、SQLAlchemy、PyDriller、httpx、Jinja2。
- Application 不导入具体 Provider 或 SQLite 实现。
- CLI 不直接执行 SQL、Git 命令或 HTTP 请求。
- Adapter 通过 Composition Root 注入 Use Case。

### 5.2 运行方式

每次 CLI 调用都是短生命周期进程：

1. 查找目标仓库和 `.gca/`。
2. 加载配置并校验版本。
3. 创建数据库会话和锁。
4. 组装 Application Use Case 与 Adapter。
5. 执行命令并提交事务。
6. 输出人类文本或 JSON。
7. 释放锁和资源。

## 6. 项目结构和文件计划

### 6.1 根目录文件

| 文件 | 操作 | 内容 |
|---|---|---|
| `pyproject.toml` | 新建 | 包元数据、依赖、`gca` entry point、pytest/coverage/ruff/mypy 配置 |
| `uv.lock` | 生成 | 锁定开发和发布依赖 |
| `README.md` | 新建 | 安装、快速开始、隐私说明和 CLI 示例 |
| `LICENSE` | 新建 | 首版采用 Apache-2.0，便于企业和开源复用 |
| `.gitignore` | 新建 | Python、构建、IDE、密钥和本地测试产物 |
| `.editorconfig` | 新建 | UTF-8、LF、4 空格和 Markdown 规则 |
| `.pre-commit-config.yaml` | 新建 | ruff、格式、文件尾和敏感信息基础检查 |
| `CHANGELOG.md` | 新建 | 版本变更记录 |
| `SECURITY.md` | 新建 | 漏洞报告和敏感仓库处理说明 |

### 6.2 Domain 层

路径：`src/git_contribution_analyzer/domain/`

| 文件 | 职责 |
|---|---|
| `models/repository.py` | Repository、RefSnapshot、DeliveryStatus |
| `models/person.py` | Person、IdentityAlias、IdentitySource、IdentityKind |
| `models/commit.py` | CommitRecord、CommitParent、FileChange、ChangeKind |
| `models/contribution.py` | ContributionItem、ContributionKind、Confidence |
| `models/evidence.py` | Evidence、EvidenceType、EvidenceReference |
| `models/assessment.py` | CapabilityAssessment、ContributionAssessment、ResumeBullet |
| `models/run.py` | AnalysisRun、RunStatus、RunWarning |
| `services/identity_resolution.py` | 候选生成、优先级和歧义判断 |
| `services/delivery_resolution.py` | authored/landed/released/reverted/duplicate 判定 |
| `services/contribution_clustering.py` | 确定性工作事项聚合 |
| `services/capability_rules.py` | 路径/变更/技术证据规则 |
| `services/confidence.py` | 置信度合成和证据缺口 |
| `errors.py` | 领域异常，不携带 CLI 退出码 |

### 6.3 Application 层

路径：`src/git_contribution_analyzer/application/`

#### Ports

| 文件 | 接口 |
|---|---|
| `ports/git_history.py` | `GitHistoryPort`：仓库发现、refs、commits、diff、可达性、patch-id、mailmap |
| `ports/repositories.py` | Repository/Person/Commit/AnalysisRun 仓储接口 |
| `ports/unit_of_work.py` | `UnitOfWork` 事务边界 |
| `ports/workspace.py` | `.gca/` 创建、配置、锁、exclude 和安全删除 |
| `ports/llm.py` | `LlmProvider`、能力声明、结构化任务请求 |
| `ports/reporting.py` | `ReportRenderer` |
| `ports/clock.py` | 可测试时钟 |
| `ports/id_generator.py` | 可测试 ID 生成器 |

#### Use Cases

| 文件 | 用例 |
|---|---|
| `use_cases/init_project.py` | 初始化工作区、数据库、配置和首次索引 |
| `use_cases/reindex_repository.py` | 全量重建索引 |
| `use_cases/sync_repository.py` | refs 差异和提交增量同步 |
| `use_cases/get_status.py` | 状态汇总 |
| `use_cases/run_doctor.py` | 环境和工作区诊断 |
| `use_cases/list_identities.py` | 身份列表和候选 |
| `use_cases/map_identity.py` | 人工身份映射 |
| `use_cases/analyze_contributions.py` | 确定性分析和可选 LLM 增强 |
| `use_cases/list_runs.py` | 分析运行查询 |
| `use_cases/generate_report.py` | 从 AnalysisRun 重建报告 |
| `use_cases/test_provider.py` | Provider 健康和 Schema 能力测试 |
| `use_cases/clean_workspace.py` | 安全清理缓存/运行 |
| `use_cases/uninit_project.py` | 删除工作区和本地 exclude 条目 |

#### DTO

| 文件 | 内容 |
|---|---|
| `dto/commands.py` | Init/Sync/Analyze/Report 等命令对象 |
| `dto/results.py` | Status/Identity/Analysis/Doctor 结果对象 |
| `dto/llm_tasks.py` | LLM 任务输入和上下文 |
| `dto/report.py` | 版本化报告模型 |

### 6.4 Git Adapter

路径：`src/git_contribution_analyzer/adapters/git/`

| 文件 | 职责 |
|---|---|
| `repository_discovery.py` | 查找仓库根目录、git-dir 和工作树状态 |
| `pydriller_history.py` | commit 元数据、修改文件和方法级信息遍历 |
| `native_git.py` | 安全执行 Git 子进程，参数列表调用，不使用 shell 拼接 |
| `refs.py` | heads/remotes/tags 快照与变化检测 |
| `reachability.py` | `merge-base --is-ancestor`、tag 包含关系 |
| `patch_id.py` | 稳定 patch-id 计算和重复提交关系 |
| `reverts.py` | revert message 和 patch 反向关系检测 |
| `mailmap.py` | `git check-mailmap` 集成 |
| `path_filters.py` | `.gcaignore`、默认排除和路径归一化 |

### 6.5 SQLite Adapter

路径：`src/git_contribution_analyzer/adapters/storage/sqlite/`

| 文件 | 职责 |
|---|---|
| `database.py` | Engine、WAL、foreign_keys、busy_timeout |
| `models.py` | SQLAlchemy ORM 映射 |
| `repositories.py` | Application repository ports 实现 |
| `unit_of_work.py` | Session 事务实现 |
| `migrations/env.py` | Alembic 环境 |
| `migrations/versions/0001_initial.py` | 初始 Schema |

### 6.6 LLM Adapter

路径：`src/git_contribution_analyzer/adapters/llm/`

| 文件 | 职责 |
|---|---|
| `base.py` | Provider 公共校验、重试、错误映射和脱敏日志 |
| `mock.py` | 测试 Provider |
| `openai_compatible.py` | OpenAI-compatible HTTP API |
| `anthropic.py` | Anthropic Messages API |
| `ollama.py` | Ollama 本地 HTTP API |
| `registry.py` | Provider 注册和工厂，不泄漏到 Application |
| `structured_output.py` | JSON 提取、Pydantic 校验和一次修复重试 |
| `cache.py` | 基于证据/Prompt/模型指纹的响应缓存 |

### 6.7 Prompt、规则和 Schema

| 文件 | 内容 |
|---|---|
| `prompts/commit_classification/v1.md` | commit/change set 分类 |
| `prompts/contribution_summary/v1.md` | 工作事项摘要 |
| `prompts/capability_assessment/v1.md` | 能力证据解释 |
| `prompts/resume_bullets/v1.md` | 简历候选生成 |
| `rules/default_capabilities.yml` | 数据库、缓存、并发、MQ、API、安全、测试等路径和变更规则 |
| `rules/default_noise.yml` | vendor、build、generated、format-only 等噪声规则 |
| `schemas/status/v1.json` | `status --json` Schema |
| `schemas/analysis/v1.json` | AnalysisRun 输出 Schema |
| `schemas/report/v1.json` | 报告 Schema |
| `schemas/llm/*.json` | 各 LLM 任务结构化输出 Schema |

### 6.8 Workspace Adapter

路径：`src/git_contribution_analyzer/adapters/workspace/`

| 文件 | 职责 |
|---|---|
| `layout.py` | `.gca/` 路径和文件命名 |
| `config.py` | YAML 配置、环境变量和优先级 |
| `locks.py` | 跨平台文件锁和陈旧锁检测 |
| `git_exclude.py` | `.git/info/exclude` 幂等维护 |
| `secrets.py` | 环境变量引用和日志脱敏 |

配置优先级固定为：

```text
CLI flags > environment variables > .gca/config.yml > user config > defaults
```

用户配置位置：

- Windows：`%APPDATA%/gca/config.yml`
- Linux/macOS：`${XDG_CONFIG_HOME:-~/.config}/gca/config.yml`

仓库级配置不得保存 API Key，只保存 `${ENV_VAR}` 引用。

### 6.9 Report Adapter

路径：`src/git_contribution_analyzer/adapters/reports/`

| 文件 | 职责 |
|---|---|
| `markdown.py` | Markdown 报告 |
| `json_report.py` | 版本化 JSON 输出 |
| `templates/contribution_report.md.j2` | 贡献报告模板 |
| `templates/resume_report.md.j2` | 简历候选模板 |

### 6.10 CLI 层

路径：`src/git_contribution_analyzer/cli/`

| 文件 | 职责 |
|---|---|
| `app.py` | Typer root app 和版本选项 |
| `bootstrap.py` | Composition Root |
| `context.py` | repository path、json、verbose 等全局上下文 |
| `output.py` | Rich/JSON 输出，不含业务判断 |
| `exit_codes.py` | 稳定退出码 |
| `commands/init.py` | `gca init` |
| `commands/index.py` | `gca index` |
| `commands/sync.py` | `gca sync` |
| `commands/status.py` | `gca status` |
| `commands/identities.py` | `gca identities list/map` |
| `commands/analyze.py` | `gca analyze` |
| `commands/runs.py` | `gca runs list/show` |
| `commands/report.py` | `gca report` |
| `commands/providers.py` | `gca providers list/test` |
| `commands/config.py` | `gca config show/set/import/export` |
| `commands/doctor.py` | `gca doctor` |
| `commands/clean.py` | `gca clean` |
| `commands/uninit.py` | `gca uninit` |

### 6.11 测试和发布文件

| 文件 | 职责 |
|---|---|
| `tests/unit/domain/*` | 领域规则测试 |
| `tests/unit/application/*` | Use Case 测试 |
| `tests/contract/llm/*` | Provider 契约测试 |
| `tests/integration/git/*` | 真实临时 Git 仓库测试 |
| `tests/integration/storage/*` | SQLite 迁移和事务测试 |
| `tests/e2e/cli/*` | CLI 端到端测试 |
| `tests/golden/*` | 黄金输入和期望报告 |
| `tests/helpers/git_repo_builder.py` | 构造 merge/revert/cherry-pick 等历史 |
| `.github/workflows/ci.yml` | 跨平台测试、lint、type check、coverage |
| `.github/workflows/release.yml` | wheel、sdist、standalone executable 构建 |
| `packaging/pyinstaller/gca.spec` | PyInstaller 配置 |

## 7. 数据模型与 SQLite Schema

### 7.1 Repository

表：`repositories`

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | TEXT | PK | UUID |
| root_path | TEXT | UNIQUE NOT NULL | 规范化绝对路径 |
| git_dir | TEXT | NOT NULL | Git 目录 |
| remote_url_hash | TEXT | NULL | 远程地址脱敏哈希 |
| default_branch | TEXT | NOT NULL | 默认目标分支 |
| object_format | TEXT | NOT NULL DEFAULT sha1 | Git 对象格式 |
| created_at | TEXT | NOT NULL | UTC ISO 时间 |
| updated_at | TEXT | NOT NULL | UTC ISO 时间 |

### 7.2 Ref Snapshot

表：`refs`

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| repository_id | TEXT | FK NOT NULL | Repository |
| ref_name | TEXT | NOT NULL | 完整 ref |
| commit_hash | TEXT | NOT NULL | 当前对象 |
| ref_type | TEXT | NOT NULL | HEAD/REMOTE/TAG |
| active | INTEGER | NOT NULL | ref 是否仍存在 |
| observed_at | TEXT | NOT NULL | 最近观察时间 |

唯一索引：`(repository_id, ref_name)`。

### 7.3 Person 与身份

表：`persons`

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | TEXT | PK | UUID |
| canonical_name | TEXT | NOT NULL | 规范名称 |
| canonical_email | TEXT | NULL | 规范邮箱 |
| kind | TEXT | NOT NULL | HUMAN/BOT/SYSTEM/SHARED/UNKNOWN |
| confirmed | INTEGER | NOT NULL | 是否人工确认 |
| created_at | TEXT | NOT NULL | UTC |

表：`identity_aliases`

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | TEXT | PK | UUID |
| repository_id | TEXT | FK NOT NULL | Repository |
| person_id | TEXT | FK NULL | 未确认时可空 |
| name | TEXT | NOT NULL | Git author name |
| email | TEXT | NOT NULL | Git author email |
| normalized_email | TEXT | NOT NULL | 规范化邮箱 |
| source | TEXT | NOT NULL | EXACT/MAILMAP/CONFIG/SUGGESTED/MANUAL |
| confidence | REAL | NOT NULL | 0..1 |
| confirmed | INTEGER | NOT NULL | 是否确认 |
| rationale | TEXT | NULL | 归一化依据 |

唯一索引：`(repository_id, name, email)`。

### 7.4 Commit 与父关系

表：`commits`

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| repository_id | TEXT | FK NOT NULL | Repository |
| hash | TEXT | NOT NULL | commit hash |
| author_alias_id | TEXT | FK NOT NULL | Author |
| committer_name | TEXT | NOT NULL | Committer name |
| committer_email | TEXT | NOT NULL | Committer email |
| authored_at | TEXT | NOT NULL | 带时区标准化时间 |
| committed_at | TEXT | NOT NULL | 带时区标准化时间 |
| subject | TEXT | NOT NULL | 首行 |
| body | TEXT | NOT NULL | 正文 |
| is_merge | INTEGER | NOT NULL | 父节点数 > 1 |
| tree_hash | TEXT | NOT NULL | Tree |
| patch_id | TEXT | NULL | 稳定 patch-id |
| insertions | INTEGER | NOT NULL | 文本新增行 |
| deletions | INTEGER | NOT NULL | 文本删除行 |
| files_changed | INTEGER | NOT NULL | 文件数 |
| indexed_at | TEXT | NOT NULL | 索引时间 |

主键：`(repository_id, hash)`。
索引：`author_alias_id, authored_at`、`patch_id`、`committed_at`。

表：`commit_parents`

主键：`(repository_id, commit_hash, parent_index)`，字段包含 `parent_hash`。

### 7.5 文件变更

表：`file_changes`

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | INTEGER | PK AUTOINCREMENT | 本地 ID |
| repository_id | TEXT | NOT NULL | Repository |
| commit_hash | TEXT | NOT NULL | Commit |
| old_path | TEXT | NULL | 旧路径 |
| new_path | TEXT | NULL | 新路径 |
| change_type | TEXT | NOT NULL | ADD/MODIFY/DELETE/RENAME/COPY |
| is_binary | INTEGER | NOT NULL | 二进制 |
| is_excluded | INTEGER | NOT NULL | 被规则排除 |
| insertions | INTEGER | NOT NULL | 新增 |
| deletions | INTEGER | NOT NULL | 删除 |
| language | TEXT | NULL | 语言 |
| content_fingerprint | TEXT | NULL | 内容/patch 指纹 |

索引：`(repository_id, commit_hash)`、`new_path`。

### 7.6 交付状态与关系

表：`commit_delivery`

| 字段 | 类型 | 说明 |
|---|---|---|
| repository_id | TEXT | Repository |
| commit_hash | TEXT | Commit |
| target_ref | TEXT | 判断目标 ref |
| status | TEXT | AUTHORED_ONLY/LANDED/RELEASED/REVERTED/DUPLICATE |
| release_ref | TEXT | 命中的 release tag |
| related_commit_hash | TEXT | revert/duplicate 对应 commit |
| evaluated_at | TEXT | 判断时间 |

主键：`(repository_id, commit_hash, target_ref)`。

### 7.7 AnalysisRun

表：`analysis_runs`

| 字段 | 类型 | 说明 |
|---|---|---|
| id | TEXT PK | ULID，便于按时间排序 |
| repository_id | TEXT | Repository |
| status | TEXT | PENDING/RUNNING/COMPLETED/PARTIAL/FAILED |
| parameters_json | TEXT | 规范化参数 |
| git_baseline_json | TEXT | refs 和索引版本 |
| rules_version | TEXT | 规则版本 |
| provider_id | TEXT NULL | Provider |
| model_id | TEXT NULL | 模型 |
| prompt_versions_json | TEXT | Prompt 版本 |
| schema_version | TEXT | 报告 Schema |
| started_at | TEXT | UTC |
| completed_at | TEXT NULL | UTC |
| warning_count | INTEGER | 告警数 |
| error_message | TEXT NULL | 脱敏错误 |

### 7.8 Contribution Item 与证据

表：`contribution_items`

| 字段 | 类型 | 说明 |
|---|---|---|
| id | TEXT PK | UUID |
| run_id | TEXT | AnalysisRun |
| person_id | TEXT | Person |
| kind | TEXT | FEATURE/FIX/REFACTOR/PERF/TEST/DOCS/OPS/SECURITY/OTHER |
| title | TEXT | 稳定标题 |
| deterministic_summary | TEXT | 规则摘要 |
| semantic_summary | TEXT NULL | LLM 摘要 |
| delivery_status | TEXT | 综合交付状态 |
| started_at | TEXT | 最早证据 |
| ended_at | TEXT | 最晚证据 |
| confidence | REAL | 聚合置信度 |
| clustering_key | TEXT | issue/branch/scope/path 指纹 |

表：`contribution_item_commits`

主键：`(contribution_item_id, repository_id, commit_hash)`。

表：`evidence`

| 字段 | 类型 | 说明 |
|---|---|---|
| id | TEXT PK | 可引用 ID |
| run_id | TEXT | AnalysisRun |
| contribution_item_id | TEXT NULL | 所属事项 |
| evidence_type | TEXT | COMMIT/FILE/REF/TAG/RULE/TEST/EXTERNAL |
| reference | TEXT | hash/path/ref/URL |
| fact_key | TEXT | 如 `delivery.landed` |
| fact_value_json | TEXT | 结构化事实 |
| source | TEXT | GIT/RULE/LLM/USER |
| confidence | REAL | 事实置信度 |

### 7.9 能力、简历和 LLM 审计

表：`capability_assessments`

- `id, run_id, person_id, capability_code, level_hint, rationale, confidence, evidence_ids_json, gaps_json`。

表：`resume_bullets`

- `id, run_id, person_id, contribution_item_id, wording, responsibility_level, evidence_ids_json, requires_review`。

表：`llm_invocations`

- `id, run_id, provider_id, model_id, task_type, prompt_version, schema_version, input_fingerprint, response_fingerprint, status, latency_ms, token_usage_json, error_code, created_at`。
- 不保存未经配置允许的完整源码 Prompt；默认只保存脱敏后的证据摘要和指纹。

### 7.10 迁移策略

- `0001_initial.py` 创建所有 MVP 表和索引。
- 每次 Schema 升级前复制 `index.sqlite` 为 `.gca/backups/index-<version>-<timestamp>.sqlite`。
- 数据库属于可重建索引；迁移失败时优先恢复备份，无法恢复时允许 `gca index --rebuild-db` 重建 Git 事实。
- AnalysisRun 和人工身份映射在重建前导出，避免与可重建 commit 索引一并丢失。

## 8. CLI 契约

### 8.1 全局选项

```text
gca [--repo PATH] [--json] [--quiet] [--verbose] [--no-color] COMMAND
```

- `--repo`：显式仓库路径；未提供时从当前目录向上查找。
- `--json`：输出版本化 JSON，不混入进度和日志。
- `--quiet`：只输出错误，适合 hooks/脚本。
- `--verbose`：输出阶段、耗时和诊断信息，不输出密钥。
- `--no-color`：关闭 ANSI 色彩。

### 8.2 子命令到 Use Case 映射

| CLI | Use Case | 写操作 |
|---|---|---|
| `gca init` | `InitProject` | 创建工作区和索引 |
| `gca index` | `ReindexRepository` | 重建索引 |
| `gca sync` | `SyncRepository` | 增量更新 |
| `gca status` | `GetStatus` | 否 |
| `gca doctor` | `RunDoctor` | 否，除非后续显式 `--repair` |
| `gca identities list` | `ListIdentities` | 否 |
| `gca identities map` | `MapIdentity` | 更新映射 |
| `gca analyze` | `AnalyzeContributions` | 创建 AnalysisRun |
| `gca runs list/show` | `ListRuns/GetRun` | 否 |
| `gca report` | `GenerateReport` | 创建报告文件 |
| `gca providers list/test` | `ListProviders/TestProvider` | 否 |
| `gca config show/set/import/export` | `ManageConfig` | 部分 |
| `gca clean` | `CleanWorkspace` | 删除指定缓存/运行 |
| `gca uninit` | `UninitProject` | 删除工作区 |

### 8.3 稳定退出码

| 退出码 | 常量 | 含义 |
|---|---|---|
| 0 | `SUCCESS` | 成功 |
| 2 | `INVALID_USAGE` | 参数或配置错误 |
| 3 | `NOT_A_REPOSITORY` | Git 仓库不可用 |
| 4 | `WORKSPACE_ERROR` | 索引、迁移、锁或工作区错误 |
| 5 | `IDENTITY_AMBIGUOUS` | 身份歧义 |
| 6 | `PROVIDER_ERROR` | Provider 失败且不允许降级 |
| 7 | `REPORT_ERROR` | 报告生成失败 |
| 8 | `INTERRUPTED` | 用户中断 |
| 10 | `INTERNAL_ERROR` | 未分类内部错误，必须记录 run/error id |

### 8.4 JSON 输出封装

所有 `--json` 输出使用统一 envelope：

```json
{
  "schemaVersion": "1.0",
  "command": "status",
  "success": true,
  "data": {},
  "warnings": [],
  "error": null
}
```

失败时 stdout 仍输出 JSON envelope，诊断日志写 stderr，退出码按表返回。

## 9. Git 索引与分析算法

### 9.1 索引 refs 范围

默认包含：

- `refs/heads/*`
- `refs/remotes/origin/*`
- `refs/tags/*`

默认排除：

- `refs/pull/*`
- `refs/merge-requests/*`
- 临时 refs、replace refs 和配置排除项。

索引 commit 对象按 hash 去重，ref 只保存引用关系。

### 9.2 全量索引

1. 获取仓库对象格式、refs 和默认分支。
2. 计算所有配置 refs 可达 commit hash 集合。
3. 按拓扑/时间顺序分批读取 commit。
4. 创建 IdentityAlias。
5. 读取父关系、numstat、rename、二进制和路径过滤结果。
6. 对非 merge 文本提交计算稳定 patch-id。
7. 分批写入 SQLite，每批事务提交。
8. 记录 ref snapshot 和索引基线。
9. 运行完整性校验：commit 数、孤立父引用、重复 alias、Schema 版本。

### 9.3 增量同步

1. 读取旧 ref snapshot。
2. 获取新 refs，分类新增、前移、后退、删除。
3. 对新增可达 commit 执行相同索引流水线。
4. 保留不再被当前 ref 引用的 commit，标记 `reachable=false`，避免丢失历史 AnalysisRun 证据。
5. 重新计算受影响 ref 的 delivery 状态。
6. 只失效涉及新增/变化 commit 的分析缓存。

### 9.4 身份归一化优先级

```text
MANUAL > CONFIG > MAILMAP > EXACT EMAIL > SUGGESTED
```

建议候选规则：

- 完全相同邮箱，不同名称：高置信度候选。
- 邮箱 local-part 相同、域名变化：中置信度候选。
- 名称相同、邮箱不同：中置信度候选，不自动合并。
- `system/bot/ci` 名称或 noreply 邮箱：机器人/系统候选。
- committer 与 author 不同不代表同一人。

### 9.5 交付状态

对每个分析目标 ref 计算：

```text
AUTHORED_ONLY: 不可从目标 ref 到达
LANDED: 可从目标 ref 到达
RELEASED: 可从选定 release tag 到达
REVERTED: 存在已进入目标 ref 的有效 revert
DUPLICATE: patch-id 与另一交付 commit 相同，净贡献只保留一份
```

优先级：`REVERTED > RELEASED > LANDED > AUTHORED_ONLY`，`DUPLICATE` 作为附加关系而非覆盖原始事实。

### 9.6 噪声和净变更

默认噪声分类：

- 依赖锁文件和 vendored code。
- build/target/dist/node_modules 等产物。
- 二进制媒体和压缩包。
- 纯格式化或行尾变化。
- 自动生成文档和代码。
- Merge commit 本身。

噪声不删除，只在贡献聚合中降低权重并单独展示。

### 9.7 Contribution Item 聚合

确定性聚合顺序：

1. 提取 commit message 中的 issue/PR/TAPD 标识。
2. 提取 Conventional Commit scope。
3. 分支名称或 merge source 线索。
4. 主要目录/模块重叠。
5. 7 天默认时间窗口。
6. patch/revert/duplicate 关系。

聚合评分达到阈值时合并；边界分数保留为候选并允许 LLM建议，但 LLM 不直接修改原始证据关系。

### 9.8 能力规则

首批能力代码：

```text
backend.api
backend.service_design
data.sql
data.modeling
data.transaction
cache.redis
concurrency.locking
messaging.mq
security.auth
security.secrets
performance.optimization
testing.unit
testing.integration
architecture.cross_module
delivery.documentation
delivery.release
```

每条规则输出 Evidence，不直接输出“高级/专家”。等级候选由证据数量、持续时间、复杂度和反向证据共同计算，并标记为需人工复核。

## 10. LLM 设计

### 10.1 Provider Port

```python
class LlmProvider(Protocol):
    @property
    def provider_id(self) -> str: ...

    def capabilities(self) -> ModelCapabilities: ...

    def health_check(self) -> ProviderHealth: ...

    def analyze(
        self,
        task: AnalysisTask,
        output_model: type[BaseModel],
    ) -> BaseModel: ...
```

`AnalysisTask` 仅包含脱敏、裁剪后的结构化证据和 Prompt 版本，不暴露数据库 Session 或文件句柄。

### 10.2 Provider 能力声明

```python
class ModelCapabilities(BaseModel):
    structured_output: bool
    json_mode: bool
    max_context_tokens: int | None
    local_execution: bool
    tool_calling: bool
```

Application 根据能力选择 JSON Schema、纯 JSON Prompt 或禁用不支持任务。

### 10.3 首批 LLM 任务

| 任务 | 输入 | 输出 |
|---|---|---|
| `commit_classification` | commit message、路径、numstat、有限 diff 摘要 | kind、scope、confidence、evidence refs |
| `contribution_summary` | 聚合后的 commit 和规则证据 | title、summary、responsibility wording |
| `capability_assessment` | capability evidence 和反向证据 | rationale、level hint、confidence、gaps |
| `resume_bullets` | 已确认工作事项和能力证据 | 中文候选描述、责任等级、需补充指标 |

### 10.4 结构化输出和失败处理

1. Provider 返回后先提取 JSON。
2. 使用 Pydantic 严格校验。
3. 失败时使用同一 Provider 执行一次“只修复结构”请求。
4. 再失败则记录 invocation，并按配置降级。
5. 不允许把未校验文本写入正式报告结论。

### 10.5 Provider 配置

```yaml
llm:
  enabled: true
  provider: openai-compatible
  model: example-model
  base_url: ${GCA_LLM_BASE_URL}
  api_key: ${GCA_LLM_API_KEY}
  timeout_seconds: 60
  max_retries: 3
  allow_fallback_to_rules: true
```

### 10.6 缓存键

```text
SHA256(
  task_type + evidence_fingerprint + prompt_version + schema_version
  + provider_id + model_id + normalized_generation_options
)
```

任何证据、Prompt、Schema、Provider 或模型变化都产生新缓存项。

## 11. 报告设计

### 11.1 Markdown 章节

1. 分析范围与口径。
2. 身份归一化结果和未决身份。
3. 贡献摘要。
4. 交付工作事项时间线。
5. 主要业务域和模块。
6. 技术能力证据。
7. 工程质量与风险信号。
8. 协作和所有权证据。
9. 简历候选描述。
10. 证据索引。
11. 数据缺口、警告和人工复核项。

### 11.2 事实与推断标识

报告中的每条内容明确标记：

- `FACT`：Git/外部系统直接事实。
- `RULE_INFERENCE`：确定性规则推断。
- `LLM_INFERENCE`：LLM 推断。
- `HUMAN_CONFIRMED`：人工确认。

### 11.3 简历措辞规则

- `主导`：关键设计和核心变更连续证据充分，且无主要他人承担证据。
- `负责`：主要提交、交付和维护证据充分。
- `参与`：存在有效贡献，但无法证明主要责任。
- `协助`：仅有局部或配套贡献。
- 百分比、用户量、收入、成本、稳定性提升必须引用外部或基准 Evidence。

## 12. 实施阶段

### 阶段 1：工程骨架、CLI 和工作区

**目标**：建立可安装的 `gca` CLI、模块边界、配置、工作区和 SQLite 基础。

**任务**：

1. 创建根目录工程文件、Python package 和依赖锁。
2. 创建 Domain/Application/Adapters/CLI 空模块和依赖约束测试。
3. 实现 `gca --help/--version`。
4. 实现 Repository Discovery 和 `.gca/` Layout。
5. 实现配置加载、环境变量引用和日志脱敏。
6. 实现跨平台锁和 `.git/info/exclude` 幂等维护。
7. 创建 SQLAlchemy Engine、Alembic 和 `0001_initial`。
8. 实现 `gca init/status/doctor/uninit` 的最小闭环。
9. 配置 ruff、mypy、pytest、coverage、pre-commit 和三平台 CI。

**交付物**：

- 可通过 `pipx` 或开发环境调用的 `gca`。
- 初始化后的 `.gca/config.yml`、`meta.json`、`index.sqlite`。
- 基础 CLI JSON envelope 和退出码。
- 跨平台 CI 绿色。

**验收标准**：

- [ ] `gca --help` 三平台通过。
- [ ] `gca init` 对空 Git 仓库成功且幂等。
- [ ] 非 Git 目录返回退出码 `3`。
- [ ] `status --json` 通过 JSON Schema 校验。
- [ ] `uninit --yes` 只删除 `.gca/` 和对应 exclude 条目。

**预计工作量**：4-6 工程日。

### 阶段 2：Git 全量/增量索引与身份归一化

**目标**：可靠索引真实 Git 历史并提供身份管理。

**任务**：

1. 实现 Native Git 安全执行器和版本检查。
2. 实现 refs 快照、commit 遍历、父关系和 file changes。
3. 集成 PyDriller，处理 rename、delete、binary 和 numstat。
4. 实现全量分批事务索引和完整性校验。
5. 实现 ref diff 和增量同步。
6. 实现 `.mailmap`、exact email 和候选身份规则。
7. 实现 `identities list/map`。
8. 实现 patch-id、目标分支可达性、tag 包含和基础 revert 检测。
9. 实现 `index/sync/status` 完整统计。

**交付物**：

- 可索引大型真实仓库的 SQLite 数据。
- 可审计的 Person/IdentityAlias 映射。
- commit delivery 和重复 patch 关系。
- Git 历史集成测试仓库构造器。

**验收标准**：

- [ ] merge、rename、binary、revert、cherry-pick、force-push fixture 全部通过。
- [ ] 生成式黄金仓库的 commit/author 基础计数与 Git 原生命令一致。
- [ ] 新增 100 commits 的增量同步不重扫全部历史。
- [ ] 模糊身份保持 unresolved。
- [ ] 数据库异常不会留下半批 commit。

**预计工作量**：8-12 工程日。

### 阶段 3：确定性贡献分析和报告

**目标**：在完全无 LLM 情况下产出可用贡献报告。

**任务**：

1. 实现分析参数解析和 Person 唯一定位。
2. 实现时间、分支、release、scope 过滤。
3. 实现噪声规则、模块统计、提交类型和净变更统计。
4. 实现 Contribution Item 确定性聚合。
5. 实现首批 capability rules 和 Evidence 生成。
6. 实现 AnalysisRun 状态机和失败/部分成功恢复。
7. 实现 Markdown/JSON 报告和证据索引。
8. 实现 `gca analyze --no-llm`、`runs list/show`、`report`。
9. 为生成式黄金仓库生成固定结果并人工复核。

**交付物**：

- 无 LLM 的端到端贡献分析。
- 版本化 analysis/report JSON Schema。
- Markdown 贡献和简历证据基础报告。
- 黄金测试结果。

**验收标准**：

- [ ] 相同输入重复运行 JSON 逐字一致，时间/ID 字段使用测试注入固定。
- [ ] 报告计数可由 Git 命令复核。
- [ ] authored/landed/released/reverted 状态正确。
- [ ] 所有 Contribution Item 有 Evidence。
- [ ] 未确认身份阻止错误分析并返回退出码 `5`。

**预计工作量**：8-10 工程日。

### 阶段 4：LLM Provider 和语义增强

**目标**：在不改变核心框架的情况下使用不同 LLM 增强报告。

**任务**：

1. 定义 `LlmProvider`、Task、Capabilities 和错误模型。
2. 实现 Mock Provider 和通用契约测试。
3. 实现 OpenAI-compatible、Anthropic、Ollama Provider。
4. 实现 httpx 超时、重试、限流错误映射和脱敏日志。
5. 创建四类 Prompt、Pydantic 输出模型和 JSON Schema。
6. 实现结构化输出修复重试和规则降级。
7. 实现 LLM cache 和 invocation 审计。
8. 实现 `providers list/test`。
9. 将语义摘要、能力解释、简历候选接入 AnalysisRun。
10. 建立 Mock 黄金测试和可选真实 Provider smoke test。

**交付物**：

- 四个 Provider Adapter。
- 可版本化和重放的 Prompt/Schema。
- 可追溯的 LLM 调用记录。
- 支持 Provider 切换和 `--no-llm` 降级。

**验收标准**：

- [ ] Domain/Application 不导入任何具体 Provider。
- [ ] Mock、OpenAI-compatible、Anthropic、Ollama 通过统一契约测试。
- [ ] Provider 超时允许降级时报告标记 `PARTIAL` 而非失败。
- [ ] 所有 LLM 结论含 Evidence ID。
- [ ] 结构化输出不合法时不会写入正式结论。

**预计工作量**：7-10 工程日。

### 阶段 5：跨平台发布、性能和文档

**目标**：将 MVP 变成可安装、可验证和可交付的独立工具。

**任务**：

1. 完成 README、CLI Reference、Provider Guide、Privacy 和 Methodology 文档。
2. 完成 wheel/sdist 构建和 `pipx` 安装测试。
3. 使用 PyInstaller 或等价工具构建三平台可执行程序。
4. 验证 Windows `.exe/.cmd` 入口，不依赖 `.ps1`。
5. 在参考仓库执行性能基准和内存分析。
6. 优化批处理、SQLite 索引和 diff 缓存。
7. 执行完整安全检查、密钥扫描和日志审计。
8. 生成 `0.1.0` 发布说明和升级/卸载说明。

**交付物**：

- wheel、sdist 和跨平台安装产物。
- 完整用户文档。
- 性能基准报告。
- `0.1.0` 候选版本。

**验收标准**：

- [ ] 三平台安装后可运行 `gca --help`。
- [ ] Windows 受限 PowerShell 环境仍可调用 `gca.exe` 或 `gca.cmd`。
- [ ] 约 15,000 commits 仓库满足确定性性能目标或记录已批准偏差。
- [ ] 报告和日志不包含测试密钥或未脱敏源码。
- [ ] 全项目覆盖率不低于 80%，核心层不低于 90%。

**预计工作量**：5-7 工程日。

### 12.1 阶段依赖

```text
阶段 1 -> 阶段 2 -> 阶段 3 -> 阶段 4 -> 阶段 5
                    |                    |
                    +---- 可先发布 0.1.0-alpha(no-llm)
```

建议在阶段 3 完成后发布 `0.1.0-alpha.1`，先验证确定性事实和报告口径，再引入 LLM，避免模型输出掩盖底层错误。

## 13. 测试策略

### 13.1 单元测试

#### Domain

- `test_identity_resolution.py`
  - `should_merge_alias_candidate_when_email_exactly_matches()`
  - `should_not_auto_merge_when_only_name_matches()`
  - `should_prefer_manual_mapping_over_mailmap()`
  - `should_classify_system_identity_when_rule_matches()`
- `test_delivery_resolution.py`
  - `should_mark_authored_only_when_commit_not_reachable()`
  - `should_mark_landed_when_commit_reachable_from_target()`
  - `should_mark_released_when_commit_reachable_from_tag()`
  - `should_link_revert_to_reverted_commit()`
  - `should_mark_duplicate_relation_when_patch_id_matches()`
- `test_contribution_clustering.py`
  - `should_group_commits_when_issue_key_matches()`
  - `should_group_commits_when_scope_path_and_time_match()`
  - `should_keep_items_separate_when_confidence_below_threshold()`
- `test_capability_rules.py`
  - 数据库、缓存、事务、MQ、并发、测试和跨模块规则各至少一正一反用例。
- `test_confidence.py`
  - 证据、反向证据和缺口对置信度的影响。

#### Application

- `test_init_project.py`：成功、幂等、非仓库、已有损坏工作区。
- `test_sync_repository.py`：新增 ref、fast-forward、force-push、删除 ref、事务失败。
- `test_map_identity.py`：新建 Person、合并确认、冲突拒绝。
- `test_analyze_contributions.py`：无 LLM、Provider 成功、Provider 降级、身份歧义。
- `test_generate_report.py`：latest、指定 run、格式错误和文件写入失败。

### 13.2 Git 集成测试

通过 `GitRepoBuilder` 在临时目录构造真实历史：

1. 线性提交。
2. Feature branch 合并。
3. 未合入分支。
4. Annotated/lightweight tag。
5. rename 和 delete。
6. binary file。
7. revert。
8. cherry-pick 和相同 patch-id。
9. squash merge。
10. force-push/ref 回退。
11. 同邮箱多名称和 `.mailmap`。
12. author 与 committer 不同。

每个 fixture 同时使用 Git 原生命令生成期望值，不手写不可验证的计数。

### 13.3 SQLite 集成测试

- 初始迁移和空数据库。
- 重复迁移幂等。
- 外键约束和事务回滚。
- WAL/锁并发。
- 备份和迁移恢复。
- 删除 ref 后 commit 保留。
- AnalysisRun 与 Evidence 级联边界。

### 13.4 LLM 契约测试

所有 Provider 运行同一测试集：

- health check。
- 结构化成功响应。
- 非法 JSON。
- 超时。
- 401/403 认证错误。
- 429 限流。
- 5xx 重试。
- 内容超限。
- 敏感字段不进入日志。

真实网络 Provider 测试默认不在普通 CI 执行，只在有安全 Secret 的手动 smoke workflow 运行。

### 13.5 CLI E2E

- `gca --help/--version`。
- `init -> status -> sync -> identities -> analyze --no-llm -> report -> uninit` 完整流程。
- `--json` stdout 纯 JSON，stderr 独立。
- 所有退出码。
- Ctrl+C 返回 `8`，不遗留锁。
- 路径含空格和中文。
- Windows PowerShell 与 `cmd.exe` 调用。

### 13.6 黄金测试

黄金测试包含：

- 小型可公开 fixture 仓库及固定历史。
- 生成式公开 fixture 的固定统计快照。
- 确定性 JSON 期望文件。
- Mock Provider 固定语义输出。
- Markdown 快照，仅忽略生成时间和 run id。

### 13.7 性能测试

命令：

```bash
pytest tests/performance -m performance
```

场景：

- 15,000 commits 首次 index。
- 100 commits sync。
- 单人 6 个月 no-LLM analyze。
- 10,000 Evidence 报告生成。
- SQLite 2 个并发只读状态查询和 1 个写锁冲突。

## 14. 可观测性和审计

### 14.1 日志

- 默认 INFO，人类可读。
- `--verbose` 输出阶段、计数和耗时。
- `--json` 时业务结果走 stdout，日志走 stderr。
- 日志字段包含 `run_id`、`repository_id`、`command`、`stage`。
- API Key、Authorization、源码正文和完整远程 URL 默认脱敏。

### 14.2 AnalysisRun 状态

```text
PENDING -> RUNNING -> COMPLETED
                   -> PARTIAL
                   -> FAILED
```

- Provider 降级为 `PARTIAL`。
- 用户中断为 `FAILED`，错误码 `INTERRUPTED`，已提交事实索引保留。
- 每个阶段记录开始、结束、计数和 warning。

### 14.3 审计

- 保存命令参数的规范化版本，不保存 secret 值。
- 保存 Git refs 基线和工具版本。
- 保存规则/Prompt/Schema/Provider/模型版本。
- 人工修改必须形成 HumanReview，不能覆盖原始推断。

## 15. 安全设计

### 15.1 Git 命令执行

- 使用参数数组调用 subprocess，不使用 `shell=True`。
- 仓库路径使用 resolve 后的绝对路径。
- 不执行仓库中的 hook、脚本或配置命令别名。
- 对 Git 输出设置大小、超时和编码处理。

### 15.2 LLM 数据最小化

- 默认只发送 commit subject、路径、统计、规则证据和裁剪后的 diff 摘要。
- `.gcaignore` 和默认规则在读取内容前生效。
- 检测 PEM、token、password、secret 等高风险模式并删除内容。
- 本地 Ollama 模式标记 `local_execution=true`。
- 报告注明是否向外部 Provider 发送数据。

### 15.3 工作区安全

- `.gca/` 文件权限按当前用户最小化。
- `uninit` 只允许删除经 Workspace Layout 验证的 `.gca/` 路径。
- 禁止根据未校验配置递归删除任意路径。
- 数据库备份和报告同样遵循敏感数据规则。

## 16. 向后兼容和版本策略

### 16.1 CLI

- `0.x` 可调整命令，但必须在 CHANGELOG 标记。
- 稳定后的命令至少一个 minor 版本发出 deprecation 警告再删除。
- JSON Schema 使用独立版本，不与工具版本绑定。
- 退出码视为公开契约。

### 16.2 数据库

- 只允许 Alembic 向前迁移。
- 启动时检测数据库比工具更新则拒绝运行，避免旧程序破坏数据。
- Git 事实可重建，身份人工映射和 HumanReview 必须备份迁移。

### 16.3 Provider

- Provider ID 稳定，例如 `openai-compatible`、`anthropic`、`ollama`、`mock`。
- Provider 特有参数放在命名空间配置，不污染核心配置。
- 不支持某项能力时显式声明，Application 决定降级。

## 17. 回滚和故障恢复

### 17.1 初始化/索引失败

- 新工作区初始化失败：删除临时 `.gca/.staging-*`，不留下半成品。
- 已有索引更新失败：事务回滚，保留上次成功基线。
- 数据库损坏：恢复最近备份或 `gca index --rebuild-db`。

### 17.2 LLM 失败

- 允许降级：AnalysisRun 标记 `PARTIAL`，保留确定性报告。
- 不允许降级：退出码 `6`，不写入未校验推断。
- 切换 Provider：新建 AnalysisRun，不覆盖旧结果。

### 17.3 发布回滚

- PyPI/内部源保留上一版本 wheel。
- 单文件可执行程序按版本目录发布。
- 工具版本回滚前检查 SQLite Schema；如不兼容则使用备份数据库或重建索引。

### 17.4 数据清理

- `clean --cache` 仅删除可重建缓存。
- `clean --runs <id>` 删除运行前要求确认并检查 HumanReview。
- `uninit` 默认交互确认；CI 使用 `--yes`。

## 18. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| PyDriller 与 Git 边缘语义不一致 | 中 | 高 | 关键语义使用原生 Git，黄金 fixture 双重验证 |
| 大仓库首次扫描慢 | 高 | 中 | 分批、增量、路径过滤、SQLite 索引和性能基准 |
| 身份误合并 | 中 | 高 | 模糊候选不自动合并，保存来源和人工确认 |
| LLM 过度归因 | 高 | 高 | Evidence 强制引用、结构校验、责任措辞规则和人工复核 |
| 模型更换结果漂移 | 高 | 中 | 版本化 Prompt/Schema、缓存指纹和黄金评测 |
| 私有代码外传 | 中 | 高 | 默认裁剪、敏感检测、本地模式、明确 Provider 状态 |
| Windows 包装失败 | 中 | 中 | Windows CI、pipx 与 standalone 两条发布路径 |
| SQLite 锁冲突 | 低 | 中 | 单写锁、WAL、busy_timeout 和清晰诊断 |
| 报告被直接当成绩效结论 | 中 | 高 | 默认多维证据、显著免责声明、不生成单一总分 |
| scope 膨胀到平台项目 | 高 | 中 | 0.1.0 非目标固定，阶段 3 后先发布 alpha 验证 |

## 19. 文档计划

| 文件 | 内容 |
|---|---|
| `README.md` | 安装、5 分钟快速开始、输出示例 |
| `doc/architecture/architecture.md` | 分层、依赖规则、数据流和扩展点 |
| `doc/architecture/data-model.md` | SQLite Schema 和迁移策略 |
| `doc/architecture/llm-provider.md` | Provider 开发契约和测试要求 |
| `doc/cli/cli-reference.md` | 所有命令、参数、输出和退出码 |
| `doc/guides/privacy.md` | 私有代码和外部模型数据边界 |
| `doc/guides/methodology.md` | 贡献和能力评估方法、限制和免责声明 |
| `doc/guides/custom-rules.md` | 自定义能力/噪声规则 |
| `doc/testing/golden-dataset.md` | 黄金数据构造和更新规则 |
| `doc/releases/0.1.0.md` | 发布说明和已知限制 |

## 20. 完成定义

MVP 只有在以下条件全部满足时才算完成：

- [ ] `gca` 在 Windows、Linux、macOS 可安装和执行。
- [ ] init/index/sync/status/doctor/uninit 生命周期完整。
- [ ] Git 索引覆盖 merge、revert、cherry-pick、rename、binary 和 force-push。
- [ ] 身份归一化可审计，模糊身份不会静默合并。
- [ ] `analyze --no-llm` 能生成可复核 Markdown/JSON。
- [ ] 四个 Provider 通过契约测试，LLM 失败可降级。
- [ ] 所有 LLM 推断引用 Evidence，并记录版本。
- [ ] 报告不会把提交数或代码行数直接转换为绩效等级。
- [ ] 全项目覆盖率 >= 80%，核心层 >= 90%。
- [ ] 跨平台 CI、lint、type check、test、package 全部通过。
- [ ] 参考仓库性能达到目标或偏差经过记录和批准。
- [ ] README、CLI、Provider、隐私和方法论文档完整。

## 21. 实施顺序

批准本计划后，实施必须按以下顺序进行：

1. 阶段 1：工程骨架和工作区。
2. 阶段 2：Git 索引和身份归一化。
3. 阶段 3：无 LLM 确定性分析，发布 alpha。
4. 使用生成式黄金 fixture 校准事实口径。
5. 阶段 4：接入可替换 LLM。
6. 阶段 5：跨平台发布和 0.1.0 验收。

编码阶段采用测试驱动顺序：先提交失败测试，再实现最小行为，最后重构；每一阶段完成后单独运行完整回归，不跨阶段堆积未验证功能。
