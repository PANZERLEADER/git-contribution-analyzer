# GCA 跨平台 GUI 详细实施方案

## 1. 基本信息

| 项目 | 内容 |
|---|---|
| 功能名称 | GCA 跨平台桌面 GUI |
| 建议目标版本 | `0.4.0` |
| 技术栈 | Python 3.12/3.13、PySide6、QML/Qt Quick Controls、Qt Charts、Pydantic、SQLAlchemy、SQLite、PyInstaller |
| 相关提案 | `doc/proposals/cross-platform-gui-proposals.md`（方案一：PySide6 + QML） |
| 方案类型 | 桌面入口适配器、应用层任务契约、可选 GUI 依赖、三平台发布制品 |
| 日期 | 2026-07-15 |

本计划使用设计文档型模板。功能不新增 REST API，不引入 localhost 服务，也不改变 GCA 的
确定性评估和报告 Schema；GUI 是与 Typer CLI 并列的入站适配器。

## 2. 背景和目标

### 2.1 当前状态

GCA `0.3.0` 已具备：

- Python-first 的 `domain -> application -> adapters` 分层以及 Typer CLI 入口。
- repository-local `.gca/index.sqlite`、版本化 run JSON 和可重放报告。
- `init/index/sync/status/doctor` 仓库生命周期。
- 人员筛选、身份映射/合并/撤销、工作评估、周期趋势、历史 run 对比和简历生成。
- `authored/committed/merged/landed/released` 时间口径，以及使用系统时区的无偏移时间输入。
- Windows、Linux、macOS CI 和 PyInstaller CLI standalone 发布流程。

现有 GUI 相关限制：

- use case 主要是同步函数，只返回最终结果，没有统一进度、取消和任务状态协议。
- provider 列表/健康检查和时间字符串解析仍有部分逻辑留在 CLI 适配器内。
- 长时间 Git、SQLite 和 LLM 操作若直接从 Qt 主线程调用会冻结窗口。
- 当前发布流程只生成 `gca` CLI 制品，没有 Qt 插件、QML 资源和 GUI 启动验证。
- 仓库中没有 `doc/research/`；本计划以当前源码、架构文档和已批准提案为事实依据。

### 2.2 问题陈述

GCA 需要让不熟悉 CLI 的用户在 Windows、Linux 和 macOS 上完成仓库初始化、索引、评估、
趋势查看、历史对比和报告导出，同时不能复制业务规则、绕过 workspace lock、改变既有 JSON
契约或把仓库内容暴露给本地 Web 服务。

### 2.3 目标

1. 提供独立的 `gca-gui` 入口和三平台可分发制品，同时保留现有 `gca` CLI。
2. GUI 与 CLI 调用同一 application use case；相同输入产生相同 snapshot、run JSON 和报告。
3. 所有耗时任务在后台执行，UI 主线程持续响应，并提供阶段进度和协作式取消。
4. 同一仓库的写任务串行，不同仓库任务可并行，`workspace_lock` 保持最终并发保护。
5. GUI 的日期时间输入使用当前操作系统时区，无偏移输入与 CLI 语义完全一致。
6. 10,000 条工作项或 Evidence 使用虚拟化 Qt model 展示，不创建等量 QML 组件。
7. GUI core 新代码达到 90% 目标覆盖率，整体项目继续满足 80% 覆盖率门禁。

### 2.4 非目标

- 不引入 Tauri、Electron、React、FastAPI、WebSocket 或 Qt WebEngine。
- 不实现云同步、账户体系、多人协作、插件市场和自动更新。
- 不在第一版内编辑 `.gca/config.yml` 的全部字段；Provider 页面以只读状态和健康检查为主。
- 不把 API key、token 或凭据写入 QSettings、仓库或发布制品。
- 不修改工作量、难度、排名、趋势、Evidence 或简历强度规则。
- 不删除 CLI，也不要求普通 core wheel 安装 PySide6。

## 3. 需求和验收标准

### 3.1 功能需求

#### FR-01：独立桌面入口

新增 `gca-gui` console script 和 GUI standalone。启动时显示版本、应用壳和仓库选择器。

验收标准：

- `pip install -e ".[gui]"` 后 `gca-gui --version` 可用。
- 未安装 `[gui]` 时 `gca` CLI 和 core wheel 不受影响。
- GUI import 不出现在 domain/application 模块依赖链中。

#### FR-02：仓库选择和最近仓库

用户可使用原生目录选择器打开 Git 仓库，并从最近仓库列表重新打开。

验收标准：

- 支持中文、空格、长路径以及 bare worktree discovery 的现有规则。
- 最近仓库只保存规范化路径和最后打开时间，最多 10 条。
- 路径不存在或不是 Git 仓库时显示可操作错误，不关闭应用。

#### FR-03：仓库生命周期

GUI 支持 `status`、`doctor`、`init`、完整 `index` 和增量 `sync`。

验收标准：

- 未初始化仓库显示初始化动作；已初始化仓库显示索引和健康状态。
- 写任务不能因重复点击而并发执行。
- 完成结果的计数与相同参数的 CLI JSON 一致。

#### FR-04：后台任务、进度和取消

耗时操作必须通过统一任务调度器执行，并产生版本化进度事件。

验收标准：

- 任务状态遵循 `QUEUED -> RUNNING -> SUCCEEDED|FAILED|CANCELLED`。
- 取消请求先进入 `CANCELLING`，只在事务安全点生效。
- 取消或异常不留下不可恢复的 workspace lock。
- 已创建的 analysis run 被取消后不得保持 `RUNNING`。

#### FR-05：身份管理

GUI 支持身份列表、未解决过滤、映射、merge preview、确认 merge、合并历史和撤销。

验收标准：

- 破坏性动作必须二次确认，并展示 source、target 和将移动的 alias。
- GUI 调用现有 identity use case，不直接执行 SQL。
- 完成操作后自动刷新身份和仓库状态。

#### FR-06：评估条件

GUI 支持人员选择、全员/排除人员、排名维度、时间范围、周期、分支、release、scope、delivery
和时间口径。

验收标准：

- `since` 必须不晚于 `until`，无效范围不能启动任务。
- 周期仅允许 `week/month/quarter`，且必须同时指定起止时间。
- 时间口径仅允许 `authored/committed/merged/landed/released`。
- GUI 日期和时间按系统时区解释；报告继续保存带 offset 的 ISO 8601 时间。
- 人员选择规则与 CLI 一致，不在 QML 中复制 selector 解析规则。

