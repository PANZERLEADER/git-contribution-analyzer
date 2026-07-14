from __future__ import annotations

from pathlib import Path

WORKSPACE_EXCLUDE = ".gca/"


def _exclude_path(repository_root: Path) -> Path:
    return repository_root.resolve() / ".git" / "info" / "exclude"


def ensure_workspace_excluded(repository_root: Path) -> None:
    path = _exclude_path(repository_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    if WORKSPACE_EXCLUDE not in lines:
        lines.append(WORKSPACE_EXCLUDE)
    content = "\n".join(lines)
    path.write_text(f"{content}\n" if content else "", encoding="utf-8", newline="\n")


def remove_workspace_exclusion(repository_root: Path) -> None:
    path = _exclude_path(repository_root)
    if not path.exists():
        return
    lines = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line != WORKSPACE_EXCLUDE
    ]
    content = "\n".join(lines)
    path.write_text(f"{content}\n" if content else "", encoding="utf-8", newline="\n")
