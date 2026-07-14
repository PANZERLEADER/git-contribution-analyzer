from __future__ import annotations

import subprocess
from pathlib import Path

from git_contribution_analyzer.domain.errors import NotARepositoryError
from git_contribution_analyzer.domain.models.repository import DiscoveredRepository


def _run_git(path: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), *arguments],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise NotARepositoryError(f"{path} is not a Git repository") from exc
    return result.stdout.strip()


def discover_repository(path: Path) -> DiscoveredRepository:
    candidate = path.expanduser().resolve()
    if not candidate.exists() or not candidate.is_dir():
        raise NotARepositoryError(f"{candidate} is not a Git repository")

    root = Path(_run_git(candidate, "rev-parse", "--show-toplevel")).resolve()
    raw_git_dir = Path(_run_git(candidate, "rev-parse", "--git-dir"))
    git_dir = raw_git_dir if raw_git_dir.is_absolute() else (candidate / raw_git_dir)
    return DiscoveredRepository(root=root, git_dir=git_dir.resolve())


def detect_current_branch(repository: DiscoveredRepository) -> str:
    for preferred in ("main", "master"):
        result = subprocess.run(
            [
                "git",
                "-C",
                str(repository.root),
                "show-ref",
                "--verify",
                "--quiet",
                f"refs/heads/{preferred}",
            ],
            check=False,
            capture_output=True,
            timeout=5,
        )
        if result.returncode == 0:
            return preferred
    try:
        branch = _run_git(repository.root, "symbolic-ref", "--quiet", "--short", "HEAD")
    except NotARepositoryError:
        return "main"
    return branch or "main"


def git_version() -> str:
    try:
        result = subprocess.run(
            ["git", "--version"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise NotARepositoryError("Git executable is not available") from exc
    return result.stdout.strip()
