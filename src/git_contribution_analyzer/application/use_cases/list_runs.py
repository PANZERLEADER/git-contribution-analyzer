from __future__ import annotations

from pathlib import Path
from typing import Any

from git_contribution_analyzer.adapters.git.repository_discovery import discover_repository
from git_contribution_analyzer.adapters.storage.sqlite.analysis import SqliteAnalysisStore
from git_contribution_analyzer.adapters.storage.sqlite.database import initialize_database
from git_contribution_analyzer.adapters.workspace.layout import WorkspaceLayout


def list_runs(path: Path) -> dict[str, Any]:
    repository = discover_repository(path)
    layout = WorkspaceLayout.for_repository(repository.root)
    initialize_database(layout.database)
    runs = SqliteAnalysisStore(layout.database, str(repository.root)).list_runs()
    return {"runs": runs, "count": len(runs)}
