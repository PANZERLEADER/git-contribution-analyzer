from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from sqlalchemy import inspect

from git_contribution_analyzer.adapters.git.repository_discovery import discover_repository
from git_contribution_analyzer.adapters.storage.sqlite.analysis import SqliteAnalysisStore
from git_contribution_analyzer.adapters.storage.sqlite.database import (
    _alembic_config,
    create_database_engine,
    initialize_database,
    upsert_repository,
)
from git_contribution_analyzer.domain.errors import ReportError
from git_contribution_analyzer.domain.models.run import RunType
from tests.helpers.git_repo_builder import GitRepoBuilder


def _store(tmp_path: Path) -> tuple[SqliteAnalysisStore, Path]:
    repo = tmp_path / "run-types"
    builder = GitRepoBuilder.create(repo)
    builder.commit_text("README.md", "test\n", "docs: initial")
    database = repo / ".gca" / "index.sqlite"
    initialize_database(database)
    discovered = discover_repository(repo)
    upsert_repository(database, discovered, "main")
    return SqliteAnalysisStore(database, str(repo.resolve())), database


def test_should_migrate_analysis_runs_with_run_type_columns(tmp_path: Path) -> None:
    _store_instance, database = _store(tmp_path)
    engine = create_database_engine(database)
    try:
        columns = {entry["name"] for entry in inspect(engine).get_columns("analysis_runs")}
    finally:
        engine.dispose()

    assert {"run_type", "parent_run_id"} <= columns


def test_should_persist_run_type_and_parent_run_id(tmp_path: Path) -> None:
    store, _database = _store(tmp_path)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    store.start_run(
        run_id="parent",
        person_id=None,
        parameters={},
        baseline_commit=None,
        started_at=now,
        run_type=RunType.ANALYSIS,
    )
    store.complete_run(
        run_id="parent",
        completed_at=now,
        report={"schemaVersion": "1.0", "reportType": "PROJECT"},
        persist_details=False,
    )
    store.start_run(
        run_id="child",
        person_id=None,
        parameters={},
        baseline_commit=None,
        started_at=now,
        run_type=RunType.WORK_ASSESSMENT,
        parent_run_id="parent",
    )

    runs = {entry["id"]: entry for entry in store.list_runs()}

    assert runs["parent"]["runType"] == "ANALYSIS"
    assert runs["child"]["runType"] == "WORK_ASSESSMENT"
    assert runs["child"]["parentRunId"] == "parent"


def test_should_reject_missing_parent_run(tmp_path: Path) -> None:
    store, _database = _store(tmp_path)

    try:
        store.start_run(
            run_id="child",
            person_id=None,
            parameters={},
            baseline_commit=None,
            started_at=datetime(2026, 1, 1, tzinfo=UTC),
            run_type=RunType.RESUME,
            parent_run_id="missing",
        )
    except ReportError as exc:
        assert "parent" in str(exc).lower()
    else:
        raise AssertionError("missing parent run must be rejected")


def test_should_upgrade_and_downgrade_run_type_migration(tmp_path: Path) -> None:
    _store_instance, database = _store(tmp_path)

    command.downgrade(_alembic_config(database), "0004_llm_audit")
    engine = create_database_engine(database)
    try:
        downgraded = {
            entry["name"] for entry in inspect(engine).get_columns("analysis_runs")
        }
    finally:
        engine.dispose()
    assert "run_type" not in downgraded
    assert "parent_run_id" not in downgraded

    command.upgrade(_alembic_config(database), "head")
    engine = create_database_engine(database)
    try:
        upgraded = {entry["name"] for entry in inspect(engine).get_columns("analysis_runs")}
    finally:
        engine.dispose()
    assert {"run_type", "parent_run_id"} <= upgraded
