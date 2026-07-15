# Contributing

Thank you for contributing to Git Contribution Analyzer (GCA).

## Before You Start

- Search existing issues and pull requests before opening a new one.
- Use an issue for changes that affect CLI contracts, report schemas, ranking rules, privacy
  boundaries, or release packaging.
- Do not submit proprietary repositories, credentials, personal email addresses, private reports,
  `.gca` workspaces, or generated SQLite databases.
- Report vulnerabilities through GitHub private vulnerability reporting, not a public issue.

## Development Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,gui,release]"
```

On Linux and macOS, use the corresponding `.venv/bin/python` executable.

## Validation

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy src
$env:QT_QPA_PLATFORM = "offscreen"
$env:QT_QUICK_BACKEND = "software"
.\.venv\Scripts\python.exe -m pytest --cov=git_contribution_analyzer --cov-report=term-missing
```

Packaging changes must also verify the wheel and affected standalone artifacts.

## Pull Requests

- Keep changes focused and include tests for changed behavior.
- Preserve CLI exit codes, JSON schemas, privacy defaults, and persisted report compatibility unless
  a documented, versioned contract explicitly changes them.
- Update English and Simplified Chinese documentation for user-facing behavior.
- Use clear commit messages. Contributions are licensed under this project's Apache License 2.0.
