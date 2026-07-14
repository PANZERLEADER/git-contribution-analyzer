from __future__ import annotations

from pathlib import Path

from git_contribution_analyzer.adapters.workspace.git_exclude import (
    ensure_workspace_excluded,
    remove_workspace_exclusion,
)


def test_should_add_workspace_exclusion_idempotently(git_repo: Path) -> None:
    ensure_workspace_excluded(git_repo)
    ensure_workspace_excluded(git_repo)

    exclude = (git_repo / ".git" / "info" / "exclude").read_text(encoding="utf-8")
    assert exclude.splitlines().count(".gca/") == 1


def test_should_remove_only_workspace_exclusion(git_repo: Path) -> None:
    exclude_path = git_repo / ".git" / "info" / "exclude"
    exclude_path.parent.mkdir(parents=True, exist_ok=True)
    exclude_path.write_text("custom-entry\n.gca/\n", encoding="utf-8")

    remove_workspace_exclusion(git_repo)

    assert exclude_path.read_text(encoding="utf-8") == "custom-entry\n"
