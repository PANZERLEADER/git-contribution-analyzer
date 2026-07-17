# GCA 0.1.0 发布说明

[中文文档索引](https://github.com/PANZERLEADER/git-contribution-analyzer/blob/v0.2.0/doc/zh-CN/README.md) | [English](https://github.com/PANZERLEADER/git-contribution-analyzer/blob/v0.1.0/doc/releases/0.1.0.md)

## 能力范围

首个正式版本提供本地 CLI，用于 Git 索引、身份确认、确定性贡献分析、已完成工作规模/难度评估，
以及有 Evidence 支持的简历草稿。LLM 只用于可选措辞增强，并且与具体 Provider 解耦。

## 安装方式

- 适用于 Python 3.12/3.13 的 wheel 和 source distribution。
- 通过 wheel 使用 `pipx` 安装。
- Release CI 构建的 Windows、Linux、macOS standalone 文件。

安装和回滚命令见 [installation.md](installation.md)。

## 兼容性

- 已有 `ANALYSIS` run 保持可读。
- 迁移 `0005_run_types` 将历史行升级为 `ANALYSIS`，并支持降级到 `0004_llm_audit`。
- 旧字段 `semantic.resumeBullets` 在 1.x 期间继续可读，但已弃用。
- 工作量和难度规则带版本；历史 run JSON 永不重写。

## 安全与隐私

- 完整支持不使用 LLM 的确定性路径。
- Provider 凭据只从环境或本机认证会话读取。
- Provider prompt 经过脱敏并受 Evidence 白名单约束。
- CI 扫描 Git 历史凭据，并在隔离环境中验证 wheel。

## 已知限制

- 结构复杂度和调用影响 Adapter 属于 MVP 后续；不可用时报告会输出 gap 并降低置信度。
- Git 证据不能证明工时、唯一所有权或业务成果。
- 缺少稳定 patch 证据的 squash merge 只能保守关联。
- Tagged workflow 已构建并冒烟验证所有发布制品。

## 发布验收

- [x] 发布提交的三平台 CI 和 standalone job 全部通过。
- [x] Wheel、sdist 和三平台 standalone 已保留。
- [x] Git 历史凭据扫描通过。
- [x] 正式版本为 `0.1.0`。
- [x] Tag 已发布 release notes 和 SHA-256 checksums。