#### FR-07：评估结果和趋势

GUI 展示总体工作量、规模/难度分布、人员排名、周期趋势、环比和同比。

验收标准：

- 图表只读取报告中的聚合序列，不重新计算指标。
- table model 支持排序、过滤、分页式加载或虚拟化滚动。
- 空数据、PARTIAL run、warnings 和 limitations 有明确状态。

#### FR-08：工作项和 Evidence 下钻

用户可从人员/评估结果进入工作项，再查看关联 Evidence、commit hash、路径和指标。

验收标准：

- 选择工作项只更新详情 model，不重跑评估。
- commit hash 可复制；外部打开动作必须由用户明确触发。
- 默认不把邮箱显示在导出或页面主表中。

#### FR-09：run 历史和比较

GUI 支持列出、查看和比较两个历史 assessment run。

验收标准：

- 比较前校验 run 类型；不可比条件显示现有 use case 返回的 warnings。
- 历史详情从持久化 JSON 加载，不静默重跑分析。
- base/target 选择顺序清晰且可交换。

#### FR-10：报告导出

GUI 支持 JSON、Markdown 和 CSV 导出，并使用原生保存对话框。

验收标准：

- 导出内容由现有 renderer/use case 生成。
- 覆盖现有文件前必须确认；写入失败不损坏原文件。
- CSV 的 `include_email` 必须由用户显式开启。

#### FR-11：简历和 Provider 状态

GUI 支持简历候选生成、Provider 列表和已选 Provider 健康检查。

验收标准：

- 简历强度仍由确定性 Evidence 限制。
- Provider 测试在后台执行并尊重当前配置超时。
- GUI 只展示 `apiKeyEnv` 名称和“是否已配置”，不显示环境变量值。

#### FR-12：本地偏好设置

GUI 保存窗口尺寸、主题模式、最近仓库和最后使用的非敏感筛选条件。

验收标准：

- 设置保存在操作系统应用配置目录，不写入 `.gca`。
- 不保存 API key、完整报告、Evidence 或仓库文件内容。
- 设置损坏时恢复默认值并记录 warning。

### 3.2 非功能需求

1. **NFR-01 响应性**：后台任务运行时，UI 事件循环 95 百分位响应时间小于 100 ms。
2. **NFR-02 启动**：开发环境冷启动目标小于 3 秒，standalone 冷启动目标小于 8 秒。
3. **NFR-03 大数据展示**：10,000 行 model 初次绑定小于 1 秒，滚动不创建 10,000 个 QML delegate。
4. **NFR-04 并发**：同仓库 mutation 串行；不同仓库最多并行 `min(4, cpu_count)` 个任务。
5. **NFR-05 安全**：无本地监听端口；无凭据持久化；外部链接和文件打开均由用户触发。
6. **NFR-06 跨平台**：Windows 11、当前 Ubuntu LTS、当前 macOS runner 上完成启动和最小生命周期验证。
7. **NFR-07 可访问性**：控件有可读名称、键盘焦点顺序、系统缩放支持，颜色不是唯一状态信号。
8. **NFR-08 兼容性**：现有 CLI 命令、退出码、JSON Schema、SQLite migration 和报告输出保持兼容。
9. **NFR-09 可测试性**：项目总覆盖率不低于 80%，application/domain 门禁不低于 90%，GUI Python 新代码目标 90%。
10. **NFR-10 包体**：不包含 Qt WebEngine；各平台 GUI 制品目标不超过 180 MB，超出时需要记录模块分析。

## 4. 技术设计

### 4.1 总体架构

```text
QML Views / Qt Quick Controls / Qt Charts
        |
        v
Qt Controllers + QAbstractItemModel        src/.../adapters/gui/
        |
        v
GuiApplicationFacade                       src/.../application/facades/gui.py
        |
        +--> ProgressReporter / CancellationToken
        +--> request DTO + shared validation
        |
        v
Existing application use cases
        |
        v
Domain rules + Git / SQLite / LLM / reporting adapters
```

依赖方向必须满足：

- QML 只调用注册到 QML context 的 controller/model。
- `adapters/gui` 可以导入 PySide6 和 application；application/domain 不得导入 PySide6。
- facade 调用 use case，不调用 Typer command，不构造 `CommandEnvelope`，不解析 CLI 文本。
- GUI 不直接实例化 SQLAlchemy table，也不读取 `.gca/index.sqlite`。
- `workspace_lock` 仍由 use case/存储适配器持有，GUI 队列不是锁的替代品。

### 4.2 应用层进度协议

新增 `application/ports/progress.py`：

```python
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    schema_version: str
    task_id: str
    operation: str
    stage: str
    repository: Path
    current: int | None
    total: int | None
    message: str
    occurred_at: datetime


class ProgressReporter(Protocol):
    def report(self, event: ProgressEvent) -> None: ...
```

同时提供 `NullProgressReporter`。`stage` 使用稳定小写标识，例如：

- `discovering_repository`
- `reading_commits`
- `resolving_delivery`
- `writing_index`
- `selecting_people`
- `building_snapshot`
- `evaluating_period`
- `calling_provider`
- `persisting_run`
- `rendering_report`

`message` 只用于展示，不成为测试或自动化契约；测试依赖 `stage/current/total`。

### 4.3 协作式取消协议

新增 `application/ports/cancellation.py`：

```python
class CancellationToken(Protocol):
    @property
    def cancellation_requested(self) -> bool: ...
    def raise_if_cancelled(self) -> None: ...


class OperationCancelled(Exception):
    pass
```

应用层提供永不取消的默认 token；Qt adapter 使用 `threading.Event` 实现可取消 token。

安全点规则：

1. Git 批量读取前后检查。
2. 每个人员、每个 period 和每个 LLM 请求之间检查。
3. SQLite 写事务开始前检查；事务开始后不强制终止线程。
4. provider 同步调用开始后只能等待 provider 返回或超时，UI 状态保持 `CANCELLING`。
5. 已调用 `start_run()` 后发生取消，必须调用 `cancel_run()`，把状态写为 `CANCELLED`。

