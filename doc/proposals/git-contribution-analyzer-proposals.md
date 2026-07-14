# 提案：Git Contribution Analyzer 独立项目

## 1. 需求摘要

### 1.1 项目目标

建设一个独立、可复用的研发贡献分析工具，从 Git 仓库及可选的 PR、需求、CI、发布数据中提取证据，回答以下问题：

1. 某个用户在指定时间内实际参与并交付了哪些工作。
2. 这些工作覆盖了哪些业务领域、技术模块和工程能力。
3. 贡献的复杂度、质量、交付影响和协作特征如何。
4. 如何生成可追溯的团队绩效证据和简历总结候选内容。
5. 如何在不改变项目主体框架的情况下替换 OpenAI、Anthropic、Ollama、本地模型或其他 LLM。
6. 如何像 CodeGraph 一样提供可安装的 CLI，在任意 Git 仓库中完成初始化、索引、增量同步、分析和报告生成。

### 1.2 核心原则

- 事实与推断分离：Git、PR、需求和 CI 数据是事实；能力和贡献判断是带置信度的推断。
- 证据可追溯：每条结论必须能回溯到 commit、PR、issue、release 或测试记录。
- 不以提交量定绩效：提交数、代码行数和活跃时间只作为背景数据，不直接转换为绩效分数。
- 交付优先：区分“开发过”“合入主干”“进入发布版本”和“产生实际效果”。
- 人工可复核：绩效报告和简历总结必须支持经理或本人确认、修订和驳回。
- LLM 可替换：核心领域模型、分析流程和报告格式不依赖任何具体模型厂商。
- 本地优先：支持只在本机处理代码和使用本地模型，避免敏感代码外传。
- CLI 优先：命令行是首要产品入口，REST API、Web UI 和 MCP 均建立在同一应用层之上。

### 1.3 功能需求

#### CLI 产品入口

- 安装后提供稳定的 `gca` 命令，支持 Windows、Linux 和 macOS。
- 可以在任意 Git 仓库根目录执行 `gca init`，创建项目级分析工作区。
- 支持全量索引、增量同步、状态检查、身份管理、贡献分析和报告导出。
- 所有核心命令支持人类可读输出，并在适用时支持 `--json` 机器可读输出。
- LLM 不可用时支持 `--no-llm`，仍可完成确定性 Git 分析。
- CLI 只负责参数解析和结果展示，业务逻辑统一调用 Application Use Cases。

#### 数据采集

- 扫描本地 Git 仓库、裸仓库或远程克隆后的仓库。
- 读取 commit、author、committer、branch、tag、merge、diff、numstat、rename 和 revert 信息。
- 支持限定用户、时间范围、目标分支、发布标签和路径范围。
- 可选接入 GitHub、GitLab、Gitee、Jira、TAPD、CI 和发布系统。

#### 身份归一化

- 合并同一人的多个 name/email。
- 支持 `.mailmap`、项目配置和人工确认三种来源。
- 区分个人账号、机器人账号、系统合并账号和共享账号。
- 保存归一化理由，避免静默合并错误身份。

#### 工作事项识别

- 将相关 commit、PR、分支、issue 和文档聚合成一个 Contribution Item。
- 识别功能开发、缺陷修复、重构、性能优化、测试、文档、运维和安全治理。
- 识别重复 cherry-pick、squash、rebase、merge 和 revert，避免重复计数。
- 区分未合入分支、已合入主干和已发布版本。

#### 能力与贡献分析

- 分析业务领域、模块所有权、跨模块影响和依赖范围。
- 分析数据库、缓存、并发、MQ、接口、安全、性能、测试和架构等技术能力证据。
- 分析交付、质量、复杂度、协作和长期维护等贡献维度。
- 对每个推断输出置信度、正向证据、反向证据和证据缺口。

#### 报告输出

- 个人贡献时间线。
- 工作事项清单及证据链接。
- 能力画像与置信度。
- 绩效评估辅助报告，不直接替代管理者评价。
- 简历项目总结和 STAR/XYZ 风格候选描述。
- Markdown、JSON、HTML 和可选 PDF 导出。

