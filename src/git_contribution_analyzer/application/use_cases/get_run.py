from __future__ import annotations

from pathlib import Path
from typing import Any

from git_contribution_analyzer.adapters.git.repository_discovery import discover_repository
from git_contribution_analyzer.adapters.storage.sqlite.analysis import SqliteAnalysisStore
from git_contribution_analyzer.adapters.storage.sqlite.database import initialize_database
from git_contribution_analyzer.adapters.workspace.layout import WorkspaceLayout


def get_run(path: Path, run_id: str) -> dict[str, Any]:
    repository = discover_repository(path)
    layout = WorkspaceLayout.for_repository(repository.root)
    initialize_database(layout.database)
    return SqliteAnalysisStore(layout.database, str(repository.root)).get_report(run_id)
