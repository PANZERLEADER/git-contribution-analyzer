# 提案：GCA 跨平台 GUI

## 1. 提案结论

推荐采用 `PySide6 + QML`，将 GUI 实现为与现有 Typer CLI 并列的入口适配器。GUI 直接调用
`application` use case，不解析人类可读 CLI 输出，也不直接访问 SQLite 或 Git。耗时任务通过
后台任务控制器执行，并向界面发送版本化进度事件。

该方案最符合 GCA 当前 Python 单体、repository-local SQLite、PyInstaller standalone 和六平台
组合 CI 的现实。若未来目标转为具有复杂动画、插件市场或大规模 Web 前端团队参与的商业桌面
产品，再考虑把同一应用服务边界接到 Tauri + React 外壳。

## 2. 需求摘要

### 2.1 功能需求

- 选择并管理一个或多个本地 Git 仓库，展示 workspace、索引和 doctor 状态。
- 执行 init、index、sync，并显示阶段进度、日志、警告、失败和取消状态。
- 管理身份映射、合并和排除人员。
- 配置人员、时间范围、系统/显式时区、周期、时间口径、分支、发布和路径过滤器。
- 展示总体工作量、规模/难度分布、周期趋势、环比/同比、人员和工作事项详情。
- 查看 Evidence、历史 run、两个 run 的对比，并导出 JSON、Markdown 和 CSV。
- 生成和审核简历候选内容，查看 Provider 状态，但保持 LLM 与确定性结论隔离。

### 2.2 非功能需求

- Windows、Linux、macOS 上行为和报告契约一致。
- 默认离线、本地执行，不要求部署服务器，不向外暴露仓库内容。
- 长任务不能阻塞 UI；重复点击不能并发写入同一个 `.gca` workspace。
- GUI 和 CLI 必须共享 use case、规则、Schema、错误码语义和历史 run，不形成两套业务实现。
- 安装包应可由 CI 构建，支持版本显示、升级、代码签名和后续自动更新。
- GUI 崩溃不能破坏 SQLite 事务或留下无法恢复的 workspace 锁。

## 3. 当前状态

仓库没有 `doc/research/`。本提案以当前代码和架构文档为依据。

当前分层为：

```text
Typer CLI
  -> application use cases
      -> domain models and deterministic rules
          -> Git / SQLite / LLM / reporting adapters
```

与 GUI 直接相关的现状：

- CLI 位于 `src/git_contribution_analyzer/cli/app.py`，使用 `CommandEnvelope` 提供版本化 JSON。
- 业务入口已经拆到 `application/use_cases/`，包括索引、工作评估、周期序列、历史对比和报告导出。
- 写操作使用 repository-local `workspace_lock`；GUI 必须保留该并发边界。
- SQLite 和历史 run 是本地事实来源，报告从持久化 JSON 重放。
- PyInstaller 已生成三平台 CLI standalone，GitHub Actions 覆盖 Windows/Linux/macOS 和
  Python 3.12/3.13。
- use case 当前主要返回最终结果，尚无统一的进度、取消和后台任务端口。

因此，GUI 的首要架构工作不是绘制页面，而是补齐稳定的 presentation facade、进度事件和取消
协议，让 CLI 与 GUI 都能复用同一任务生命周期。

## 4. 方案一：PySide6 + QML，直接复用 Python Core

### 4.1 概述

新增 `gca-gui` Python entry point，以 PySide6 提供窗口、原生文件选择、系统主题和 QML UI。
GUI controller 调用 application use case，使用 Qt model/signal 将结果投影到界面。

### 4.2 实现结构

```text
QML views
  -> Qt view models / controllers       adapters/gui/
      -> GuiApplicationFacade           application/facades/
          -> existing use cases
              -> domain + existing adapters
```

建议增加：

- `application/ports/progress.py`：`ProgressEvent`、`ProgressReporter`、阶段和完成百分比。
- `application/ports/cancellation.py`：协作式 `CancellationToken`，只在事务安全边界取消。
- `application/facades/gui.py`：稳定、类型化、去 UI 框架的 GUI 调用门面。
- `adapters/gui/`：Qt controller、table model、settings 和任务调度。
- `gui/qml/`：页面、组件、主题和资源。
- `gca-gui.spec`：独立 GUI standalone；现有 `gca.spec` 保留 CLI。

耗时任务使用 `QThreadPool/QRunnable` 或专用 worker thread。UI 主线程只处理信号和 model 更新。
第一版使用协作式取消；不要在线程中强制终止 SQLite 写事务。相同仓库的写任务在 GUI 层排队，
底层 `workspace_lock` 继续作为最终保护。

