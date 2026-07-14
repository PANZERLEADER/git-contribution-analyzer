from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from jsonschema import validate
from typer.testing import CliRunner

from git_contribution_analyzer.adapters.llm.mock import MockLlmProvider
from git_contribution_analyzer.cli.app import app
from git_contribution_analyzer.domain.errors import LlmTimeoutError
from tests.helpers.git_repo_builder import GitRepoBuilder

runner = CliRunner()


def _initialized_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "assessment"
    builder = GitRepoBuilder.create(repo)
    builder.commit_text(
        "api/UserController.py",
        "USER = True\n",
        "feat(user): add user PROJ-1",
        name="Alice",
        email="alice@example.com",
    )
    builder.commit_text(
        "tests/test_user.py",
        "def test_user(): pass\n",
        "test(user): cover user PROJ-1",
        name="Alice",
        email="alice@example.com",
    )
    builder.commit_text(
        "service/bob.py",
        "BOB = True\n",
        "feat: bob",
        name="Bob",
        email="bob@example.com",
    )
    assert runner.invoke(app, ["init", str(repo)]).exit_code == 0
    mapped = runner.invoke(
        app,
        [
            "identities",
            "map",
            str(repo),
            "--name",
            "Alice",
            "--email",
            "alice@example.com",
            "--person-name",
            "Alice",
            "--person-email",
            "alice@example.com",
        ],
    )
    assert mapped.exit_code == 0
    return repo


def test_should_assess_person_and_replay_markdown(tmp_path: Path) -> None:
    repo = _initialized_repo(tmp_path)

    result = runner.invoke(
        app,
        ["assess", str(repo), "--person", "alice@example.com", "--no-llm", "--json"],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    report = payload["data"]
    schema = json.loads(
        (Path(__file__).parents[2] / "schemas/work-assessment/v2.json").read_text(
            encoding="utf-8"
        )
    )
    validate(report, schema)
    assert report["schemaVersion"] == "2.0"
    assert report["reportType"] == "WORK_ASSESSMENT"
    assert report["scopeType"] == "PERSON"
    assert report["run"]["runType"] == "WORK_ASSESSMENT"
    assert report["workloadSummary"]["completedItems"] >= 1
    assert report["technicalSummary"]["headline"]
    assert report["businessSummary"]["headline"]
    assert report["selection"]["includedPersonIds"] == [
        report["subjects"][0]["person"]["id"]
    ]
    assert report["ranking"] == {
        "enabled": False,
        "ruleVersion": None,
        "cohortFingerprint": None,
        "dimensions": [],
        "composite": None,
        "config": None,
    }

    run_id = report["run"]["id"]
    runs = runner.invoke(app, ["runs", "list", str(repo), "--json"])
    markdown = runner.invoke(
        app, ["report", str(repo), "--run", run_id, "--format", "markdown"]
    )

    assert json.loads(runs.stdout)["data"]["runs"][0]["runType"] == "WORK_ASSESSMENT"
    assert "Work Assessment" in markdown.stdout
    assert "Technical Summary" in markdown.stdout
    assert "Business Summary" in markdown.stdout


def test_should_assess_all_with_ranking_disabled(tmp_path: Path) -> None:
    repo = _initialized_repo(tmp_path)

    result = runner.invoke(
        app, ["assess", str(repo), "--all", "--no-llm", "--json"]
    )

    assert result.exit_code == 0, result.stdout
    report = json.loads(result.stdout)["data"]
    assert report["scopeType"] == "PROJECT"
    assert len(report["subjects"]) == 1
    assert report["identityWarnings"] == []
    assert report["selection"]["exclusions"][0]["reason"] == "UNCONFIRMED"
    assert report["ranking"]["enabled"] is False
    assert report["ranking"]["dimensions"] == []
    assert "score" not in json.dumps(report).casefold()


def test_should_add_optional_assessment_explanation_with_mock_provider(
    tmp_path: Path,
) -> None:
    repo = _initialized_repo(tmp_path)
    config_path = repo / ".gca" / "config.yml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["llm"].update({"enabled": True, "provider": "mock"})
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    result = runner.invoke(
        app, ["assess", str(repo), "--person", "alice@example.com", "--json"]
    )

    assert result.exit_code == 0, result.stdout
    report = json.loads(result.stdout)["data"]
    assert report["run"]["providerId"] == "mock"
    assert report["run"]["promptVersion"] == "assessment-explanation-v1"
    assert report["explanation"]["overallExplanation"]


def test_should_retain_deterministic_assessment_when_provider_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _initialized_repo(tmp_path)
    config_path = repo / ".gca" / "config.yml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["llm"].update(
        {"enabled": True, "provider": "mock", "allowFallbackToRules": True}
    )
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    def timeout(_provider: MockLlmProvider, _task: object) -> object:
        raise LlmTimeoutError()

    monkeypatch.setattr(MockLlmProvider, "complete", timeout)
    result = runner.invoke(
        app, ["assess", str(repo), "--person", "alice@example.com", "--json"]
    )

    assert result.exit_code == 0, result.stdout
    report = json.loads(result.stdout)["data"]
    assert report["run"]["status"] == "PARTIAL"
    assert report["workloadSummary"]["completedItems"] >= 1
    assert report["explanation"] is None
    assert "TIMEOUT" in report["warnings"][0]
