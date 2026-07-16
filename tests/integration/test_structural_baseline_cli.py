from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import jsonschema
import pytest
import yaml
from alembic import command
from sqlalchemy import create_engine, text
from sqlalchemy import inspect as inspect_database
from typer.testing import CliRunner

from git_contribution_analyzer.adapters.storage.sqlite.database import (
    _alembic_config,
    initialize_database,
)
from git_contribution_analyzer.adapters.storage.sqlite.structural_baseline import (
    SqliteStructuralBaselineStore,
)
from git_contribution_analyzer.application.ports.cancellation import (
    CancellationSource,
    CancellationToken,
    OperationCancelled,
)
from git_contribution_analyzer.application.use_cases.manage_structural_baselines import (
    get_structural_status,
    rebuild_structural_baseline,
    show_structural_baseline,
)
from git_contribution_analyzer.cli.app import app
from git_contribution_analyzer.domain.errors import WorkspaceError
from tests.helpers.git_repo_builder import GitRepoBuilder

runner = CliRunner()
ROOT = Path(__file__).parents[2]


def _database(repo: Path):  # type: ignore[no-untyped-def]
    return create_engine(f"sqlite:///{(repo / '.gca' / 'index.sqlite').as_posix()}")


def _commit_pair(builder: GitRepoBuilder, suffix: str) -> str:
    first = builder.root / "src" / "a.py"
    second = builder.root / "db" / "b.sql"
    first.parent.mkdir(parents=True, exist_ok=True)
    second.parent.mkdir(parents=True, exist_ok=True)
    first.write_text(f"a = '{suffix}'\n", encoding="utf-8")
    second.write_text(f"-- {suffix}\n", encoding="utf-8")
    builder.run("add", "src/a.py", "db/b.sql")
    return builder._commit(f"feat: pair {suffix}")


def _use_test_structural_thresholds(repo: Path) -> None:
    path = repo / ".gca" / "config.yml"
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    config["structural"].update(
        {
            "minimumBaselineCommits": 2,
            "minimumCoChangeCount": 2,
            "minimumSubsetRatio": 0.75,
            "minimumJaccard": 0.2,
            "minimumHubPenalty": 0.0,
        }
    )
    path.write_text(
        yaml.safe_dump(config, sort_keys=False),
        encoding="utf-8",
        newline="\n",
    )


def test_should_rebuild_show_and_report_structural_status(tmp_path: Path) -> None:
    repo = tmp_path / "structural"
    builder = GitRepoBuilder.create(repo)
    _commit_pair(builder, "one")
    _commit_pair(builder, "two")
    _commit_pair(builder, "three")
    assert runner.invoke(app, ["init", str(repo)]).exit_code == 0
    _use_test_structural_thresholds(repo)

    rebuild = runner.invoke(
        app,
        [
            "structural",
            "rebuild",
            str(repo),
            "--cutoff",
            "2027-01-01T00:00:00Z",
            "--json",
        ],
    )

    assert rebuild.exit_code == 0, rebuild.stdout
    rebuilt = json.loads(rebuild.stdout)["data"]
    jsonschema.validate(
        rebuilt,
        json.loads((ROOT / "schemas" / "structural-baseline" / "v1.json").read_text()),
        format_checker=jsonschema.FormatChecker(),
    )
    assert rebuilt["status"] == "COMPLETED"
    assert rebuilt["timeStrategy"] == "DUAL_WINDOW"
    assert rebuilt["configuration"] == {
        "minimumBaselineCommits": 2,
        "hotspotPercentile": 0.95,
        "minimumCoChangeCount": 2,
        "minimumSubsetRatio": 0.75,
        "minimumJaccard": 0.2,
        "minimumHubPenalty": 0.0,
        "maximumContextPaths": 100,
        "rollingWindowDays": 365,
    }
    assert rebuilt["summary"]["eligibleCommits"] == 3
    assert rebuilt["summary"]["rawEdges"] == 1
    assert rebuilt["materialization"]["couplings"][0]["crossModule"] is True

    status = runner.invoke(app, ["structural", "status", str(repo), "--json"])
    assert status.exit_code == 0
    status_data = json.loads(status.stdout)["data"]
    assert status_data["baselineCount"] == 1
    assert status_data["latestBaselineId"] == rebuilt["baselineId"]
    jsonschema.validate(
        json.loads(status.stdout),
        json.loads(
            (ROOT / "schemas" / "commands" / "structural-status-v1.json").read_text()
        ),
    )

    repository_status = runner.invoke(app, ["status", str(repo), "--json"])
    assert repository_status.exit_code == 0
    assert json.loads(repository_status.stdout)["data"]["structural"]["baselineCount"] == 1
    jsonschema.validate(
        json.loads(repository_status.stdout),
        json.loads((ROOT / "schemas" / "status" / "v2.json").read_text()),
    )

    doctor = runner.invoke(app, ["doctor", str(repo), "--json"])
    assert doctor.exit_code == 0
    checks = json.loads(doctor.stdout)["data"]["checks"]
    assert next(check for check in checks if check["name"] == "structural")["healthy"] is True

    show = runner.invoke(
        app,
        [
            "structural",
            "show",
            str(repo),
            "--baseline",
            rebuilt["baselineId"],
            "--json",
        ],
    )
    assert show.exit_code == 0
    assert json.loads(show.stdout)["data"] == rebuilt