### 1.4 非功能需求

| 项目 | 要求 |
|---|---|
| 可替换性 | LLM Provider 通过稳定接口接入，核心层不依赖厂商 SDK |
| 可重复性 | 相同代码、配置、Prompt 版本和模型版本能够重放分析 |
| 可审计性 | 保存规则版本、Prompt 版本、模型信息、输入证据和原始结构化输出 |
| 隐私 | 支持完全离线模式、路径脱敏和敏感文件排除 |
| 性能 | 首次全量扫描可增量缓存，后续只分析新增提交 |
| 稳定性 | LLM 超时、限流或结构化输出失败不影响基础 Git 分析结果 |
| 可测试性 | Git 解析、聚合、评分、Provider 和报告层均可独立测试 |
| 扩展性 | 后续可增加新的代码托管平台、需求系统、能力规则和报告模板 |

## 2. 当前问题与可借鉴基础

### 2.1 大型仓库验证出的现实问题

使用不记录项目名和人员身份的私有规模基准，已经观察到以下典型问题：

- 仓库历史规模超过一万条提交，不能逐条人工审阅。
- 同一开发者可能使用多个邮箱和作者名。
- 共享自动化身份可能包含大量合并提交，不能直接归为个人贡献。
- 同一功能可能分散在 Service、Admin、API、Common、SQL、测试和文档中。
- 提交信息可以帮助分类，但不能单独证明业务影响和技术质量。
- `--all` 中可能包含废弃分支；只有进入目标分支或发布标签的内容才属于实际交付。

### 2.2 可借鉴的开源项目

| 项目 | 可借鉴内容 | 不直接采用的原因 |
|---|---|---|
| Apache DevLake | DevOps 数据采集、插件化连接器、指标模型、Grafana 展示 | 偏团队指标平台，不理解代码业务语义 |
| PyDriller | Commit、Diff、方法级变更和仓库遍历 | 只负责挖掘，不负责贡献归并和能力判断 |
| GrimoireLab | 身份合并、社区贡献和长期趋势分析 | 系统较重，主要面向组织和社区分析 |
| git-fame | 当前代码归属和作者统计 | 无法覆盖被删除、替换或重构后的历史贡献 |
| Gource | 按目录和作者展示代码演化 | 适合展示，不适合审计和评估 |
| CodeGraph | `init/index/sync/status/query` 的仓库本地 CLI 生命周期、增量索引和状态检查 | 面向代码图谱，不负责历史贡献、绩效证据和简历总结 |
| Understand Anything | 代码知识图谱、节点依赖和变更影响范围 | 当前能力偏单次 Diff，需要扩展为历史工作事项分析 |

## 3. 提议的方法

### 方法一：Python 模块化单体 + PyDriller + LLM Provider SPI

#### 概述

使用 Python 构建独立 CLI 和 REST 服务，以 PyDriller/Git 命令完成仓库挖掘，以固定领域模型组织数据，通过 Provider 接口接入不同 LLM。这是最适合快速形成可用产品的方案。

#### 总体结构

```text
CLI (`gca`) / REST API / optional MCP
                  |
Application Use Cases
                  |
Contribution Analysis Core
                  |
+-----+----------+-----------+-----------+
| Git Adapter    | LLM SPI   | Storage   | Reporters |
| PyDriller/Git  | Providers | SQLite/PG | MD/JSON   |
+----------------+-----------+-----------+-----------+
```

#### 建议技术栈

- Python 3.12+
- Typer：CLI
- Rich：终端表格、进度和诊断输出
- FastAPI：可选 REST API
- PyDriller + 原生 Git 命令：仓库挖掘
- Pydantic：领域 DTO、配置和 LLM 结构化输出校验
- SQLAlchemy + Alembic：SQLite/PostgreSQL
- Jinja2：Markdown/HTML 报告
- pytest：测试

#### LLM Provider 契约