### 4.3 页面建议

```text
App shell
  Repository switcher
  Status / sync indicator
  Navigation
    Overview
    Assessment
    Trends
    People
    Work items / Evidence
    Runs / Compare
    Resume
    Settings / Providers
```

Assessment 页面使用侧栏过滤器和主内容 tabs。Overview/Trends 使用 QML Chart，人员、事项和 Evidence
使用虚拟化 table/tree model。不要把完整报告 JSON 一次性转换成大量独立 QML object；用
`QAbstractTableModel` 按行投影。

### 4.4 优点

- 与当前 Python 架构最一致，application/domain 无需跨进程序列化。
- 不需要 localhost 服务、浏览器或 Rust/Node 构建链。
- Qt 的窗口、菜单、文件对话框、表格、无障碍和 HiDPI 跨平台能力成熟。
- QML 可以实现比传统 Qt Widgets 更现代的界面，并保留原生桌面行为。
- 可扩展现有 PyInstaller 和 GitHub Actions 发布流程。
- 默认本地运行，攻击面小，隐私模型与 CLI 一致。

### 4.5 缺点与风险

- PySide6 standalone 通常明显大于当前 CLI，预估 90-180 MB，取决于 Qt 模块和平台插件。
- QML 和 Qt model/signal 需要学习成本；复杂图表不如 Web 生态丰富。
- 必须避免引入 Qt WebEngine，否则包体和安全维护成本会显著上升。
- 需要处理 Linux X11/Wayland 插件、macOS notarization 和 Windows/macOS 代码签名。
- PySide6 使用 LGPL/商业双许可，发布时需要保留许可声明并遵循动态链接和替换要求。

**复杂性**：中

**风险**：低到中

**相对工作量**：中

## 5. 方案二：Tauri 2 + React，Python Sidecar

### 5.1 概述

使用 React/TypeScript 构建前端，以 Tauri 2 提供桌面窗口、系统集成和更新能力。把现有 GCA
standalone 作为 sidecar 打包，通过 JSON Lines 或本地 IPC 调用。

### 5.2 实现结构

```text
React SPA
  -> Tauri commands / event bus
      -> bundled GCA Python sidecar
          -> application use cases -> domain/adapters
```

不建议每次操作都执行一次 `gca ... --json`。应新增长生命周期的 `gca serve --stdio` 内部协议：

- stdin：版本化 request，包含 request ID、command 和参数。
- stdout：progress/result/error JSON Lines；stderr 仅用于诊断日志。
- 支持 cancel request、协议版本协商和 sidecar 崩溃恢复。
- sidecar 仍通过 workspace lock 保护本地状态。

### 5.3 优点

- React 图表、数据表、状态管理和测试生态最丰富，适合复杂趋势和对比体验。
- Tauri 比 Electron 更轻，系统权限可通过 capability 精确限制。
- UI 与 Python core 进程隔离；core 崩溃时可以重启 sidecar。
- 长期更容易招聘前端开发者，并扩展自动更新、深链接和系统托盘。

### 5.4 缺点与风险

- 同时维护 Python、Rust、Node 三套工具链和依赖供应链。
- 必须设计和版本化 IPC；错误、取消、进度和大报告传输都增加复杂度。
- 每个平台都要处理 sidecar 命名、权限、签名和 notarization。
- 调试跨进程问题比 PySide6 直接调用更困难。
- 虽然 Tauri 外壳较小，捆绑 Python runtime 后总体包体不会像纯 Rust 应用那样小。

**复杂性**：高

**风险**：中到高

**相对工作量**：大

## 6. 方案三：FastAPI + React，本地浏览器 UI

### 6.1 概述

新增 `gca gui`，在 `127.0.0.1` 随机端口启动 FastAPI，并打开系统浏览器加载 React SPA。
后端直接调用 application use case，通过 WebSocket/SSE 推送任务进度。

### 6.2 优点

- 最快验证信息架构和图表交互，前端生态完整。
- Python 后端直接复用 core，不需要 Rust。
- SPA 可在未来复用于 Tauri 外壳。
- 浏览器 DevTools 让 UI 调试和自动化测试简单。

### 6.3 缺点与风险

- 不是完整原生桌面体验，依赖系统浏览器，窗口和文件交互不一致。
- 必须防止本地其他进程或网页调用 API：只绑定 loopback、使用随机会话 token、校验 Origin，
  并设置严格 CSP/CSRF 策略。
- 需要管理端口冲突、浏览器生命周期、后台进程退出和重复实例。
- 若最终仍要桌面安装包，之后还要增加 Tauri/Electron 外壳，存在二次工程成本。

