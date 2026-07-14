from __future__ import annotations

from pathlib import Path
from typing import Any

from git_contribution_analyzer.adapters.git.repository_discovery import discover_repository
from git_contribution_analyzer.adapters.storage.sqlite.git_index import SqliteGitIndexStore
from git_contribution_analyzer.adapters.workspace.layout import WorkspaceLayout


def list_identities(path: Path, *, unresolved_only: bool = False) -> dict[str, Any]:
    repository = discover_repository(path)
    layout = WorkspaceLayout.for_repository(repository.root)
    store = SqliteGitIndexStore(layout.database, str(repository.root))
    persons = store.list_identities(unresolved_only=unresolved_only)
    return {"persons": persons, "count": len(persons)}
