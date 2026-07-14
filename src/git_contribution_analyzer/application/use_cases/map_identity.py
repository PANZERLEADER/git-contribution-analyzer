from __future__ import annotations

from pathlib import Path
from typing import Any

from git_contribution_analyzer.adapters.git.repository_discovery import discover_repository
from git_contribution_analyzer.adapters.storage.sqlite.git_index import SqliteGitIndexStore
from git_contribution_analyzer.adapters.workspace.layout import WorkspaceLayout


def map_identity(
    path: Path,
    *,
    name: str,
    email: str,
    person_name: str,
    person_email: str,
) -> dict[str, Any]:
    repository = discover_repository(path)
    layout = WorkspaceLayout.for_repository(repository.root)
    store = SqliteGitIndexStore(layout.database, str(repository.root))
    person = store.map_identity(
        name=name,
        email=email,
        person_name=person_name,
        person_email=person_email,
    )
    return {"person": person}