```python
class LlmProvider(Protocol):
    def provider_id(self) -> str: ...

    def capabilities(self) -> ModelCapabilities: ...

    def analyze(
        self,
        task: AnalysisTask,
        context: AnalysisContext,
        output_schema: type[BaseModel],
    ) -> BaseModel: ...
```

首批 Provider：

- `OpenAICompatibleProvider`：兼容 OpenAI API 协议，可覆盖 OpenAI、DeepSeek、通义兼容接口及自建网关。
- `AnthropicProvider`：Claude 原生接口。
- `OllamaProvider`：本地模型。
- `MockProvider`：测试和离线规则模式。

#### 优点

- PyDriller 与 Python 数据处理生态成熟，MVP 速度最快。
- Provider 抽象简单，易接入本地模型和新厂商。
- 适合生成 Markdown、JSON、图表和后续模型评测数据集。
- 可作为独立工具运行，不侵入被分析项目。

#### 缺点

- 团队需要维护 Python 工具链。
- 大型仓库需要设计增量缓存和并发策略。
- 依赖 PyDriller 时仍需保留原生 Git 回退能力。

**复杂性**：中
**风险级别**：低至中
**工作量**：中

### 方法二：Java 17 模块化单体 + Spring Boot + JGit SPI

#### 概述

使用 Java 17 和 Spring Boot 构建固定框架，以 JGit 读取仓库，以 Java SPI 或 Spring Bean 接入 LLM Provider。适合由 Java 团队长期维护并部署为内部服务。

#### 建议模块

```text
contribution-domain
contribution-application
adapter-git-jgit
adapter-llm-spi
adapter-storage-jdbc
adapter-report
app-cli
app-server
```

#### 优点

- 与现有 Java/Spring Boot 团队技术栈一致。
- 类型系统、模块边界和长期服务化治理较稳定。
- 容易与企业认证、权限、数据库和内部平台集成。

#### 缺点

- JGit 对部分复杂 Git 行为的处理成本高于原生 Git/PyDriller 组合。
- 文本分析、数据实验和 LLM 评测效率低于 Python。
- MVP 代码量和开发周期更大。

**复杂性**：中至高
**风险级别**：中
**工作量**：大

### 方法三：DevLake 数据平台 + 独立语义分析服务

#### 概述

使用 Apache DevLake 采集 Git、PR、Issue、CI/CD 和发布数据，在其上增加独立的贡献语义分析服务。适合多团队、多仓库和长期绩效数据平台。

#### 优点

- 连接器、增量采集、数据看板和 DORA 指标可以复用。
- 适合跨仓库、跨平台、跨团队统一分析。
- 可以将 Git 贡献与需求、Review、构建、发布和故障数据结合。

#### 缺点

- 部署、数据治理和运维成本最高。
- 对单仓库 MVP 明显过重。
- 仍需自行开发代码语义、能力画像和简历总结模块。

**复杂性**：高
**风险级别**：中至高
**工作量**：大

## 4. 比较矩阵

| 标准 | 方法一：Python 模块化单体 | 方法二：Java 模块化单体 | 方法三：DevLake + 分析服务 |
|---|---|---|---|
| MVP 速度 | 优 | 中 | 差 |
| Git 历史分析生态 | 优 | 中 | 中 |
| LLM/数据实验 | 优 | 中 | 优 |
| Java 团队维护便利性 | 中 | 优 | 中 |
| 单机离线运行 | 优 | 良好 | 差 |
| 多仓库平台化 | 良好 | 良好 | 优 |
| 部署复杂度 | 低 | 中 | 高 |
| 长期扩展能力 | 良好 | 优 | 优 |
| 初始工作量 | 中 | 大 | 大 |
| 当前需求匹配度 | 最高 | 良好 | 未来阶段适用 |

## 5. 推荐方案

### 5.1 推荐：方法一，保留向方法三演进的边界

首版推荐采用“Python 模块化单体 + PyDriller/原生 Git + LLM Provider SPI”。原因如下：

