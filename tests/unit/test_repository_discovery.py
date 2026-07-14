from __future__ import annotations

from pathlib import Path

import pytest

from git_contribution_analyzer.adapters.git.repository_discovery import discover_repository
from git_contribution_analyzer.domain.errors import NotARepositoryError


def test_should_discover_repository_when_path_is_git_root(git_repo: Path) -> None:
    discovered = discover_repository(git_repo)

    assert discovered.root == git_repo.resolve()
    assert discovered.git_dir == (git_repo / ".git").resolve()


def test_should_discover_repository_when_path_is_nested(git_repo: Path) -> None:
    nested = git_repo / "src" / "module"
    nested.mkdir(parents=True)

    discovered = discover_repository(nested)

    assert discovered.root == git_repo.resolve()


def test_should_raise_when_path_is_not_git_repository(tmp_path: Path) -> None:
    with pytest.raises(NotARepositoryError):
        discover_repository(tmp_path)
