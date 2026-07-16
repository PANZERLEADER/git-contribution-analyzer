from __future__ import annotations

from pathlib import Path

from git_contribution_analyzer.adapters.storage.sqlite.structural_baseline import (
    SqliteStructuralBaselineStore,
)
from git_contribution_analyzer.application.ports.structural_baseline import (
    StructuralBaselineStore,
)


def test_sqlite_structural_store_should_implement_application_port() -> None:
    store = SqliteStructuralBaselineStore(Path("unused.sqlite"), "unused")

    assert isinstance(store, StructuralBaselineStore)
