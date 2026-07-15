# GCA 中文文档

[返回中文 README](../../README.zh-CN.md) | [English documentation](../../README.md)

本目录提供 GCA 0.2.0 核心用户文档的简体中文版本。英文文档仍是原始技术契约；中文文档与其
保持相同的 CLI、配置键、状态枚举、Schema 和安全边界。

## 快速入口

- [architecture.md](architecture.md)：分层架构、分析流水线、扩展点和故障边界。
- [data-model.md](data-model.md)：`.gca` 工作区、SQLite 表和迁移。
- [cli-reference.md](cli-reference.md)：命令、参数、Provider 和退出码。
- [installation.md](installation.md)：开发安装、wheel、pipx、standalone、升级和卸载。
- [methodology.md](methodology.md)：完成状态、工作规模、难度和简历 claim 规则。
- [privacy.md](privacy.md)：本地数据、LLM 上下文、报告分享和保留策略。
- [provider-guide.md](provider-guide.md)：HTTP、Ollama、Codex CLI、Claude CLI 配置。
- [golden-dataset.md](golden-dataset.md)：确定性规则和双轨 E2E 的黄金仓库契约。
- [release-0.2.0.md](release-0.2.0.md)：0.2.0 新能力、兼容性和发布门禁。
- [release-0.1.0.md](release-0.1.0.md)：0.1.0 能力范围、兼容性和已知限制。

## 推荐阅读顺序

1. 初次使用：`installation.md` -> `cli-reference.md`。
2. 团队评估：`methodology.md` -> `privacy.md`。
3. 接入 LLM：`provider-guide.md` -> `architecture.md`。
4. 二次开发：`architecture.md` -> `data-model.md` -> `golden-dataset.md`。

中文文档如与程序实际输出不一致，应以当前 CLI `--help`、JSON Schema、测试和英文源文档为准，
并在同一次变更中同步修正文档。
