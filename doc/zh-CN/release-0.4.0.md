# GCA 0.4.0

GCA 0.4.0 新增基于 PySide6 和 QML 的可选跨平台桌面应用。

## 主要变更

- 新增独立 `gca-gui` 入口，同时保留 `gca` CLI。
- 新增仓库生命周期、工作评估、趋势、人员、工作项/Evidence、历史 run 对比、报告导出、
  简历和 Provider 页面。
- Git、SQLite 和 Provider 任务在 Qt UI 线程之外执行，并按仓库 FIFO 调度。
- 新增协作式进度和取消契约，取消后的 assessment run 会进入明确终态。
- CLI 和 GUI 共用系统时区时间边界解析，并统一检查 `since <= until`。
- 新增 `[gui]` 可选安装和 Windows/Linux/macOS PyInstaller GUI 制品。

## 兼容性

普通 core wheel 不依赖 PySide6。现有 CLI 命令、JSON 报告契约和仓库本地 SQLite Schema 保持
兼容。GUI 只保存非敏感本地偏好；Provider 凭据仍来自环境变量或已认证的命令行会话。