1. 当前第一目标是准确分析单个项目和个人贡献，而不是先建设组织级数据平台。
2. Python 在 Git 挖掘、LLM 接入、数据处理和报告生成方面开发效率最高。
3. 通过领域层和 Adapter 边界，可以保证主体框架稳定，不因更换 LLM 或存储而重写核心。
4. 后续需要多团队平台化时，可以接入 DevLake 数据，而无需替换贡献分析核心。
5. CLI 生命周期可以借鉴 CodeGraph，但 `gca` 命令始终调用固定应用层，不让终端交互侵入领域逻辑。

### 5.2 固定框架边界

以下部分属于固定框架，不允许由 Provider 改变：

- 领域模型和数据库结构。
- Git 事实采集和身份归一化逻辑。
- 主干可达性、发布状态、重复提交和 revert 判定。
- 工作事项聚合流程。
- 证据引用格式、置信度模型和人工审核状态。
- 报告 JSON Schema。
- 安全、脱敏、缓存、审计和重放机制。
- CLI 命令语义、退出码和机器可读输出格式。

LLM 只负责以下可替换任务：

- Commit/ChangeSet 的语义分类。
- 多个变更聚合后的工作事项摘要。
- 技术复杂度证据解释。
- 能力标签候选与理由生成。
- 简历表述候选生成。

LLM 不直接负责：

- 计算提交数量和代码行数。
- 判断提交是否进入主干或发布版本。
- 合并身份。
- 最终绩效评级。
- 生成无法回溯证据的业务效果数字。

## 6. 推荐领域模型

| 实体 | 说明 |
|---|---|
| Repository | 被分析仓库及默认分支配置 |
| Person | 归一化后的人员身份 |
| IdentityAlias | Git name/email 与 Person 的映射及确认状态 |
| CommitRecord | 不可变 Git 提交事实 |
| ChangeSet | 文件、方法、行数、依赖和变更类型 |
| ContributionItem | 聚合后的功能、修复、重构或工程事项 |
| Evidence | 指向 commit、PR、issue、测试、发布或指标的证据 |
| CapabilityAssessment | 能力标签、理由、置信度和反向证据 |
| ContributionAssessment | 交付、质量、复杂度、协作和影响分析 |
| ResumeBullet | 简历候选描述及其证据来源 |
| AnalysisRun | 配置、规则、Prompt、模型和执行状态快照 |
| HumanReview | 人工确认、修改、驳回及备注 |

## 7. 核心分析流水线

```text
1. Repository Discovery
2. Commit Ingestion
3. Identity Resolution
4. Reachability and Release Resolution
5. Noise and Duplicate Filtering
6. ChangeSet Extraction
7. Contribution Item Clustering
8. Rule-based Capability Evidence
9. LLM Semantic Analysis
10. Cross-evidence Aggregation
11. Confidence and Gap Calculation
12. Human Review
13. Report Export
```

### 7.1 规则优先、LLM 补充

确定性规则先产生事实标签，例如：

- 修改 DDL、Entity、Mapper 和事务 Service，形成数据库设计证据。
- 修改 Redis Key、缓存读写和 TTL，形成缓存能力证据。
- 修改锁、幂等键、并发测试，形成并发能力证据。
- 修改 MQ Producer/Consumer，形成消息系统证据。
- 同时修改 Service、Controller、DTO 和测试，形成端到端交付证据。

LLM 读取压缩后的代码上下文和规则证据，负责解释其业务含义和复杂度，不重新计算事实。

## 8. LLM 可替换设计

### 8.1 Provider 配置示例

```yaml
llm:
  provider: openai-compatible
  model: example-model
  base_url: ${LLM_BASE_URL}
  api_key: ${LLM_API_KEY}
  timeout_seconds: 60
  max_retries: 3
  structured_output: true
```

### 8.2 Prompt 与模型治理

- Prompt 存放于版本化目录，不写死在 Provider 中。
- 每类任务使用独立 Prompt 和 JSON Schema。
- 保存 `provider/model/prompt_version/schema_version`。
- 支持相同 AnalysisRun 切换模型重放和结果对比。
- 对不同模型运行一致性、事实引用率和幻觉率评测。
- Provider 输出必须经过 Pydantic 校验；失败时重试或降级为规则结果。

