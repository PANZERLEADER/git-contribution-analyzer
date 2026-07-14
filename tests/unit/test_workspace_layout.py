from __future__ import annotations

from pathlib import Path

from git_contribution_analyzer.adapters.workspace.layout import WorkspaceLayout


def test_should_build_all_workspace_paths_from_repository_root(tmp_path: Path) -> None:
    layout = WorkspaceLayout.for_repository(tmp_path)

    assert layout.root == tmp_path / ".gca"
    assert layout.config == layout.root / "config.yml"
    assert layout.metadata == layout.root / "meta.json"
    assert layout.database == layout.root / "index.sqlite"
    assert layout.identities == layout.root / "identities.yml"
    assert layout.cache == layout.root / "cache"
    assert layout.runs == layout.root / "runs"
    assert layout.reports == layout.root / "reports"
    assert layout.locks == layout.root / "locks"
