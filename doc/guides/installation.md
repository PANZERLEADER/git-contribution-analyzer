# Installation, Upgrade And Removal

[简体中文](../zh-CN/installation.md)

## Prerequisites

- Git available on `PATH`.
- Python 3.12 or 3.13 for wheel/pipx installations.
- Read access to the repository being analyzed.

## Development Installation

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\gca.exe --help
```

On Linux/macOS, use `.venv/bin/python` and `.venv/bin/gca`.

For the optional desktop application:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev,gui]"
.\.venv\Scripts\gca-gui.exe
```

The ordinary core wheel does not install Qt. Use the `[gui]` extra or a `gca-gui-*` release
artifact when a desktop interface is required.

## Wheel Or pipx

```powershell
python -m build
python -m pip install dist/git_contribution_analyzer-0.5.0-py3-none-any.whl
pipx install dist/git_contribution_analyzer-0.5.0-py3-none-any.whl
gca --version
```

Release CI validates the wheel in a fresh virtual environment before publishing artifacts.

## Standalone Artifact

Download the artifact matching the operating system, place `gca` or `gca.exe` on `PATH`, then run:

```powershell
gca --help
gca doctor D:\path\to\repository --json
```

The Windows executable does not require a PowerShell script execution policy exception.

GUI release artifacts are named `gca-gui-windows-x86_64.exe`, `gca-gui-linux-x86_64` and
`gca-gui-macos-x86_64.app.zip`. The macOS archive contains an application bundle.

## Upgrade

1. Back up `.gca/index.sqlite` when retaining manual identity/run history matters.
2. Upgrade the wheel, pipx package or standalone binary.
3. Run `gca status <repo> --json`; opening the workspace applies additive migrations.
4. Run `gca doctor <repo> --json` and `gca sync <repo> --json`.

Historical runs remain immutable. New rule versions create new runs.

## Removal

```powershell
gca uninit D:\path\to\repository --yes
pipx uninstall git-contribution-analyzer
python -m pip uninstall git-contribution-analyzer
```

`uninit` deletes only `.gca` and its `.git/info/exclude` entry. It does not alter commits, refs or
working-tree files.