`analysis_runs.status` 当前为字符串且无数据库 CHECK 约束，因此新增 `CANCELLED` 不需要 Alembic DDL
迁移。需更新 run 文档、列表展示和兼容性测试。进程崩溃恢复继续使用 `FAILED`：在确认可获得
workspace lock 后，把遗留 `RUNNING` run 标记为 `FAILED`，错误原因固定为
`Interrupted before completion`。

### 4.4 GUI facade 和请求 DTO

新增 `application/dto/gui.py`，定义框架无关、不可变请求对象：

```python
@dataclass(frozen=True, slots=True)
class AssessmentRequest:
    repository: Path
    person_selectors: tuple[str, ...]
    all_people: bool
    exclude_selectors: tuple[str, ...]
    rank_by: tuple[str, ...]
    ranking_config: Path | None
    since_text: str | None
    until_text: str | None
    period: str | None
    branch: str | None
    release: str | None
    scope: str | None
    delivery: str | None
    time_basis: str
    use_llm: bool


@dataclass(frozen=True, slots=True)
class ExportRequest:
    repository: Path
    run_id: str
    report_format: str
    target: Path
    include_email: bool
    overwrite: bool
```

新增 `application/facades/gui.py`，`GuiApplicationFacade` 对 GUI 暴露以下方法：

```python
open_repository(path) -> RepositoryView
initialize(path, progress, cancellation) -> dict[str, Any]
status(path) -> dict[str, Any]
doctor(path) -> dict[str, Any]
index(path, full_rebuild, progress, cancellation) -> dict[str, Any]
list_identities(path, unresolved_only) -> dict[str, Any]
map_identity(path, request) -> dict[str, Any]
preview_identity_merge(path, request) -> dict[str, Any]
merge_identities(path, request) -> dict[str, Any]
list_identity_merges(path, status) -> dict[str, Any]
unmerge_identities(path, merge_id) -> dict[str, Any]
assess(request, progress, cancellation) -> dict[str, Any]
list_runs(path) -> dict[str, Any]
get_run(path, run_id) -> dict[str, Any]
compare_runs(path, base_run_id, target_run_id) -> dict[str, Any]
export_report(request, progress, cancellation) -> Path
generate_resume(request, progress, cancellation) -> dict[str, Any]
list_providers(path) -> dict[str, Any]
test_provider(path, progress, cancellation) -> dict[str, Any]
```

facade 的职责仅包括：

- 请求 DTO 校验和规范化。
- 加载 workspace config、ranking config 和 provider。
- 在单次评估与周期评估 use case 之间路由。
- 把已知 domain/application 异常转换为结构化 `GuiError`。
- 不重新实现指标计算、身份解析、报告渲染或存储查询。

### 4.5 共享时间边界

把 `cli/app.py` 中 `_parse_boundary()`、`_parse_boundaries()`、
`_localize_system_time()` 和 `_uses_system_timezone()` 移到
`application/services/time_boundaries.py`，CLI 改为调用共享服务。

规则：

- 仅日期的 `since` 解析为系统时区当天 `00:00:00`。
- 仅日期的 `until` 解析为系统时区当天 `23:59:59.999999`。
- 不带 offset 的日期时间使用 `datetime.now().astimezone().tzinfo` 对应的系统时区。
- 带 `Z` 或显式 offset 的输入保持其 offset 语义。
- 解析后统一校验 `since <= until`。
- GUI 的日期/时间控件生成不带 offset 的本地文本，交给同一服务解析，禁止 QML 自行换算 UTC。
- 周、月、季度继续由 `domain/services/assessment_periods.py` 按报告 offset 分桶。

### 4.6 任务调度和线程模型

新增 `adapters/gui/task_runner.py`：

```text
TaskRequest
  id
  repository_key
  operation
  mutates_workspace
  callable
  cancellation_source

RepositoryTaskScheduler
  global QThreadPool: max min(4, cpu_count)
  per-repository FIFO
  at most one mutation task per repository
  read task waits while same-repository mutation is active

TaskBridge(QObject)
  signals: queued, started, progress, succeeded, failed, cancelled
```

所有 Qt signal 的 payload 使用 Qt 可传递的 primitive/dict，model 更新只发生在主线程。worker
不得持有 QML object。应用退出时：

1. 对可取消任务请求取消。
2. 阻止提交新任务。
3. 等待事务中的任务完成，显示明确的退出等待状态。
4. 超时后仍不使用 `QThread.terminate()`；由用户选择继续等待或放弃退出。

### 4.7 Controller 和 Qt model

Controller 按工作区拆分，避免单一 QObject 承担全部状态：

| Controller | 职责 |
|---|---|
| `ApplicationController` | 导航、当前仓库、全局通知、应用退出 |
| `RepositoryController` | 选择仓库、recent、status、doctor、init/index/sync |
| `AssessmentController` | 筛选表单、参数校验、启动/取消评估、结果路由 |
| `RunsController` | run 列表、详情、base/target 对比、导出 |
| `IdentityController` | 身份列表、映射、merge preview/执行/撤销 |
| `ResumeController` | 简历参数、生成结果、warnings |
| `ProviderController` | Provider 列表、选择状态和健康检查 |

数据量可能较大的列表使用 `QAbstractTableModel`：

- `PersonTableModel`
- `WorkItemTableModel`
- `EvidenceTableModel`
- `RunTableModel`
- `PeriodTrendModel`

model 暴露稳定 role 名，支持 `reset_from_report()`、排序和文本过滤。QML delegate 高度固定，
不使用嵌套卡片；详情通过侧边 inspector 或独立页面呈现。

### 4.8 页面和导航

```text
ApplicationWindow
  Top bar: repository switcher, sync status, active task
  Navigation rail
    Overview
    Assessment
    Trends
    People
    Work Items / Evidence
    Runs / Compare
    Resume
    Settings / Providers
  Main content
  Task drawer: progress, logs, warnings, cancel
```

页面约束：

- 第一屏直接进入可用工作台，不增加营销型 landing page。
- 评估筛选器使用侧栏；时间口径和周期使用 segmented control/menu。
- 二元配置使用 toggle/checkbox，数字使用输入框或 stepper。
- 命令按钮使用 Qt 标准图标或随包分发的 Lucide 图标，并提供 tooltip/accessibility name。
- 表格、筛选栏和图表使用稳定尺寸约束，动态内容不能导致整体布局跳动。
- 窄窗口下导航折叠，筛选器切换为 drawer；文本允许换行但不能遮挡操作控件。
- 第一版支持系统浅色/深色主题，不引入自定义渐变或装饰性背景。