### 8.3 上下文控制

- 不向 LLM 发送整个仓库。
- 先通过 Git、AST、路径和依赖关系筛选相关上下文。
- 默认排除密钥、证书、二进制、依赖包、生成文件和超大文件。
- 支持只发送 Diff 摘要、符号签名和脱敏片段。

## 9. 绩效与简历输出边界

### 9.1 绩效报告

系统默认输出多维证据，不输出单一“员工总分”。建议维度：

| 维度 | 主要证据 |
|---|---|
| 交付 | 合入主干、进入发布版本、需求完成状态 |
| 复杂度 | 跨模块、数据一致性、并发、缓存、MQ、外部集成 |
| 质量 | 测试、缺陷、revert、Review、静态检查和发布后问题 |
| 所有权 | 持续维护领域、事故处理、长期演进 |
| 协作 | PR Review、共同提交、文档、方案和跨团队工作 |
| 影响 | 性能、稳定性、成本或业务指标，需要外部证据支持 |

### 9.2 简历总结

简历候选内容采用以下结构：

```text
在什么项目和场景下，负责或参与什么工作，采用什么关键技术，
解决了什么问题，产生了什么可验证结果。
```

系统必须区分：

- “实现/主导”：需要连续提交、关键设计、核心代码和交付证据。
- “参与/协助”：存在贡献证据，但不足以证明负责人身份。
- “优化并提升 X%”：必须有基准测试、监控或业务指标证据。
- 无效果数据时，只描述规模、复杂度和技术结果，不虚构百分比。

## 10. CLI 产品设计

### 10.1 命令定位

项目安装后提供 `gca` 可执行程序。典型使用流程如下：

```bash
# 1. 在当前 Git 仓库初始化并建立首次索引
gca init .

# 2. 查看索引、身份和配置状态
gca status

# 3. 查看待确认的 Git 身份别名
gca identities list --unresolved

# 4. 分析指定人员和时间范围
gca analyze \
  --person "gongzhen" \
  --since 2026-01-01 \
  --until 2026-06-30 \
  --target-branch master

# 5. 导出最近一次报告
gca report --run latest --format markdown

# 6. 拉取最新提交后执行增量同步
gca sync
```

### 10.2 首批命令

| 命令 | 作用 | MVP |
|---|---|---|
| `gca init [path]` | 验证 Git 仓库、创建 `.gca/`、写入配置并建立首次索引 | 是 |
| `gca index [path]` | 丢弃旧索引并执行全量重建 | 是 |
| `gca sync [path]` | 只同步上次索引后的新增或变化提交 | 是 |
| `gca status [path]` | 显示仓库、提交、身份、索引和最近分析状态 | 是 |
| `gca identities list` | 列出 Git 身份、别名候选和确认状态 | 是 |
| `gca identities map` | 将 name/email 映射到规范 Person | 是 |
| `gca analyze` | 按人员、时间、分支和发布范围运行贡献分析 | 是 |
| `gca runs list/show` | 查看历史 AnalysisRun、配置和模型版本 | 是 |
| `gca report` | 导出 Markdown、JSON 或 HTML 报告 | 是 |
| `gca providers list/test` | 查看和验证 LLM Provider | 是 |
| `gca config show/set` | 查看或修改项目级配置 | 是 |
| `gca doctor` | 检查 Git、数据库、配置、网络和模型可用性 | 是 |
| `gca clean` | 清理缓存或指定运行产物，不删除项目配置 | 是 |
| `gca uninit [path]` | 删除 `.gca/` 本地工作区 | 是 |
| `gca serve` | 启动本地 REST API 和可选 Web UI | 后续 |
| `gca serve --mcp` | 暴露贡献查询 MCP，供 Codex 等 Agent 使用 | 后续 |
| `gca install-agent` | 将 MCP 服务配置到 Codex、Claude Code 等客户端 | 后续 |

### 10.3 `analyze` 参数设计

