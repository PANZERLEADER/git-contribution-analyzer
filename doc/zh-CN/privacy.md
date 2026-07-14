# 隐私与数据边界

[中文文档索引](README.md) | [English](../guides/privacy.md)

## 本地数据

默认情况下，索引、身份规范化、确定性贡献分析、工作评估和 no-LLM 简历模板都在本地运行。
`.gca/index.sqlite` 包含仓库路径、commit 元数据、作者身份、派生 Evidence 和持久化报告，应作为
项目内部数据保护。

GCA 不会把 API key 写入仓库配置或日志。Provider secret 必须来自环境变量，或来自本机 Provider
CLI 已有的认证会话。

## LLM 上下文

Provider 请求使用经过脱敏和白名单限制的上下文，可以包含：

- Contribution Item ID 和 Evidence ID；
- commit subject，以及保守的模块/路径摘要；
- 确定性能力标签或 claim strength 上限；
- 用户选择的目标岗位、语言和风格。

Provider 请求不得包含：

- Person 邮箱；
- 源码正文；
- 凭据和 Authorization header；
- 其他人员的简历内容；
- 团队排名；
- 不受限制的仓库访问能力。

`codex-cli` 和 `claude-cli` 通过标准输入接收 prompt，Adapter 会关闭仓库工具访问。命令仍以当前
操作系统用户身份执行，因此在处理私有仓库前，应审核本机 CLI 配置、网关和日志策略。

## Provider 选择

- `mock`：本地确定性测试，不访问网络。
- `ollama`：默认访问本地模型端点，除非用户改为其他地址。
- `codex-cli` / `claude-cli`：复用本机已认证命令及其 Provider 配置。
- `openai-compatible` / `anthropic`：将脱敏 prompt 发送到配置的 HTTP endpoint。

当仓库策略禁止任何模型处理时，应使用 `--no-llm`。

## 报告分享

个人分析 JSON 可能包含规范邮箱；简历 Markdown 会主动省略邮箱和其他身份。工作评估 CSV 默认
不包含邮箱，只有 `--include-email` 会显式加入。团队范围中被排除的身份按 Person ID 和原因记录。
对外分享前，应审核并清理内部路径、身份和 commit subject。

Verified outcome 文件由人工维护，可能包含敏感业务结果。未经批准不得放入公共仓库。

## 保留与删除

`gca uninit <repo> --yes` 删除本地工作区。Provider 调用审计只保存 hash、版本、状态和已验证
响应，不保存 API key。组织的数据保留、访问控制和报告授权仍由仓库所有者负责。