### 4.9 错误模型

新增 `GuiError`：

```text
code: NOT_A_REPOSITORY | WORKSPACE | IDENTITY | REPORT | PROVIDER |
      VALIDATION | CANCELLED | UNEXPECTED
title: 短标题
message: 用户可操作说明
detail: 诊断详情，可折叠
retryable: bool
```

已知异常沿用 `domain/errors.py` 分类；未知异常记录 traceback 到本机日志，只向界面展示通用消息。
日志目录使用 `platformdirs.user_log_dir("gca")`，默认轮转，禁止记录 API key、Provider prompt
全文或仓库文件内容。

### 4.10 本地设置

`adapters/gui/settings.py` 使用 `QSettings`，键如下：

```text
ui/theme = system|light|dark
ui/windowGeometry = byte array
repositories/recent = [{path, lastOpenedAt}]
assessment/lastPeriod = none|week|month|quarter
assessment/lastTimeBasis = authored|committed|merged|landed|released
assessment/includeEmail = false
```

人员 selector、API key、完整路径过滤器和报告内容默认不持久化。最近仓库路径属于必要本地偏好，
可在设置页一键清除。

## 5. 数据模型、兼容性和迁移

### 5.1 SQLite 变更

本功能不新增表或字段，不创建 Alembic migration。

需要修改 `SqliteAnalysisStore`：

```python
def cancel_run(self, run_id: str, completed_at: datetime) -> None: ...
def fail_running_runs(self, completed_at: datetime, message: str) -> int: ...
```

- `cancel_run()` 写入 `status="CANCELLED"`、`completed_at` 和固定错误说明。
- `fail_running_runs()` 只允许在持有 repository workspace lock 时调用。
- `get_run()` 仍只返回有 `result_json` 的已完成报告；取消 run 可在 `list_runs()` 中看到，但不能导出。
- 既有 `COMPLETED/PARTIAL/FAILED/RUNNING` 状态保持不变。

### 5.2 GUI task model

GUI task 只存在于内存，不写入 `.gca`：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID string | 单次 GUI 任务 ID |
| `repositoryKey` | normalized path | 调度分区键 |
| `operation` | string | `sync/assess/export/...` |
| `state` | enum | `QUEUED/RUNNING/CANCELLING/SUCCEEDED/FAILED/CANCELLED` |
| `progress` | 0..1/null | 可确定总量时设置 |
| `stage` | string | 稳定应用层阶段标识 |
| `message` | string | 展示文本 |
| `createdAt/startedAt/finishedAt` | aware datetime | 系统时间 |

### 5.3 向后兼容性

- `gca` console script 和所有现有命令保持不变。
- use case 新增的 `progress` 和 `cancellation` 参数均为 keyword-only 且有 no-op 默认值。
- `CommandEnvelope`、work-assessment Schema、snapshot canonical JSON 不加入 GUI 字段。
- GUI request DTO 不持久化进 run；facade 仍把原有标准参数传给 use case。
- 时间解析移动后必须由现有 `test_time_boundaries.py` 证明行为不变。
- core wheel 不依赖 PySide6；`gui` wheel extra 才安装 Qt。

### 5.4 回滚和降级

- GUI 是新增入口，出现发布问题时可从 release 中移除 GUI artifact，CLI 制品继续可用。
- 不存在数据库 DDL，回滚无需 downgrade migration。
- `CANCELLED` 状态对旧版本表现为未知但可列出的字符串；旧版本不会把它当成可导出报告。
- GUI QML 加载失败时，进程以非零状态退出并写本机日志，不修改仓库。
- Qt Charts 不可用时趋势页显示数据表和 warning，其余页面仍可使用。

## 6. 影响文件清单

### 6.1 新增 application 文件

1. `src/git_contribution_analyzer/application/ports/progress.py`
   - `ProgressEvent`、`ProgressReporter`、`NullProgressReporter`。
2. `src/git_contribution_analyzer/application/ports/cancellation.py`
   - `CancellationToken`、默认 token、`OperationCancelled`。
3. `src/git_contribution_analyzer/application/dto/gui.py`
   - GUI request/result DTO 和 `GuiError`。
4. `src/git_contribution_analyzer/application/facades/__init__.py`
5. `src/git_contribution_analyzer/application/facades/gui.py`
   - 框架无关 GUI facade 和依赖装配。
6. `src/git_contribution_analyzer/application/services/time_boundaries.py`
   - CLI/GUI 共用的系统时区解析和范围校验。
7. `src/git_contribution_analyzer/application/use_cases/list_providers.py`
   - 从 CLI 提取 Provider 描述和选择状态。
8. `src/git_contribution_analyzer/application/use_cases/test_provider.py`
   - 从 CLI 提取 Provider 健康检查。
9. `src/git_contribution_analyzer/application/use_cases/export_report.py`
   - 原子写出报告和覆盖策略。
10. `src/git_contribution_analyzer/application/use_cases/recover_runs.py`
    - 在持锁条件下恢复崩溃遗留的 `RUNNING` run。

### 6.2 新增 GUI Python 文件

1. `src/git_contribution_analyzer/adapters/gui/__init__.py`
2. `src/git_contribution_analyzer/adapters/gui/app.py`
   - `gca-gui` 主入口、QApplication/QQmlApplicationEngine 和命令行 smoke 参数。
3. `src/git_contribution_analyzer/adapters/gui/resources.py`
   - 通过 `importlib.resources` 定位 QML、字体和图标。
4. `src/git_contribution_analyzer/adapters/gui/settings.py`
   - QSettings schema、recent repository 和非敏感偏好。
5. `src/git_contribution_analyzer/adapters/gui/task_runner.py`
   - 后台 worker、repository scheduler、Qt signal bridge 和取消 source。
