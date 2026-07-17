# GCA 0.4.1

[中文文档索引](https://github.com/PANZERLEADER/git-contribution-analyzer/blob/v0.4.1/doc/zh-CN/README.md) | [English](https://github.com/PANZERLEADER/git-contribution-analyzer/blob/v0.4.1/doc/releases/0.4.1.md)

GCA 0.4.1 修复引入可选桌面 GUI 后的 CLI standalone 打包问题。

## 修复内容

- 从 `gca` CLI standalone 制品中排除 Qt adapter、QML 资源、PySide6 和 shiboken6。
- 直接检查最终 CLI PyInstaller 归档；如果包含 GUI runtime 条目，发布构建立即失败。
- 保留共享包导出所需的框架无关 GUI 请求 DTO。
- macOS 应用 bundle 版本改为直接读取 `pyproject.toml`。

## 兼容性

本补丁不改变 CLI 命令、报告 Schema、SQLite Schema 或 GUI 工作流。core wheel 仍不依赖
PySide6。使用 `0.4.0` CLI standalone 制品的用户应升级到 `0.4.1`；GUI 制品功能保持一致。