```text
gca analyze [path]
  --person <name-or-email>        必填，可重复
  --since <date>                  可选
  --until <date>                  可选
  --target-branch <branch>        默认读取项目配置
  --release <tag-or-range>        可选，限定发布版本
  --scope <path>                  可选，限定模块或目录
  --provider <provider-id>        可选，覆盖默认 LLM Provider
  --model <model-id>              可选，覆盖默认模型
  --no-llm                        只运行确定性规则
  --refresh                       分析前执行增量同步
  --format text|json              CLI 输出格式
  --verbose                       输出详细阶段和耗时
```

`gca analyze` 返回非零退出码的情况必须稳定定义：

| 退出码 | 含义 |
|---|---|
| `0` | 成功，报告已生成 |
| `2` | 参数或配置错误 |
| `3` | 不是 Git 仓库或仓库不可读 |
| `4` | 索引损坏或被锁定 |
| `5` | 身份存在歧义，需要人工确认 |
| `6` | LLM Provider 失败且未允许降级 |
| `7` | 报告生成失败 |

### 10.4 仓库本地工作区

`gca init` 默认在被分析仓库创建 `.gca/`：

```text
.gca/
├── config.yml              # 当前仓库分析配置
├── meta.json               # 工具版本、索引版本和仓库指纹
├── index.sqlite            # Git 事实和增量索引
├── identities.yml          # 本地身份映射及确认记录
├── cache/                  # Diff、AST 和 LLM 缓存
├── runs/                   # AnalysisRun 结构化结果
├── reports/                # Markdown/JSON/HTML 报告
└── locks/                  # 防止并发写入的锁文件
```

默认通过 `.git/info/exclude` 忽略 `.gca/`，避免自动修改项目的受版本控制文件。需要团队共享配置时，通过显式命令导出：

```bash
gca config export --output gca.yml
gca config import gca.yml
```

仓库根目录可选提供 `.gcaignore`，用于排除密钥、证书、依赖包、生成文件和不参与评估的路径。

### 10.5 CLI 状态输出

`gca status` 至少显示：

```text
Repository: D:/CodeWorkspace/example
Branch: master
Indexed commit: abc1234
Indexed commits: 12,345
Identities: N total, M unresolved
Analysis runs: 6
Last sync: 2026-01-01 12:00:00
Index status: up to date
```

`gca status --json` 必须返回版本化 JSON Schema，供脚本、CI 和 Agent 调用。

### 10.6 安装与跨平台要求

- Python 包通过 `pyproject.toml` 注册 `gca` console script。
- 开发者安装优先支持 `pipx install git-contribution-analyzer`。
- 发布阶段生成 Windows `gca.exe`、Linux/macOS 单文件可执行程序或等价安装包。
- Windows 必须提供 `.exe` 或 `.cmd` 可调用入口，不能只依赖可能受执行策略限制的 `.ps1` shim。
- CI 必须在 Windows、Linux 和 macOS 验证 `gca --help`、`gca init`、`gca status --json`。

### 10.7 增量与并发模型

- `gca init/index` 执行全量索引。
- `gca sync` 基于已记录的 Git 对象和 refs 变化做增量更新。
- 仓库写操作使用锁文件，检测到陈旧锁时由 `gca doctor` 提示，后续可提供 `gca unlock`。
- CLI 中断后保留已提交事务，不留下半完成的 AnalysisRun。
- LLM 结果按证据指纹、Prompt 版本、Provider 和模型版本缓存。

## 11. 建议目录结构

```text
git-contribution-analyzer/
├── pyproject.toml
├── README.md
├── src/
│   └── git_contribution_analyzer/
│       ├── domain/
│       ├── application/
│       ├── adapters/
│       │   ├── git/
│       │   ├── llm/
│       │   ├── storage/
│       │   └── reports/
│       ├── prompts/
│       ├── rules/
│       ├── cli/
│       │   ├── app.py
│       │   ├── commands/
│       │   ├── output.py
│       │   └── exit_codes.py
│       └── api/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── fixtures/
│   └── golden/
├── config/
├── schemas/
├── packaging/
│   ├── windows/
│   ├── linux/
│   └── macos/
└── doc/
    ├── proposals/
    ├── plans/
    ├── architecture/
    └── reports/
```