6. `src/git_contribution_analyzer/adapters/gui/controllers/application.py`
7. `src/git_contribution_analyzer/adapters/gui/controllers/repository.py`
8. `src/git_contribution_analyzer/adapters/gui/controllers/assessment.py`
9. `src/git_contribution_analyzer/adapters/gui/controllers/runs.py`
10. `src/git_contribution_analyzer/adapters/gui/controllers/identities.py`
11. `src/git_contribution_analyzer/adapters/gui/controllers/resume.py`
12. `src/git_contribution_analyzer/adapters/gui/controllers/providers.py`
13. `src/git_contribution_analyzer/adapters/gui/models/base_table.py`
14. `src/git_contribution_analyzer/adapters/gui/models/people.py`
15. `src/git_contribution_analyzer/adapters/gui/models/work_items.py`
16. `src/git_contribution_analyzer/adapters/gui/models/evidence.py`
17. `src/git_contribution_analyzer/adapters/gui/models/runs.py`
18. `src/git_contribution_analyzer/adapters/gui/models/trends.py`

每个 `controllers/` 和 `models/` 目录补充 `__init__.py`。

### 6.3 新增 QML 和资源文件

1. `src/git_contribution_analyzer/gui/qml/Main.qml`
2. `src/git_contribution_analyzer/gui/qml/components/AppTopBar.qml`
3. `src/git_contribution_analyzer/gui/qml/components/NavigationRail.qml`
4. `src/git_contribution_analyzer/gui/qml/components/TaskDrawer.qml`
5. `src/git_contribution_analyzer/gui/qml/components/EmptyState.qml`
6. `src/git_contribution_analyzer/gui/qml/components/ErrorBanner.qml`
7. `src/git_contribution_analyzer/gui/qml/components/MetricBand.qml`
8. `src/git_contribution_analyzer/gui/qml/components/FilterDrawer.qml`
9. `src/git_contribution_analyzer/gui/qml/pages/RepositoryPage.qml`
10. `src/git_contribution_analyzer/gui/qml/pages/OverviewPage.qml`
11. `src/git_contribution_analyzer/gui/qml/pages/AssessmentPage.qml`
12. `src/git_contribution_analyzer/gui/qml/pages/TrendsPage.qml`
13. `src/git_contribution_analyzer/gui/qml/pages/PeoplePage.qml`
14. `src/git_contribution_analyzer/gui/qml/pages/WorkItemsPage.qml`
15. `src/git_contribution_analyzer/gui/qml/pages/RunsPage.qml`
16. `src/git_contribution_analyzer/gui/qml/pages/ResumePage.qml`
17. `src/git_contribution_analyzer/gui/qml/pages/SettingsPage.qml`
18. `src/git_contribution_analyzer/gui/qml/theme/Theme.qml`
19. `src/git_contribution_analyzer/gui/assets/icons/`
    - 只收录实际使用的 Lucide SVG，并保留上游许可证。
20. `src/git_contribution_analyzer/gui/assets/app-icon.*`
    - Windows `.ico`、macOS `.icns` 和 PNG 源图。

### 6.4 新增测试和验证文件

1. `tests/unit/test_progress.py`
2. `tests/unit/test_cancellation.py`
3. `tests/unit/test_gui_facade.py`
4. `tests/unit/test_gui_settings.py`
5. `tests/unit/test_gui_task_runner.py`
6. `tests/unit/test_gui_models.py`
7. `tests/unit/test_provider_use_cases.py`
8. `tests/integration/test_gui_repository_lifecycle.py`
9. `tests/integration/test_gui_assessment_parity.py`
10. `tests/integration/test_gui_cancellation.py`
11. `tests/integration/test_gui_export.py`
12. `tests/e2e/test_gui_smoke.py`
13. `tests/gui/tst_navigation.qml`
14. `tests/gui/tst_assessment_form.qml`
15. `tests/gui/tst_run_compare.qml`
16. `scripts/verify_gui_standalone.py`
17. `gca-gui.spec`

Qt Python 测试通过 `pytest.importorskip("PySide6")` 隔离；CI 的 GUI job 必须安装 `[gui]`，因此
不会误跳过。QML test 使用 `QT_QPA_PLATFORM=offscreen`，平台 standalone smoke 使用真实平台插件。

### 6.5 修改现有文件

1. `pyproject.toml`
   - 新增 `[gui]` optional dependency：`PySide6>=6.8,<7`。
   - dev GUI 测试依赖按 CI job 安装，不加入普通 core 依赖。
   - 新增 `gca-gui = "git_contribution_analyzer.adapters.gui.app:main"`。
   - 确保 QML、图标和许可证作为 package data 进入 wheel。
   - 增加 Desktop Environment classifier。
2. `src/git_contribution_analyzer/cli/app.py`
   - 改用共享 time boundary、provider 和 export use case，删除对应 CLI 私有业务逻辑。
3. `src/git_contribution_analyzer/application/ports/__init__.py`
4. `src/git_contribution_analyzer/application/dto/__init__.py`
5. `src/git_contribution_analyzer/application/use_cases/index_repository.py`
6. `src/git_contribution_analyzer/application/use_cases/analyze_contributions.py`
7. `src/git_contribution_analyzer/application/use_cases/analyze_project.py`
8. `src/git_contribution_analyzer/application/use_cases/assess_work.py`
9. `src/git_contribution_analyzer/application/use_cases/assess_work_series.py`
10. `src/git_contribution_analyzer/application/use_cases/generate_resume.py`
    - 以上耗时 use case 增加 progress/cancellation keyword-only 参数和安全点。
11. `src/git_contribution_analyzer/adapters/storage/sqlite/analysis.py`
    - 新增取消 run 和恢复遗留 RUNNING run 方法。
12. `src/git_contribution_analyzer/application/use_cases/list_runs.py`
    - 明确返回 CANCELLED/FAILED 状态，但不尝试加载缺失 report。
13. `tests/unit/test_time_boundaries.py`
    - 导入路径迁移到 application service，保留并扩充系统时区用例。
14. `tests/e2e/test_release_readiness.py`
    - 增加 GUI spec、GUI 文档和 release artifact 断言。
15. `.github/workflows/ci.yml`
    - 保留 core 六组合 job；新增三平台 Python 3.12 GUI quality/smoke job。
16. `.github/workflows/release.yml`
    - 安装 `[gui]`，构建、验证和上传 `gca-gui` 制品。
17. `README.md`、`README.zh-CN.md`
    - 增加 GUI 安装、启动、与 CLI 并存说明。
18. `doc/architecture/architecture.md`、`doc/zh-CN/architecture.md`
    - 把 GUI 标为并列入站 adapter，记录线程和任务边界。
19. `doc/guides/installation.md`
    - 增加 `[gui]` 安装和各平台制品说明。