**复杂性**：中

**风险**：中

**相对工作量**：小到中

## 7. 比较矩阵

| 标准 | PySide6 + QML | Tauri + React | FastAPI + React |
|---|---|---|---|
| 符合当前 Python 架构 | 最佳 | 中，需要 IPC | 好 |
| 跨平台桌面体验 | 好 | 最佳 | 一般 |
| 图表和前端生态 | 中到好 | 最佳 | 最佳 |
| 构建链复杂度 | 中 | 高 | 中 |
| 本地安全边界 | 最简单 | 好 | 需要额外防护 |
| 长任务隔离 | 线程/可选 worker | sidecar 天然隔离 | server worker |
| 安装包体 | 较大 | 中到较大 | 中 |
| 对现有 CI 改动 | 中 | 大 | 中 |
| MVP 速度 | 快 | 慢 | 最快 |
| 长期维护风险 | 低到中 | 中到高 | 中 |

## 8. 推荐方案

### 8.1 推荐：PySide6 + QML

这是当前 GCA 的最佳平衡点。GCA 是本地、证据驱动、Python-first 的开发者工具，不需要 Web
服务或多语言进程边界。现有 application/domain 分层已经允许新增 GUI adapter，PySide6 能最大限度
复用这些边界，并沿用当前 standalone 发布思路。

关键决策：

1. GUI 不调用 Typer command，也不解析 CLI 文本；它调用 application facade。
2. GUI 不直接执行 SQL；历史 run、报告和身份都通过 use case 访问。
3. 在第一张复杂页面之前先实现 progress/cancellation port 和任务状态机。
4. CLI 和 GUI 保持两个 entry point、两个 standalone，避免无 GUI 环境安装 Qt 依赖。
5. 使用 `[gui]` optional dependency，例如 `PySide6>=6.8,<7`；core wheel 不强制安装 Qt。
6. 第一版不引入 WebEngine、自动更新或插件系统，控制包体和攻击面。

### 8.2 何时改选 Tauri

只有同时满足以下条件时优先 Tauri：

- 团队已有成熟 React/TypeScript 能力，并接受 Rust/Node/Python 三套构建链。
- UI 需要大量定制图表、动画、复杂编辑器或未来共享 Web 前端。
- 愿意先把 GCA core 提升为稳定的版本化 IPC service，而不是临时解析 CLI JSON。

## 9. 建议实施阶段

### 阶段 1：GUI-ready application contract

- 新增 GUI facade、进度事件、取消 token 和任务状态模型。
- 为 init/index/sync/assess/report 增加阶段化进度，不改变现有最终 JSON Schema。
- 增加同仓库写任务排队和进程退出恢复测试。

### 阶段 2：桌面壳与仓库生命周期

- 新增 `gca-gui`、QML app shell、仓库选择、recent repositories、status/doctor、init/sync。
- 实现错误详情、日志抽屉、进度和取消。
- 增加 headless Qt smoke 和 Windows/Linux/macOS 启动测试。

### 阶段 3：评估工作台

- 实现过滤器、人员选择、周期/时间口径、趋势、分布、事项和 Evidence drill-down。
- 使用 table model 处理大报告；图表只消费聚合序列。
- 实现 run 历史、compare 和 JSON/Markdown/CSV 导出。

### 阶段 4：身份、简历和设置

- 身份映射/合并、简历候选审核、Provider 配置和健康检查。
- 敏感配置继续使用环境变量，不将 API key 写入 GUI settings。

### 阶段 5：发布工程

- 新增三平台 `gca-gui` artifact，保留 CLI artifact。
- 增加 Qt license notices、Linux platform plugin 检查、macOS notarization 和 Windows 签名。
- 使用 Playwright/QML screenshot 或 Qt Quick Test 做关键视图的跨分辨率视觉回归。

## 10. 初始验收标准

- GUI 在 Windows、Ubuntu 和 macOS 上能选择中文/空格路径仓库并完成 init、sync、assess。
- GUI 与相同参数的 CLI 产生相同 snapshot ID、run JSON 和报告。
- 运行索引或评估时窗口持续响应；取消不会留下 RUNNING run 或损坏 SQLite。
- 同仓库写任务不会并发，不同仓库任务可以并行。
- 10,000 个事项的 table model 滚动和筛选不需要一次创建 10,000 个 QML component。
- 发布制品不包含 API key，普通 core wheel 不依赖 PySide6。
- GUI standalone 通过三平台启动、版本、中文路径和最小仓库生命周期测试。
