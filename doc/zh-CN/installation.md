# 安装、升级与卸载

[中文文档索引](README.md) | [English](../guides/installation.md)

## 前置条件

- `PATH` 中可以执行 Git。
- 使用 wheel 或 pipx 安装时，需要 Python 3.12 或 3.13。
- 对被分析仓库拥有读取权限。

## 开发安装

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\gca.exe --help
```

Linux/macOS 使用 `.venv/bin/python` 和 `.venv/bin/gca`。

## Wheel 或 pipx

```powershell
python -m build
python -m pip install dist/git_contribution_analyzer-0.2.0-py3-none-any.whl
pipx install dist/git_contribution_analyzer-0.2.0-py3-none-any.whl
gca --version
```

Release CI 会在发布制品前，在全新虚拟环境中验证 wheel 生命周期。

## Standalone 制品

从 GitHub Release 下载对应操作系统的文件：

- Windows：`gca-windows-x86_64.exe`
- Linux：`gca-linux-x86_64`
- macOS：`gca-macos-x86_64`

将文件重命名为 `gca` 或 `gca.exe` 并放入 `PATH`，然后运行：

```powershell
gca --help
gca doctor D:\path\to\repository --json
```

Windows 可执行文件不需要放宽 PowerShell 脚本执行策略。

## 升级

1. 如需保留人工身份映射和历史 run，先备份 `.gca/index.sqlite`。
2. 升级 wheel、pipx package 或 standalone 文件。
3. 运行 `gca status <repo> --json`；打开工作区时会应用增量迁移。
4. 运行 `gca doctor <repo> --json` 和 `gca sync <repo> --json`。

历史 run 保持不可变。新规则版本会创建新的 run。

## 卸载

```powershell
gca uninit D:\path\to\repository --yes
pipx uninstall git-contribution-analyzer
python -m pip uninstall git-contribution-analyzer
```

`uninit` 只删除 `.gca` 及其 `.git/info/exclude` 条目，不会修改 commit、ref 或工作区文件。