20. `doc/guides/privacy.md`
    - 记录 QSettings、日志和凭据边界。
21. `doc/cli/cli-reference.md`
    - 说明 CLI 行为不变，并记录共享时间解析语义。
22. `THIRD_PARTY_NOTICES.md`
    - 增加 Qt/PySide6 和 Lucide 许可证声明。

## 7. 实施阶段

### 阶段 0：Qt 可行性和发布探针

目标：在正式改造 application 前，证明最小 QML、Qt Charts、中文路径和 PyInstaller 能在三平台工作。

任务：

1. 在独立 feature branch 增加临时最小 `gca-gui` 窗口和 `gca-gui.spec`。
2. 加载一个 QML 页面、一个 table model 和一个 Qt Charts 折线图。
3. 在三平台 CI 构建并运行 `--version`、QML load 和自动退出 smoke。
4. 记录实际包体、启动时间、Linux Qt platform plugin 和 macOS bundle 行为。
5. 确认 PySide6/LGPL notices 和 Lucide ISC notice 的发布方式。

交付物：

- 三平台探针制品和 CI 结果。
- 包体/启动基线记录。
- 对 `gca-gui.spec` 打包策略的已确认决定。

验收标准：

- [ ] Windows、Ubuntu、macOS 都能加载非空 QML 窗口并自动退出。
- [ ] 中文和空格路径资源可加载。
- [ ] 不包含 Qt WebEngine。
- [ ] GUI 制品目标小于 180 MB；超出时有模块清单和处理结论。

预计工作量：2-3 人日。

### 阶段 1：GUI-ready application contract

目标：先建立框架无关的进度、取消、时间、provider、export 和 facade 契约。

任务：

1. TDD 新增 progress/cancellation ports 和 no-op 默认实现。
2. 把 CLI 时间解析迁移到共享 service，补充 DST、日期边界和 `since > until` 测试。
3. 从 CLI 提取 provider list/test 和 report export use case，并证明 CLI 输出不变。
4. 为 index/analyze/assess/series/resume 注入进度和取消安全点。
5. 为 `SqliteAnalysisStore` 增加 `cancel_run()` 和遗留 run 恢复。
6. 实现 request DTO、`GuiError` 和 `GuiApplicationFacade`。
7. 增加 facade parity 测试：同输入直接 use case 和 facade 结果相等。

交付物：

- 可在无 PySide6 环境运行的完整 GUI application contract。
- CLI 回归测试全部通过。
- 取消后无 RUNNING run 的数据库集成测试。

验收标准：

- [ ] application/domain 不导入 PySide6。
- [ ] 现有 CLI JSON fixture 和 E2E 生命周期无变化。
- [ ] 所有长任务至少报告 started、一个业务阶段和 completed。
- [ ] `since > until` 在启动任务前失败。
- [ ] 无偏移 GUI/CLI 时间都使用系统时区。

预计工作量：6-8 人日。

### 阶段 2：桌面壳、仓库生命周期和任务系统

目标：交付可日常打开仓库、诊断和同步的桌面应用壳。

任务：

1. 实现 QApplication、QML engine、资源定位、主题和本地日志。
2. 实现 task runner、同仓库 FIFO、跨仓库线程池和退出等待流程。
3. 实现 Application/Repository controller 和 recent repository settings。
4. 实现主窗口、导航、仓库页、任务抽屉、错误 banner 和空状态。
5. 接入 status/doctor/init/index/sync，并实现取消与刷新。
6. 增加 headless controller/model 测试和仓库生命周期集成测试。
7. 验证高 DPI、键盘导航、系统浅色/深色主题和窄窗口布局。

交付物：

- 可用的 repository lifecycle GUI。
- 后台任务系统和统一错误展示。
- 第一版 Windows/Linux/macOS 开发构建。

验收标准：

- [ ] index/sync 时窗口保持响应。
- [ ] 同仓库连续点击只产生一个运行任务，其余明确排队或禁用。
- [ ] 不同仓库任务可并行。
- [ ] 关闭窗口不会强制终止 SQLite 事务线程。
- [ ] 状态和 doctor 结果与 CLI 一致。

预计工作量：5-7 人日。

### 阶段 3：评估工作台 MVP

目标：交付完整评估、周期趋势、人员、工作项和 Evidence 浏览，这是首个可发布 MVP 边界。

任务：

1. 实现 Assessment controller、共享参数校验和系统时区日期时间输入。
2. 实现人员选择、全员排除、排名、branch/release/scope/delivery/time basis/period 筛选器。
3. 实现 Overview、Assessment、Trends、People、Work Items/Evidence 页面。
4. 实现 People/WorkItem/Evidence/PeriodTrend model 和虚拟化表格。
5. 使用 Qt Charts 展示趋势和分布；提供无 Charts 时的数据表降级。
6. 展示 warnings、limitations、PARTIAL 状态和 LLM fallback。
7. 增加 10,000 行 model 性能测试和 GUI/CLI assessment parity 集成测试。

交付物：

- 可从仓库选择到评估下钻的完整 MVP。
- 周、月、季度以及环比/同比趋势页。
- 与 CLI run JSON 一致性报告。

验收标准：

- [ ] 相同筛选条件下 GUI 与 CLI 产生相同 snapshot ID 和持久化 report。
- [ ] GUI 不计算工作量、难度、排名或趋势 delta。
- [ ] 周期拆分使用系统时区并正确处理 DST/跨年/季度边界。
- [ ] 10,000 行滚动和过滤满足性能目标。
- [ ] 取消周期评估不留下 RUNNING parent/child run。

预计工作量：8-12 人日。

### 阶段 4：历史、导出、身份、简历和 Provider

目标：补齐现有 CLI 的主要管理和输出能力。

任务：

1. 实现 run 列表、详情、base/target 选择、交换和 compare 页面。
2. 实现 JSON/Markdown/CSV 保存对话框、原子写入和覆盖确认。
3. 实现身份列表、映射、merge preview/确认、历史和撤销。
4. 实现 Resume 页面和候选项展示。
5. 实现 Provider 只读状态、环境变量是否存在和后台 health check。
6. 增加破坏性动作、导出失败、不可比较 run 和 provider timeout 测试。

交付物：

- CLI 主要业务能力的 GUI 覆盖。
- 安全的身份维护和报告导出流程。
- Provider/简历后台任务体验。

验收标准：

