# 阶段 4 实施报告：可替换 LLM Provider 与语义增强

## 结论

实施计划阶段 4 已完成。`gca` 在保持确定性 Git 事实和规则分析不变的前提下，新增了可替换 LLM Provider、证据约束语义增强、调用审计、响应缓存、失败降级和 Provider CLI。

LLM 不计算 commits、交付状态、Contribution Item、能力规则或绩效等级。每条语义结论必须引用已存在的 Evidence ID；无证据百分比、未知 Evidence/Item/capability 和非法 Schema 会被拒绝。

## Provider SPI

Application 层只通过 `LlmProvider` 协议使用以下统一对象：

- `LlmTask`：任务、Prompt/Schema 版本、结构化 Schema 和 Evidence 白名单。
- `ProviderCapabilities`：结构化输出、本地执行和健康检查能力。
- `LlmCompletion`：Provider、模型、结构化内容、attempts 和字符计数。

首批 Adapter：

| Provider ID | Adapter | 执行位置 |
|---|---|---|
| `mock` | 固定测试/黄金输出 | 本地 |
| `openai-compatible` | Chat Completions 兼容 HTTP API | 远程 |
| `anthropic` | Messages HTTP API | 远程 |
| `ollama` | 本地 Chat HTTP API | 本地 |
| `codex-cli` | 本机 Codex 非交互命令 | 本地 CLI/已配置网关 |
| `claude-cli` | 本机 Claude Code 非交互命令 | 本地 CLI/已配置网关 |

公共 HTTP 层实现 timeout、401/403、429、5xx 映射，可重试错误按配置重试。非法 JSON 只执行一次带明确修复指令的重试，第二次非法响应直接拒绝。

## 语义安全

四类 Prompt 版本均为 `semantic-v1`：

- overall summary
- Contribution Item summary
- capability explanation
- resume bullet

发送上下文只包含裁剪后的统计、路径、Contribution Item、capability 和 Evidence 摘要。Person email、API Key、Authorization 和源码正文不进入 Prompt。

正式输出使用 Pydantic 模型与 `schemas/llm/semantic-v1.json` 双重版本化。额外执行以下业务校验：

- 每个 claim 至少一个 Evidence ID。
- Evidence ID 必须位于本次任务白名单。
- Contribution Item 和 capability 引用必须存在。
- 没有确定性指标证据时拒绝百分比表述。

## 配置与 CLI

新增命令：

```powershell
gca providers list <repository> --json
gca providers test <repository> --json
```

配置支持 Provider ID、模型、base URL、API Key 环境变量名、timeout、max retries 和规则降级。优先级为：

```text
GCA_LLM_* environment > .gca/config.yml > defaults
```

仓库配置只保存 `apiKeyEnv` 的变量名，不保存变量值。`--no-llm` 会完全绕过 Provider、缓存和 invocation 写入。

## 审计与缓存

Alembic migration：`0004_llm_audit`

- `llm_invocations`：run、request hash、Provider/model、Prompt/Schema 版本、attempts、latency、status、error 和 cache hit。
- `llm_cache`：request hash、Provider/model、Prompt/Schema 版本和结构化响应。

request hash 由 Provider/model、Prompt/Schema 版本、系统/用户 Prompt 和输出 Schema 的规范化 JSON 计算。数据库不保存 Prompt、API Key、Authorization 或源码正文。

## 运行状态

已验证：

```text
RUNNING -> COMPLETED   Provider 成功或完全 no-LLM
RUNNING -> PARTIAL     Provider 失败且允许规则降级
RUNNING -> FAILED      Provider 失败且禁止降级
```

`PARTIAL` 报告保留全部确定性事实、`semantic: null` 和可见 warning。禁止降级时 CLI 返回退出码 `6`，不保存非法语义报告。

## TDD 记录

### RED

- 429 被最初测试错误归入不可重试，依据现有错误模型修正为可重试限流。
- 非法 JSON 虽会重试，但第二次请求没有修复指令。
- CLI Provider 工作区构造未使用既有 `for_repository()` 工厂。
- mypy 发现审计 Protocol 参数过宽和 CLI `object` 推断。
- IMPROVE 中一次机械替换误将异常 attempts 放入 cache-hit 分支，被定向测试立即阻止。

### GREEN

- 完成六个 Provider 和统一合同。
- 完成语义任务、Pydantic Schema、Evidence 校验和 Prompt 资源。
- 完成 `0004_llm_audit`、request hash、缓存和审计装饰器。
- 完成 Registry、配置、`providers list/test` 和 analyze 接线。
- 完成成功、PARTIAL、FAILED、no-LLM 和 cache-hit 流程。

