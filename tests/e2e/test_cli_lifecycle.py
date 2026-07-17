from __future__ import annotations

import json
import tomllib
from pathlib import Path

from alembic import command
from jsonschema import validate
from sqlalchemy import create_engine, text
from typer.testing import CliRunner

from git_contribution_analyzer import __version__
from git_contribution_analyzer.adapters.storage.sqlite.database import _alembic_config
from git_contribution_analyzer.cli.app import app

runner = CliRunner()


def test_should_show_help_and_version() -> None:
    help_result = runner.invoke(app, ["--help"])
    version_result = runner.invoke(app, ["--version"])

    assert help_result.exit_code == 0
    assert "Git contribution analysis" in help_result.stdout
    assert version_result.exit_code == 0
    metadata = tomllib.loads(
        (Path(__file__).parents[2] / "pyproject.toml").read_text(encoding="utf-8")
    )
    lock = tomllib.loads(
        (Path(__file__).parents[2] / "uv.lock").read_text(encoding="utf-8")
    )
    locked_project = next(
        package for package in lock["package"] if package["name"] == "git-contribution-analyzer"
    )
    assert version_result.stdout.strip() == "0.5.1"
    assert metadata["project"]["version"] == "0.5.1"
    assert locked_project["version"] == "0.5.1"
    assert __version__ == "0.5.1"


def test_should_reject_init_when_path_is_not_repository(tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", str(tmp_path)])

    assert result.exit_code == 3
    assert "not a Git repository" in result.stdout


def test_should_initialize_status_and_uninitialize_repository(git_repo: Path) -> None:
    first_init = runner.invoke(app, ["init", str(git_repo)])
    second_init = runner.invoke(app, ["init", str(git_repo)])

    assert first_init.exit_code == 0
    assert second_init.exit_code == 0
    assert (git_repo / ".gca" / "config.yml").is_file()
    assert (git_repo / ".gca" / "meta.json").is_file()
    assert (git_repo / ".gca" / "index.sqlite").is_file()

    status = runner.invoke(app, ["status", str(git_repo), "--json"])
    assert status.exit_code == 0
    payload = json.loads(status.stdout)
    schema_path = Path(__file__).parents[2] / "schemas" / "status" / "v2.json"
    validate(payload, json.loads(schema_path.read_text(encoding="utf-8")))
    assert payload["schemaVersion"] == "2.0"
    assert payload["command"] == "status"
    assert payload["success"] is True
    assert payload["data"]["repository"] == str(git_repo.resolve())
    assert payload["data"]["workspaceInitialized"] is True
    assert payload["data"]["indexedCommits"] == 0
    assert payload["data"]["indexStatus"] == "up-to-date"

    engine = create_engine(f"sqlite:///{(git_repo / '.gca' / 'index.sqlite').as_posix()}")
    with engine.connect() as connection:
        repository_count = connection.execute(
            text("SELECT COUNT(*) FROM repositories")
        ).scalar_one()
    engine.dispose()
    assert repository_count == 1

    uninit = runner.invoke(app, ["uninit", str(git_repo), "--yes"])
    assert uninit.exit_code == 0
    assert not (git_repo / ".gca").exists()
    exclude = (git_repo / ".git" / "info" / "exclude").read_text(encoding="utf-8")
    assert ".gca/" not in exclude.splitlines()


def test_should_report_doctor_findings_for_initialized_repository(git_repo: Path) -> None:
    init_result = runner.invoke(app, ["init", str(git_repo)])
    assert init_result.exit_code == 0

    doctor = runner.invoke(app, ["doctor", str(git_repo), "--json"])

    assert doctor.exit_code == 0
    payload = json.loads(doctor.stdout)
    assert payload["success"] is True
    assert payload["data"]["healthy"] is True
    assert {check["name"] for check in payload["data"]["checks"]} >= {
        "git",
        "workspace",
        "database",
        "lock",
    }


def test_status_and_doctor_should_migrate_an_existing_workspace(git_repo: Path) -> None:
    assert runner.invoke(app, ["init", str(git_repo)]).exit_code == 0
    database = git_repo / ".gca" / "index.sqlite"
    command.downgrade(_alembic_config(database), "0006_identity_merges")

    status = runner.invoke(app, ["status", str(git_repo), "--json"])
    doctor = runner.invoke(app, ["doctor", str(git_repo), "--json"])

    assert status.exit_code == 0
    assert json.loads(status.stdout)["data"]["databaseHealthy"] is True
    assert doctor.exit_code == 0
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    with engine.connect() as connection:
        revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
    engine.dispose()
    assert revision == "0007_structural_baselines"


def test_should_list_and_test_mock_provider(git_repo: Path) -> None:
    assert runner.invoke(app, ["init", str(git_repo)]).exit_code == 0

    listed = runner.invoke(app, ["providers", "list", str(git_repo), "--json"])
    tested = runner.invoke(app, ["providers", "test", str(git_repo), "--json"])

    assert listed.exit_code == 0
    assert {item["id"] for item in json.loads(listed.stdout)["data"]["providers"]} == {
        "mock",
        "openai-compatible",
        "anthropic",
        "ollama",
        "codex-cli",
        "claude-cli",
    }
    assert tested.exit_code == 0
    assert json.loads(tested.stdout)["data"] == {
        "healthy": True,
        "localExecution": True,
        "model": "deterministic",
        "provider": "mock",
    }


def test_should_return_workspace_error_when_doctor_runs_before_init(git_repo: Path) -> None:
    doctor = runner.invoke(app, ["doctor", str(git_repo), "--json"])

    assert doctor.exit_code == 4
    payload = json.loads(doctor.stdout)
    assert payload["success"] is False
    assert payload["data"]["healthy"] is False
