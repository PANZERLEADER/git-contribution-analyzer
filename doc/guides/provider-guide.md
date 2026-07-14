# LLM Provider Guide

[简体中文](../zh-CN/provider-guide.md)

## Boundary

GCA computes Git facts, delivery status, Contribution Items, Evidence, and rule-based capability
labels without an LLM. A Provider may only add semantic summaries, explanations, and resume
candidates. Every generated claim must reference an existing Evidence ID.

LLM use is disabled by default. `gca analyze --no-llm` always bypasses Provider construction,
network calls, cache reads, and invocation writes.

## Configuration

Repository settings live in `.gca/config.yml`:

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

Supported IDs:

| ID | Default base URL | Key required | Execution |
|---|---|---|---|
| `mock` | local | no | local deterministic fixture |
| `openai-compatible` | `https://api.openai.com/v1` | yes | remote |
| `anthropic` | `https://api.anthropic.com` | yes | remote |
| `ollama` | `http://127.0.0.1:11434` | no | local |
| `codex-cli` | local command | no | local authenticated CLI |
| `claude-cli` | local command | no | local authenticated CLI |

Environment variables override repository settings:

- `GCA_LLM_PROVIDER`
- `GCA_LLM_MODEL`
- `GCA_LLM_BASE_URL`
- `GCA_LLM_EXECUTABLE`
- the variable named by `apiKeyEnv`

The key value is never written to repository configuration, SQLite, reports, or logs.

## Commands

```powershell
gca providers list D:\path\to\repository --json
gca providers test D:\path\to\repository --json
gca analyze D:\path\to\repository --person alice@example.com --json
gca analyze D:\path\to\repository --person alice@example.com --no-llm --json
```

`providers test` checks the configured Provider's health endpoint. It does not run contribution
analysis. Real Provider checks are excluded from normal CI and can be run through the manual
`provider-smoke.yml` workflow with a repository secret.

## Failure And Audit Semantics

Timeouts, HTTP 429, and HTTP 5xx responses are retried up to `maxRetries`. Authentication errors
are not retried. Invalid JSON receives one repair request; a second invalid response is rejected.
Pydantic validation and Evidence-reference validation run before semantic conclusions enter the
report.

When `allowFallbackToRules` is true, a Provider failure produces a `PARTIAL` report containing all
deterministic facts and a warning. When false, the AnalysisRun is `FAILED`, CLI exit code is `6`,
and no semantic conclusion is stored in the report.

SQLite migration `0004_llm_audit` adds:

- `llm_invocations`: request hash, run, Provider/model, Prompt/Schema versions, attempts, latency,
  status, error code/message, and cache-hit state.
- `llm_cache`: request hash, Provider/model, Prompt/Schema versions, and structured response.

Neither table stores prompts, source bodies, API keys, or Authorization headers.

## Codex And Claude CLI

Use command Providers when the machine already has an authenticated coding CLI or when that CLI
is configured for a gateway, proxy, cloud platform, or another non-official model endpoint.

```yaml
llm:
  enabled: true
  provider: codex-cli
  model: configured-default
  executable: null
  commandTimeoutSeconds: 300
```

`configured-default` omits the CLI model flag and preserves the CLI's active model/provider
selection. Set a model ID to pass `--model` explicitly. `GCA_LLM_EXECUTABLE` has the highest
priority and can point to a native executable or an approved wrapper.

GCA does not run either command in the analyzed repository:

- Prompt context is sent through stdin, not command arguments.
- A fresh temporary directory is used as the process working directory.
- Codex uses `exec --ephemeral`, read-only sandboxing, output Schema, and disables MCP servers.
- On Windows, automatic discovery prefers the npm package's native `codex.exe` over `codex.cmd`
  to prevent inherited pipe handles from blocking process completion.
- Claude uses `--print`, JSON Schema, `--tools ""`, strict empty MCP configuration, no Chrome,
  and no session persistence.
- stderr is never copied into the report or invocation error message.

Command Providers intentionally do not retry failed model invocations because retries can consume
the user's subscription or gateway quota twice. Normal GCA cache, audit, Evidence validation, and
fallback behavior still apply.
