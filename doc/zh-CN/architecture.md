# GCA 架构

[中文文档索引](README.md) | [English](../architecture/architecture.md)

## 目标

GCA 是一个以 CLI 为入口、在本地运行的 Git 分析工具。确定性 Git 事实和带版本的规则是唯一
事实来源。LLM Provider 可以改善表达，但不能替换 Evidence、修改工作规模或难度，也不能突破
简历 claim strength 的确定性上限。

## 分层

```text
CLI / PySide6-QML GUI
  -> Application 用例
      -> Domain 模型和确定性规则
          -> Application Ports
              -> Git、SQLite、LLM、Outcome 和 Reporting Adapters
```

- `domain`：不可变模型，以及贡献、工作量、难度和 claim 的确定性规则。
- `application`：用例、EvidenceSnapshot、Provider task 和与仓库实现无关的 ports。
- `adapters`：Native Git/PyDriller、SQLite、LLM Provider、YAML outcome 和报告渲染器。
- `cli`：Typer 命令、带版本输出 envelope 和稳定退出码映射。
- `adapters/gui`：Qt controller、table model、按仓库调度的后台任务和 QML 资源。GUI 调用
  application facade，不解析 CLI 输出，也不直接查询 SQLite。

依赖方向必须向内。Domain 代码不能依赖 CLI、SQLite、HTTP 或命令行 Provider。
Application 和 Domain 不能依赖 PySide6。GUI 与 CLI 共用系统时区时间边界校验、Provider use case、
报告 renderer 和持久化 run 契约。

## 桌面任务边界

GUI 会串行执行同一仓库的任务，不同仓库可以使用 Qt 线程池并行。Application progress event 通过
Qt signal 跨越 Adapter 边界。取消是协作式的，只在事务安全点生效；Qt worker thread 不会被强制
终止。仓库本地 `workspace_lock` 仍是 CLI 和 GUI 进程的最终写入保护。

## 分析流水线

```text
init/index/sync -> Git index -> 身份规范化
                              -> EvidenceSnapshot
                                  -> analyze
                                  -> assess -> 可选工作评估解释
                                  -> resume -> 可选简历措辞生成
```

`EvidenceSnapshot` 使用规范 JSON 进行内容寻址。相同 Git 基线、过滤条件、身份范围和规则版本
应生成相同 Snapshot ID。Provider 只接收由 Snapshot 派生的、经过脱敏和白名单约束的上下文，
不会直接读取仓库。

## 结构信号

分析流程通过纯 Domain 服务从 Snapshot 提交事实中推导 `structural-signals-v1`。该服务计算重复文件
共同变更边和结构热点，不直接读取 Git 或 SQLite。个人和项目报告会持久化信号及其支持提交哈希，
但 LLM 上下文、工作量、难度和排名输入保持不变。

## 扩展点

- 实现 `LlmProvider` 并注册到 Provider registry，可增加新的 LLM 接入。
- 使用新的规则版本增加确定性信号，不能改写历史运行结果。
- 在 reporting adapter 边界后增加新的报告格式。
- 未来复杂度/影响分析器通过 application port 接入；Adapter 不可用时必须显式输出 gap。

## 故障边界

- Git 或索引失败会回滚 SQLite 事务。
- Provider 失败时，根据配置生成保留确定性输出的 `PARTIAL` run，或明确失败。
- 报告从持久化 run JSON 重建，不会静默重新分析仓库。
- `.gca/` 是仓库本地状态，只写入 `.git/info/exclude`，不会提交到项目历史。