- [ ] compare 使用持久化历史，不重新运行评估。
- [ ] 导出结果逐字节匹配现有 renderer（平台换行规则除外）。
- [ ] merge/unmerge 全程使用现有事务和 workspace lock。
- [ ] GUI settings/log 不包含凭据值。
- [ ] provider timeout 不冻结 UI。

预计工作量：7-10 人日。

### 阶段 5：三平台发布、文档和发布门禁

目标：形成可重复构建、验证、签名预留和发布的正式 GUI 制品。

任务：

1. 完成 `gca-gui.spec`：QML、Qt plugins、Charts、图标、许可证和平台 bundle。
2. CI 新增 GUI lint/type/test/QML load job，release matrix 新增 GUI build/smoke/upload。
3. Windows 构建 GUI `.exe`；Linux 构建 standalone；macOS 构建并压缩 `.app`。
4. `verify_gui_standalone.py` 在临时中文路径仓库完成 open/init/sync/assess/auto-exit smoke。
5. 增加 SHA-256，预留 Windows 签名和 macOS codesign/notarization secret 步骤；无 secret 时明确跳过。
6. 更新中英文 README、架构、安装、隐私、release notes 和第三方许可证。
7. 执行最终代码审查、无障碍检查和三平台手动探索测试。

交付物：

- 三平台 GUI artifact 和不变的 CLI artifact。
- 自动化 smoke、checksum、许可证和安装文档。
- `0.4.0` 发布候选。

验收标准：

- [ ] core wheel 安装后只有 core 依赖，`gca` 正常工作。
- [ ] `[gui]` 安装和 standalone 均可启动 GUI。
- [ ] 三平台可完成最小仓库生命周期。
- [ ] 发布制品不包含 API key 或机器私有路径。
- [ ] 所有 CI、coverage、gitleaks 和 release readiness 门禁通过。

预计工作量：5-8 人日。

### 7.1 总体排期

| 里程碑 | 阶段 | 预计工作量 | 结果 |
|---|---|---:|---|
| 技术可行性 | 0 | 2-3 人日 | 三平台 Qt/PyInstaller 探针 |
| Core GUI-ready | 1 | 6-8 人日 | 可测试的应用层任务契约 |
| Repository GUI | 2 | 5-7 人日 | 可初始化、诊断、同步 |
| GUI MVP | 3 | 8-12 人日 | 可评估、看趋势和 Evidence |
| 功能完整 | 4 | 7-10 人日 | 历史、导出、身份、简历、Provider |
| Release Candidate | 5 | 5-8 人日 | 三平台正式制品 |

总计：33-48 人日。单人顺序实施约 7-10 周；MVP 到阶段 3 为 21-30 人日。阶段 0 是必须
完成的发布探针，不建议在未验证 Qt 打包前大规模编写 QML 页面。

## 8. 测试策略

### 8.1 单元测试

`tests/unit/test_progress.py`：

- `test_null_reporter_should_accept_events()`
- `test_progress_event_should_reject_invalid_counts()`
- `test_progress_stages_should_be_stable_identifiers()`

`tests/unit/test_cancellation.py`：

- `test_default_token_should_never_cancel()`
- `test_event_token_should_raise_after_request()`
- `test_cancel_should_be_idempotent()`

`tests/unit/test_gui_facade.py`：

- `test_assess_should_route_to_single_run_without_period()`
- `test_assess_should_route_to_series_with_period()`
- `test_assess_should_reject_reversed_time_range()`
- `test_facade_should_map_known_errors_without_traceback_leak()`
- `test_facade_should_not_change_report_payload()`

`tests/unit/test_gui_task_runner.py`：

- `test_same_repository_mutations_should_run_fifo()`
- `test_different_repositories_should_run_in_parallel()`
- `test_read_should_wait_for_same_repository_mutation()`
- `test_cancelled_queued_task_should_never_start()`
- `test_worker_signal_should_be_delivered_on_ui_thread()`

`tests/unit/test_gui_models.py`：

- role 名和列顺序稳定。
- reset/sort/filter 不修改输入 report。
- 空值、Unicode、长路径和 warnings 正确投影。
- 10,000 行不创建每行 QObject。

### 8.2 application/SQLite 集成测试

`tests/integration/test_gui_cancellation.py`：

- index 在写事务前取消，不修改现有 index。
- assess 在 `start_run` 后取消，run 状态为 `CANCELLED`。
- series 取消后 parent/child 都不保持 `RUNNING`。
- 进程中断模拟后，持锁恢复把遗留 run 标为 `FAILED`。

`tests/integration/test_gui_assessment_parity.py`：

- 单次和周期评估的 facade 结果与直接 use case 结果一致。
- 系统时区、显式 offset、DST、跨月、跨季度、跨年结果一致。
- authored/committed/merged/landed/released 五种口径一致。

`tests/integration/test_gui_export.py`：

- 三种格式与 `generate_report()` 输出一致。
- 不允许覆盖时返回 validation error。
- 临时文件写入失败不破坏已存在目标文件。
- `include_email=false` 是默认值。

### 8.3 QML 和 controller 测试

使用 Qt Quick Test 和 offscreen platform 验证：

- 主窗口在无仓库、未初始化、已初始化、任务运行、错误五种状态可加载。
- 侧栏导航和键盘焦点顺序正确。
- 评估表单的 period 与 since/until 联动校验。
- 运行任务时按钮不会导致重复 mutation。
- compare 必须选择两个不同 assessment run。
- 320 px 等效窄窗口和 1280/1440 桌面宽度下无控件重叠。

### 8.4 E2E 和发布验证

开发环境 E2E：

1. 创建中文和空格路径临时 Git 仓库。
2. 启动 GUI smoke mode，打开仓库。
3. init、sync、选择人员、执行 no-LLM assessment。
4. 验证 run 已持久化、页面 model 非空。
5. 自动关闭并确认退出码为 0。

standalone E2E 在 Windows/Linux/macOS release matrix 重复上述最小流程。真实 UI 手动验收还包括
文件选择器、系统主题、高 DPI、屏幕阅读器名称、深色模式和错误详情复制。

### 8.5 性能和资源测试

