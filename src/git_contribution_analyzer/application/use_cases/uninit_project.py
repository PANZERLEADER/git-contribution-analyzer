from __future__ import annotations

import shutil
from pathlib import Path

from git_contribution_analyzer.adapters.git.repository_discovery import discover_repository
from git_contribution_analyzer.adapters.workspace.git_exclude import remove_workspace_exclusion
from git_contribution_analyzer.adapters.workspace.layout import WorkspaceLayout
from git_contribution_analyzer.domain.errors import WorkspaceError


def uninit_project(path: Path) -> bool:
    repository = discover_repository(path)
    layout = WorkspaceLayout.for_repository(repository.root)
    if layout.root.parent != repository.root or layout.root.name != ".gca":
        raise WorkspaceError(f"Refusing to delete unsafe workspace path: {layout.root}")
    if layout.root.is_symlink():
        raise WorkspaceError(f"Refusing to delete symlink workspace: {layout.root}")
    existed = layout.root.exists()
    if existed:
        shutil.rmtree(layout.root)
    remove_workspace_exclusion(repository.root)
    return existed