def test_should_accumulate_low_frequency_edge_after_sync(tmp_path: Path) -> None:
    repo = tmp_path / "incremental"
    builder = GitRepoBuilder.create(repo)
    _commit_pair(builder, "one")
    assert runner.invoke(app, ["init", str(repo)]).exit_code == 0
    _use_test_structural_thresholds(repo)
    first = runner.invoke(
        app,
        ["structural", "rebuild", str(repo), "--cutoff", "2027-01-01", "--json"],
    )
    assert first.exit_code == 0
    assert json.loads(first.stdout)["data"]["materialization"]["couplings"] == []

    _commit_pair(builder, "two")
    _commit_pair(builder, "three")
    sync = runner.invoke(app, ["sync", str(repo), "--json"])
    assert sync.exit_code == 0
    second = runner.invoke(
        app,
        ["structural", "rebuild", str(repo), "--cutoff", "2027-01-01", "--json"],
    )

    assert second.exit_code == 0
    result = json.loads(second.stdout)["data"]
    assert result["materialization"]["couplings"][0]["coChangeCount"] == 3

    engine = _database(repo)
    with engine.connect() as connection:
        occurrence_count = connection.execute(
            text("SELECT COUNT(*) FROM structural_edge_occurrences")
        ).scalar_one()
    engine.dispose()
    assert occurrence_count == 3


def test_should_prune_rebuildable_baselines(tmp_path: Path) -> None:
    repo = tmp_path / "prune"
    builder = GitRepoBuilder.create(repo)
    _commit_pair(builder, "one")
    assert runner.invoke(app, ["init", str(repo)]).exit_code == 0
    for cutoff in ("2026-01-02", "2026-01-03", "2027-01-01"):
        result = runner.invoke(
            app,
            ["structural", "rebuild", str(repo), "--cutoff", cutoff, "--json"],
        )
        assert result.exit_code == 0

    prune = runner.invoke(
        app,
        ["structural", "prune", str(repo), "--keep", "1", "--yes", "--json"],
    )

    assert prune.exit_code == 0
    assert json.loads(prune.stdout)["data"]["deletedBaselines"] == 2
    jsonschema.validate(
        json.loads(prune.stdout),
        json.loads(
            (ROOT / "schemas" / "commands" / "structural-prune-v1.json").read_text()
        ),
    )


def test_should_not_publish_cancelled_structural_baseline(tmp_path: Path) -> None:
    repo = tmp_path / "cancelled"
    builder = GitRepoBuilder.create(repo)
    _commit_pair(builder, "one")
    assert runner.invoke(app, ["init", str(repo)]).exit_code == 0
    source = CancellationSource()
    source.cancel()

    with pytest.raises(OperationCancelled):
        rebuild_structural_baseline(
            repo,
            cutoff=datetime(2027, 1, 1, tzinfo=UTC),
            cancellation=source.token,
        )

    assert get_structural_status(repo)["baselineCount"] == 0


class _CancelAfterBuildStarts(CancellationToken):
    def __init__(self) -> None:
        self.calls = 0

    @property
    def cancellation_requested(self) -> bool:
        return self.calls >= 3

    def raise_if_cancelled(self) -> None:
        self.calls += 1
        if self.cancellation_requested:
            raise OperationCancelled("Operation cancelled")


