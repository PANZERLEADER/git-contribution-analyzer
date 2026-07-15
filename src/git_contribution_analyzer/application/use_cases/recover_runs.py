from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from git_contribution_analyzer.adapters.git.repository_discovery import discover_repository
from git_contribution_analyzer.adapters.storage.sqlite.analysis import SqliteAnalysisStore
from git_contribution_analyzer.adapters.storage.sqlite.database import initialize_database
from git_contribution_analyzer.adapters.workspace.layout import WorkspaceLayout
from git_contribution_analyzer.adapters.workspace.locks import workspace_lock


def recover_interrupted_runs(path: Path) -> int:
    repository = discover_repository(path)
    layout = WorkspaceLayout.for_repository(repository.root)
    initialize_database(layout.database)
    store = SqliteAnalysisStore(layout.database, str(repository.root))
    with workspace_lock(layout.locks / "workspace.lock"):
        return store.fail_running_runs(
            datetime.now(UTC),
            "Interrupted before completion",
        )