### IMPROVE

- 失败 Provider 将真实 retry attempts 写入 invocation。
- 报告始终显式包含 `semantic` 和 `warnings`。
- Markdown 在存在语义输出时渲染 Semantic Summary 和 Resume Candidates。
- 增加独立 Provider Guide、落盘 LLM Schema 和手动真实 Provider smoke workflow。

## 质量门禁

| 检查 | 结果 |
|---|---|
| pytest | 68 passed |
| 全项目覆盖率 | 88.74%，达到 80% 门槛 |
| Ruff | 通过 |
| mypy strict | 74 个源码文件通过 |
| JSON Schema | 全部可解析，语义样例通过落盘 Schema |
| workflow YAML | PyYAML 解析通过 |
| wheel/sdist | 构建成功 |
| wheel 隔离安装 | 成功 |
| wheel CLI | `gca --help` 成功，包含 `providers` |
| wheel Prompt 资源 | `importlib.resources` 读取成功 |

构建产物：

- `dist/git_contribution_analyzer-0.1.0.dev0-py3-none-any.whl`
- `dist/git_contribution_analyzer-0.1.0.dev0.tar.gz`

## 生成式 Mock 黄金验证

验证仓库在临时目录中生成，使用虚构身份和 `example.com` 保留域名，不记录任何外部仓库、
真实人员或本机路径。

| 指标 | 结果 |
|---|---|
| 状态 | `COMPLETED` |
| Provider/model | `mock` / `deterministic` |
| 输入 | 生成式 fixture |
| Contribution Items | 与 fixture 预期一致 |
| Evidence | 引用完整 |
| semantic overall claims | 1 |
| semantic Evidence | `EV-001` |
| warnings | 0 |
| migration | `0004_llm_audit` |
| invocation | 首次执行并写入审计 |

相同参数第二次运行命中缓存，证明 CLI 的 request hash、审计和缓存链路可重放。测试结束后临时
仓库自动删除，不保存人员级报告。

## Provider 验证边界

实现采用 OpenAI-compatible 边界，并将 endpoint、model 和 key 环境变量保持可配置，未把厂商
行为写入 Domain/Application。真实 HTTP Provider smoke 只允许在手动工作流中使用 GitHub Secret；
普通 CI 不访问外部 LLM，也不会消耗 API 配额。

### 命令 Provider

Codex/Claude 命令 Provider 使用生成式 fixture 完成最小 smoke，报告只保留行为结论，不记录本机
账号、版本、绝对路径、会话配置、运行 ID 或人员级分析结果：

| Provider | 结果 |
|---|---|
| `codex-cli` | 结构化输出通过 Schema 和 Evidence 校验 |
| `claude-cli` | 结构化输出通过 Schema 和 Evidence 校验 |

Windows 命令包装器可能继承管道句柄，因此实现优先解析同一安装包内的原生可执行文件。显式
`executable` 配置保持最高优先级，支持用户自定义包装器或非官方 Provider 配置。

两个命令 Provider 都在独立临时目录运行，不向代理开放目标仓库。Prompt 通过 stdin 传入；Codex 使用 ephemeral、read-only、禁用 MCP 和输出 Schema；Claude 禁用 tools、MCP、Chrome 和会话持久化。调用仍进入现有 request hash、cache、invocation audit、Pydantic 和 Evidence 校验链路。

验证过程中还发现并修复空分析边界：当筛选结果没有 Evidence 时，GCA 现在跳过 LLM，不写 invocation，不浪费 CLI/API 配额，报告保持 `COMPLETED` 并给出明确说明。

集成验证还发现 `AnalysisRun.completedAt` 原先在 LLM 调用前记录，无法覆盖命令 Provider 耗时。
完成时间现已移动到语义增强或降级处理之后，并由集成测试验证。

## 已知限制

- 当前是短生命周期同步 HTTP 调用，不支持流式输出和并行批任务。
- OpenAI-compatible 服务对 `json_schema` 支持不一致；不兼容服务会进入明确失败/降级路径。
- Anthropic 和 Ollama 的结构化输出最终仍由 GCA 本地 Pydantic/Evidence 校验兜底。
- cache 保存结构化 Provider 响应，不保证不同模型版本的文本逐字相同；model、Prompt 和 Schema 变化会产生新 hash。
- LLM 只能生成候选总结，绩效、晋升和简历内容仍需要人工复核。

## 下一阶段入口

阶段 5 将完成跨平台可执行程序、完整 CLI/Privacy/Methodology 文档、性能和内存基准、安全扫描以及 `0.1.0` 发布验收。