- 10,000 work items + 20,000 Evidence 的 model 构建与滚动基准。
- 12 个季度或 104 个周 period 的趋势加载基准。
- 运行 30 分钟 sync/assessment 观察 UI thread、内存和取消行为。
- 连续切换 20 个仓库后 controller/model 可释放，不持续增长。
- 用 PyInstaller analysis 报告检查无 WebEngine、无未使用 Qt 模块。

### 8.6 测试命令

```powershell
python -m pip install -e ".[dev,gui,release]"
python -m ruff check .
python -m mypy src
python -m pytest --cov=git_contribution_analyzer --cov-report=term-missing
$env:QT_QPA_PLATFORM = "offscreen"
python -m pytest tests/unit tests/integration tests/e2e/test_gui_smoke.py
pyinstaller --clean --noconfirm gca-gui.spec
python scripts/verify_gui_standalone.py
```

## 9. 风险和缓解

### 风险 1：PyInstaller 缺少 Qt plugin/QML module

- 概率：中；影响：高。
- 缓解：阶段 0 先做三平台探针；spec 显式收集 QML、QtQuick、Controls、Charts 和 platform plugins。
- 监测：release smoke 必须从干净 runner 启动制品，不能依赖系统 PySide6。

### 风险 2：UI 线程冻结或跨线程更新 model

- 概率：中；影响：高。
- 缓解：所有耗时 use case 只经 task runner；worker 只发 primitive signal；model 只在主线程更新。
- 监测：测试记录 signal thread，长任务期间增加事件循环心跳断言。

### 风险 3：取消破坏 SQLite 状态

- 概率：中；影响：高。
- 缓解：只在安全点抛取消；事务中不 terminate thread；取消 run 显式终态化。
- 监测：取消后执行 `doctor`、SQLite integrity check 和无 RUNNING run 断言。

### 风险 4：GUI 和 CLI 业务行为漂移

- 概率：中；影响：高。
- 缓解：GUI 只调用 facade/use case；抽取 CLI 内的时间/provider/export 逻辑；增加 parity golden tests。
- 监测：同仓库同参数比较 snapshot ID、run JSON 和 renderer output。

### 风险 5：Qt 包体和许可义务

- 概率：高；影响：中。
- 缓解：不引入 WebEngine；只打包用到模块；发布 notices；保留 PySide6 动态库和许可证要求。
- 监测：每次 release 记录包体和第三方组件清单。

### 风险 6：macOS notarization 和 Windows 签名缺失

- 概率：中；影响：中到高。
- 缓解：构建与签名步骤解耦，CI 预留 secret；未签名制品明确标识为 preview。
- 监测：正式发布清单必须记录签名/公证状态。

### 风险 7：系统时区和 DST 差异

- 概率：中；影响：高。
- 缓解：GUI/CLI 共用解析服务；报告持久化 offset；周期领域服务只消费 aware datetime。
- 监测：至少覆盖 Asia/Shanghai、UTC、America/New_York 三类时区测试。

### 风险 8：QML 大表格性能不足

- 概率：中；影响：中。
- 缓解：QAbstractTableModel、固定 delegate 尺寸、聚合图表输入、延迟详情加载。
- 监测：10,000/20,000 行基准作为 MVP 门禁。

## 10. 发布、回滚和运维

### 10.1 制品命名

建议 release 产物：

```text
gca-windows-x86_64.exe
gca-linux-x86_64
gca-macos-x86_64
gca-gui-windows-x86_64.exe
gca-gui-linux-x86_64
gca-gui-macos-x86_64.app.zip
SHA256SUMS.txt
```

### 10.2 发布前检查

- core wheel、sdist、CLI standalone 和 GUI standalone 全部通过 smoke。
- 三平台 GUI 显示正确版本，能处理中文路径，能打开一个真实临时仓库。
- `THIRD_PARTY_NOTICES.md` 与制品一起发布。
- gitleaks、私有邮箱和机器路径文档扫描通过。
- 发布说明区分 CLI core 和可选 GUI，不暗示自动更新能力。

### 10.3 回滚步骤

1. 停止分发有问题的 GUI artifact。
2. 保留或重新发布同版本 CLI artifact；GUI 故障不要求数据库回滚。
3. 使用 `git revert <gui-release-commit>` 回退入口/spec/workflow。
4. 若仅 QML 页面故障，修复后发布 patch 版本，不修改历史 tag。
5. 对取消/恢复逻辑缺陷，先禁用相关 GUI 操作并引导使用 CLI，再发 patch。

## 11. 已解决决策和实施前检查点

1. **GUI 技术选型**：已解决，使用 PySide6 + QML。
2. **时间口径**：已解决，GUI 无偏移时间使用系统时区，复用 CLI/application 共享解析服务。
3. **CLI 是否保留**：已解决，`gca` 与 `gca-gui` 独立入口和制品。
4. **是否引入 WebEngine**：已解决，第一版禁止。
5. **是否持久化 API key**：已解决，禁止；继续使用环境变量。
6. **是否新增数据库 migration**：已解决，不新增 DDL；状态值为兼容性扩展。
7. **签名和公证证书**：发布前检查点；若尚未提供，GUI 只能标识为 unsigned preview。
8. **应用图标和品牌资产**：阶段 2 前检查点；需要确定最终 bitmap/icon 资产和许可证。
9. **首发语言**：默认中英文文档，GUI 文案建议先以可翻译英文 key 实现，并至少提供简体中文翻译。

## 12. Definition of Done

- `gca-gui` 在 Windows、Linux、macOS 启动并完成最小仓库生命周期。
- GUI 覆盖仓库、评估、趋势、Evidence、run 对比、导出、身份、简历和 Provider 主要流程。
- GUI 和 CLI 相同参数产生相同 snapshot ID、持久化 run JSON 和报告。
- UI 长任务不冻结；取消不损坏 SQLite，不留下 RUNNING run。
- 日期时间使用系统时区，`since > until` 在任务启动前失败。
- core wheel 不依赖 PySide6，CLI 行为和 Schema 保持兼容。
- 三平台 CI、coverage、QML load、standalone smoke、gitleaks 和 release readiness 全部通过。
- 中英文安装、架构、隐私和发布文档，以及 Qt/Lucide 第三方许可证已更新。

## 13. 参考资料

- `doc/proposals/cross-platform-gui-proposals.md`
- `doc/architecture/architecture.md`
- `doc/architecture/data-model.md`
- `doc/testing/golden-dataset.md`
- `pyproject.toml`
- `gca.spec`
- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`
