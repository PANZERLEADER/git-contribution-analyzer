# Installation, Upgrade And Removal

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

## Wheel Or pipx

```powershell
python -m build
python -m pip install dist/git_contribution_analyzer-0.1.0-py3-none-any.whl
pipx install dist/git_contribution_analyzer-0.1.0-py3-none-any.whl
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
