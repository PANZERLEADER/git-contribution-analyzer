from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from git_contribution_analyzer.adapters.storage.sqlite.analysis import SqliteAnalysisStore
from git_contribution_analyzer.adapters.workspace.layout import WorkspaceLayout
from git_contribution_analyzer.application.use_cases.init_project import init_project
from git_contribution_analyzer.domain.models.run import RunType
from tests.helpers.git_repo_builder import GitRepoBuilder


def test_store_should_terminalize_cancelled_run(tmp_path: Path) -> None:
    repository = tmp_path / "cancelled-run"
    builder = GitRepoBuilder.create(repository)
    builder.commit_text("README.md", "cancel\n", "docs: cancel fixture")
    init_project(repository)
    layout = WorkspaceLayout.for_repository(repository)
    store = SqliteAnalysisStore(layout.database, str(repository.resolve()))
    now = datetime(2026, 7, 15, tzinfo=UTC)
    store.start_run(
        run_id="cancel-me",
        person_id=None,
        parameters={},
        baseline_commit=store.baseline_commit(),
        started_at=now,
        run_type=RunType.WORK_ASSESSMENT,
    )

    store.cancel_run("cancel-me", now)

    run = next(item for item in store.list_runs() if item["id"] == "cancel-me")
    assert run["status"] == "CANCELLED"


def test_store_should_recover_running_runs_as_failed(tmp_path: Path) -> None:
    repository = tmp_path / "interrupted-run"
    builder = GitRepoBuilder.create(repository)
    builder.commit_text("README.md", "interrupt\n", "docs: interrupt fixture")
    init_project(repository)
    layout = WorkspaceLayout.for_repository(repository)
    store = SqliteAnalysisStore(layout.database, str(repository.resolve()))
    now = datetime(2026, 7, 15, tzinfo=UTC)
    store.start_run(
        run_id="interrupted",
        person_id=None,
        parameters={},
        baseline_commit=store.baseline_commit(),
        started_at=now,
        run_type=RunType.WORK_ASSESSMENT,
    )

    count = store.fail_running_runs(now, "Interrupted before completion")

    run = next(item for item in store.list_runs() if item["id"] == "interrupted")
    assert count == 1
    assert run["status"] == "FAILED"
