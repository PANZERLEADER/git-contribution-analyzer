# LLM Provider 指南

[中文文档索引](README.md) | [English](../guides/provider-guide.md)

## 能力边界

GCA 在不使用 LLM 的情况下计算 Git 事实、交付状态、Contribution Item、Evidence 和规则能力标签。
Provider 只能增加语义总结、解释和简历候选措辞。每个生成的 claim 都必须引用已有 Evidence ID。

LLM 默认关闭。`gca analyze --no-llm` 会绕过 Provider 构造、网络调用、缓存读取和调用审计写入。

## 配置

仓库配置位于 `.gca/config.yml`：

```yaml
llm:
  enabled: true
  provider: mock
  model: deterministic
  baseUrl: null
  apiKeyEnv: GCA_LLM_API_KEY
  executable: null
  timeoutSeconds: 30.0
  commandTimeoutSeconds: 300.0
  maxRetries: 2
  allowFallbackToRules: true
```

支持的 Provider：

| ID | 默认地址 | 需要密钥 | 执行方式 |
|---|---|---|---|
| `mock` | 本地 | 否 | 本地确定性 fixture |
| `openai-compatible` | `https://api.openai.com/v1` | 是 | 远程 HTTP |
| `anthropic` | `https://api.anthropic.com` | 是 | 远程 HTTP |
| `ollama` | `http://127.0.0.1:11434` | 否 | 本地 HTTP |
| `codex-cli` | 本地命令 | 否 | 已认证 CLI |
| `claude-cli` | 本地命令 | 否 | 已认证 CLI |

以下环境变量覆盖仓库配置：

- `GCA_LLM_PROVIDER`
- `GCA_LLM_MODEL`
- `GCA_LLM_BASE_URL`
- `GCA_LLM_EXECUTABLE`
- `apiKeyEnv` 指定的环境变量

密钥值永远不会写入仓库配置、SQLite、报告或日志。

## 常用命令

```powershell
gca providers list D:\path\to\repository --json
gca providers test D:\path\to\repository --json
gca analyze D:\path\to\repository --person alice@example.com --json
gca analyze D:\path\to\repository --person alice@example.com --no-llm --json
```

`providers test` 只检查当前 Provider 健康状态，不执行贡献分析。真实远程 Provider 检查不进入普通
CI，可通过手动 `provider-smoke.yml` workflow 和仓库 secret 执行。

## 失败与审计语义

Timeout、HTTP 429 和 HTTP 5xx 最多按 `maxRetries` 重试。认证错误不重试。无效 JSON 只允许一次
修复请求，第二次无效响应会被拒绝。语义结论进入报告前，必须通过 Pydantic 和 Evidence 引用校验。

当 `allowFallbackToRules` 为 `true` 时，Provider 失败生成包含完整确定性事实和警告的 `PARTIAL`
报告。为 `false` 时，AnalysisRun 标记为 `FAILED`，CLI 返回退出码 `6`，报告中不保存语义结论。

迁移 `0004_llm_audit` 增加：

- `llm_invocations`：request hash、run、Provider/model、Prompt/Schema 版本、尝试次数、延迟、状态、
  错误码/消息和 cache hit。
- `llm_cache`：request hash、Provider/model、Prompt/Schema 版本和结构化响应。

两张表都不保存 prompt、源码正文、API key 或 Authorization header。

## Codex CLI 与 Claude CLI

当目标机器已有认证的代码 CLI，或 CLI 已配置网关、代理、云平台、非官方模型 endpoint 时，可以
使用 command Provider：

```yaml
llm:
  enabled: true
  provider: codex-cli
  model: configured-default
  executable: null
  commandTimeoutSeconds: 300
```

`configured-default` 不传递 CLI model 参数，保留 CLI 当前模型/Provider 选择。设置明确 model ID 时，
GCA 会传递 `--model`。`GCA_LLM_EXECUTABLE` 优先级最高，可以指向原生可执行文件或批准的 wrapper。

GCA 不会在被分析仓库中运行这些命令：

- Prompt 通过 stdin 传递，不放入命令参数。
- 进程工作目录是全新的临时目录。
- Codex 使用 `exec --ephemeral`、只读 sandbox、输出 Schema，并关闭 MCP server。
- Windows 自动发现优先使用 npm package 中的原生 `codex.exe`，避免 `codex.cmd` 继承管道导致阻塞。
- Claude 使用 `--print`、JSON Schema、`--tools ""`、空 MCP 配置、无 Chrome、无会话持久化。
- stderr 不会复制到报告或 invocation error message。

Command Provider 不自动重试失败的模型调用，避免重复消耗订阅或网关额度。GCA 的缓存、审计、
Evidence 校验和 fallback 规则仍然有效。