## 12. MVP 范围

### 第一阶段：无 LLM 的确定性分析

- 可安装的 `gca` CLI 及跨平台 `--help`。
- `gca init/index/sync/status/doctor/uninit` 仓库生命周期。
- `.gca/` 本地工作区、SQLite 索引、锁和增量元数据。
- 本地仓库扫描。
- 用户身份归一化。
- 主干可达性和发布标签判断。
- Merge、revert、重复提交和噪声过滤。
- 模块、语言、文件和提交类型统计。
- Markdown/JSON 基础报告。
- 稳定退出码和 `--json` 机器可读输出。

### 第二阶段：可替换 LLM 分析

- Provider SPI。
- OpenAI-compatible、Ollama 和 Mock Provider。
- `gca providers list/test` 和 `gca analyze --no-llm` 降级路径。
- Commit 语义分类。
- Contribution Item 聚合与摘要。
- 能力证据解释和简历候选生成。
- Prompt/Schema 版本化及重放。

### 第三阶段：绩效证据增强

- GitHub/GitLab PR、Review、Issue 接入。
- CI、测试、发布和 revert 关联。
- 人工审核流程。
- HTML 报告和多周期对比。

### 第四阶段：平台化

- 多仓库和团队管理。
- PostgreSQL。
- DevLake/Jira/TAPD 接入。
- 权限、审计、定时增量分析和看板。

## 13. 主要风险与缓解措施

| 风险 | 缓解措施 |
|---|---|
| LLM 幻觉或过度归因 | 强制证据引用、结构化输出、置信度和人工确认 |
| Git 身份误合并 | 映射来源和确认状态可审计，不自动合并模糊身份 |
| 提交数量被当作绩效 | 默认不生成单一总分，报告突出交付和质量证据 |
| 废弃分支造成虚假贡献 | 默认只统计目标分支可达或进入发布标签的工作 |
| Squash/Cherry-pick 重复 | 使用 patch-id、PR 元数据和内容指纹去重 |
| 敏感代码外传 | 本地模式、路径排除、脱敏、本地 Provider |
| 大仓库扫描缓慢 | 增量索引、对象缓存、按时间/用户/路径裁剪 |
| 模型更换导致结果漂移 | 保存模型和 Prompt 版本，支持黄金数据集回归 |
| Windows CLI 被执行策略阻断 | 发布 `.exe`/`.cmd` 入口并在 Windows CI 做真实调用验证 |
| CLI 与服务端逻辑分叉 | CLI、REST 和 MCP 只调用同一 Application Use Cases |

## 14. 验收标准

- 在 Windows、Linux 和 macOS 上可以运行 `gca --help`。
- 在任意 Git 仓库执行 `gca init` 后可以通过 `gca status --json` 验证索引。
- 新增提交后执行 `gca sync` 只处理增量变更。
- `gca analyze --no-llm` 可以独立生成确定性报告。
- 同一人的多个 Git 身份能够被正确归一化并说明依据。
- 能区分未合入、已合入和已发布的贡献。
- 对重复提交、Merge 和 revert 不重复计入实际交付。
- 每个 Contribution Item 至少包含一个可访问的证据引用。
- 更换 LLM Provider 不修改领域层和应用层代码。
- LLM 不可用时仍能生成确定性基础报告。
- 对同一黄金仓库重复运行，确定性事实结果完全一致。
- 简历描述中的责任和效果措辞符合证据强度。

## 15. 下一步

1. 确认采用方法一作为首版技术路线。
2. 创建详细实施计划和领域模型设计。
3. 固化 `gca init/index/sync/status/analyze/report` 命令契约、退出码和 JSON Schema。
4. 使用生成式公开 fixture 制作黄金测试数据集。
5. 按“无 LLM 核心 -> Provider SPI -> 语义分析 -> 人工审核”顺序实施。