def test_should_record_cancelled_baseline_after_build_starts(tmp_path: Path) -> None:
    repo = tmp_path / "cancelled-diagnostic"
    builder = GitRepoBuilder.create(repo)
    _commit_pair(builder, "one")
    assert runner.invoke(app, ["init", str(repo)]).exit_code == 0

    with pytest.raises(OperationCancelled, match="diagnostic"):
        rebuild_structural_baseline(
            repo,
            cutoff=datetime(2027, 1, 1, tzinfo=UTC),
            cancellation=_CancelAfterBuildStarts(),
        )

    engine = _database(repo)
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT id, status, error_message FROM structural_baselines")
        ).one()
    engine.dispose()
    assert row.status == "CANCELLED"
    assert row.error_message == "OperationCancelled"
    assert len(row.id) == 64
    with pytest.raises(WorkspaceError, match="not found"):
        show_structural_baseline(repo, row.id)


def test_should_record_failed_baseline_with_diagnostic_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "failed-diagnostic"
    builder = GitRepoBuilder.create(repo)
    _commit_pair(builder, "one")
    assert runner.invoke(app, ["init", str(repo)]).exit_code == 0

    def fail_load(*args: object, **kwargs: object) -> object:
        raise RuntimeError("simulated structural failure")

    monkeypatch.setattr(SqliteStructuralBaselineStore, "load_commits", fail_load)

    with pytest.raises(WorkspaceError, match="diagnostic"):
        rebuild_structural_baseline(repo, cutoff=datetime(2027, 1, 1, tzinfo=UTC))

    engine = _database(repo)
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT id, status, error_message FROM structural_baselines")
        ).one()
    engine.dispose()
    assert row.status == "FAILED"
    assert row.error_message == "RuntimeError"
    assert get_structural_status(repo)["failedBaselines"] == 1
    with pytest.raises(WorkspaceError, match="not found"):
        show_structural_baseline(repo, row.id)


def test_sync_should_mark_unreachable_completed_baseline_stale(tmp_path: Path) -> None:
    repo = tmp_path / "mark-stale"
    builder = GitRepoBuilder.create(repo)
    first_commit = _commit_pair(builder, "one")
    _commit_pair(builder, "two")
    assert runner.invoke(app, ["init", str(repo)]).exit_code == 0
    assert runner.invoke(
        app,
        ["structural", "rebuild", str(repo), "--cutoff", "2027-01-01"],
    ).exit_code == 0

    builder.reset_hard(first_commit)
    assert runner.invoke(app, ["sync", str(repo)]).exit_code == 0

    engine = _database(repo)
    with engine.connect() as connection:
        status = connection.execute(text("SELECT status FROM structural_baselines")).scalar_one()
    engine.dispose()
    assert status == "STALE"

    doctor = runner.invoke(app, ["doctor", str(repo), "--json"])
    assert doctor.exit_code == 4
    structural = next(
        check
        for check in json.loads(doctor.stdout)["data"]["checks"]
        if check["name"] == "structural"
    )
    assert "1 stale" in structural["detail"]


def test_incremental_baseline_should_equal_full_rebuild(tmp_path: Path) -> None:
    repo = tmp_path / "incremental-equivalence"
    builder = GitRepoBuilder.create(repo)
    _commit_pair(builder, "one")
    _commit_pair(builder, "two")
    assert runner.invoke(app, ["init", str(repo)]).exit_code == 0
    _use_test_structural_thresholds(repo)

    _commit_pair(builder, "three")
    _commit_pair(builder, "four")
    assert runner.invoke(app, ["sync", str(repo)]).exit_code == 0
    incremental = rebuild_structural_baseline(
        repo,
        cutoff=datetime(2027, 1, 1, tzinfo=UTC),
    )

    assert runner.invoke(app, ["index", str(repo)]).exit_code == 0
    rebuilt = rebuild_structural_baseline(
        repo,
        cutoff=datetime(2027, 1, 1, tzinfo=UTC),
    )

    assert rebuilt["baselineId"] == incremental["baselineId"]
    assert rebuilt["summary"] == incremental["summary"]
    assert rebuilt["materialization"] == incremental["materialization"]


def test_default_branch_change_should_not_reuse_previous_baseline(tmp_path: Path) -> None:
    repo = tmp_path / "default-branch-baseline"
    builder = GitRepoBuilder.create(repo)
    _commit_pair(builder, "main")
    assert runner.invoke(app, ["init", str(repo)]).exit_code == 0
    main = rebuild_structural_baseline(
        repo,
        cutoff=datetime(2027, 1, 1, tzinfo=UTC),
    )

    builder.checkout("dev", create=True)
    _commit_pair(builder, "dev")
    config_path = repo / ".gca" / "config.yml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(
            "defaultBranch: main",
            "defaultBranch: dev",
        ),
        encoding="utf-8",
    )
    assert runner.invoke(app, ["sync", str(repo)]).exit_code == 0

    dev = rebuild_structural_baseline(
        repo,
        cutoff=datetime(2027, 1, 1, tzinfo=UTC),
    )

    assert main["branch"] == "refs/heads/main"
    assert dev["branch"] == "refs/heads/dev"
    assert dev["baselineId"] != main["baselineId"]


def test_should_use_completed_baseline_without_loading_facts_again(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "warm"
    builder = GitRepoBuilder.create(repo)
    _commit_pair(builder, "one")
    assert runner.invoke(app, ["init", str(repo)]).exit_code == 0
    cutoff = datetime(2027, 1, 1, tzinfo=UTC)
    first = rebuild_structural_baseline(repo, cutoff=cutoff)

    def fail_load(*args: object, **kwargs: object) -> object:
        raise AssertionError("warm cache hit must not load structural commit facts")

    monkeypatch.setattr(SqliteStructuralBaselineStore, "load_commits", fail_load)

    second = rebuild_structural_baseline(repo, cutoff=cutoff)

    assert second == first


def test_doctor_should_reject_completed_baseline_without_materialization(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "orphan"
    builder = GitRepoBuilder.create(repo)
    _commit_pair(builder, "one")
    assert runner.invoke(app, ["init", str(repo)]).exit_code == 0
    assert runner.invoke(
        app,
        ["structural", "rebuild", str(repo), "--cutoff", "2027-01-01"],
    ).exit_code == 0
    engine = _database(repo)
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM structural_materializations"))
    engine.dispose()

    doctor = runner.invoke(app, ["doctor", str(repo), "--json"])

    assert doctor.exit_code == 4
    structural = next(
        check
        for check in json.loads(doctor.stdout)["data"]["checks"]
        if check["name"] == "structural"
    )
    assert structural["healthy"] is False
    assert "orphan" in structural["detail"]


def test_doctor_should_report_baseline_made_stale_by_force_push(tmp_path: Path) -> None:
    repo = tmp_path / "stale"
    builder = GitRepoBuilder.create(repo)
    first_commit = _commit_pair(builder, "one")
    _commit_pair(builder, "two")
    assert runner.invoke(app, ["init", str(repo)]).exit_code == 0
    assert runner.invoke(
        app,
        ["structural", "rebuild", str(repo), "--cutoff", "2027-01-01"],
    ).exit_code == 0
    builder.reset_hard(first_commit)

    doctor = runner.invoke(app, ["doctor", str(repo), "--json"])

    assert doctor.exit_code == 4
    structural = next(
        check
        for check in json.loads(doctor.stdout)["data"]["checks"]
        if check["name"] == "structural"
    )
    assert structural["healthy"] is False
    assert "1 stale" in structural["detail"]


def test_structural_migration_should_downgrade_and_upgrade_cleanly(tmp_path: Path) -> None:
    database = tmp_path / "migration.sqlite"
    initialize_database(database)

    command.downgrade(_alembic_config(database), "0006_identity_merges")
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    downgraded_tables = set(inspect_database(engine).get_table_names())
    engine.dispose()
    assert "analysis_runs" in downgraded_tables
    assert "structural_baselines" not in downgraded_tables

    command.upgrade(_alembic_config(database), "head")
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    upgraded_tables = set(inspect_database(engine).get_table_names())
    engine.dispose()
    assert {
        "structural_commit_facts",
        "structural_file_occurrences",
        "structural_edge_occurrences",
        "structural_baselines",
        "structural_file_counts",
        "structural_edge_counts",
        "structural_materializations",
    } <= upgraded_tables
