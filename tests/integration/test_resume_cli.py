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


def _repo(tmp_path: Path, *, confirmed: bool) -> Path:
    repo = tmp_path / ("resume-confirmed" if confirmed else "resume-unconfirmed")
    builder = GitRepoBuilder.create(repo)
    builder.commit_text(
        "api/user.py",
        "USER = True\n",
        "feat(user): implement user API",
        name="Alice",
        email="alice@example.com",
    )
    assert runner.invoke(app, ["init", str(repo)]).exit_code == 0
    if confirmed:
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


def test_should_generate_conservative_resume_without_llm(tmp_path: Path) -> None:
    repo = _repo(tmp_path, confirmed=True)

    result = runner.invoke(
        app,
        [
            "resume",
            str(repo),
            "--person",
            "alice@example.com",
            "--target-role",
            "Backend Engineer",
            "--language",
            "en-US",
            "--style",
            "concise",
            "--no-llm",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.stdout
    report = json.loads(result.stdout)["data"]
    schema = json.loads(
        (Path(__file__).parents[2] / "schemas/resume/v1.json").read_text(encoding="utf-8")
    )
    validate(report, schema)
    assert report["reportType"] == "RESUME"
    assert report["person"] == {"id": report["person"]["id"], "name": "Alice"}
    assert report["experienceBullets"]
    assert all(claim["contributionItemIds"] for claim in report["experienceBullets"])
    assert all(claim["evidenceIds"] for claim in report["experienceBullets"])
    assert {entry["id"] for entry in report["evidence"]} >= {
        evidence_id
        for claim in report["experienceBullets"]
        for evidence_id in claim["evidenceIds"]
    }
    assert "alice@example.com" not in result.stdout

    run_id = report["run"]["id"]
    markdown = runner.invoke(
        app, ["report", str(repo), "--run", run_id, "--format", "markdown"]
    )
    shown = runner.invoke(app, ["runs", "show", run_id, str(repo)])
    assert "Resume Draft" in markdown.stdout
    assert "Resume candidates" in shown.stdout


def test_should_reject_resume_for_unconfirmed_person(tmp_path: Path) -> None:
    repo = _repo(tmp_path, confirmed=False)

    result = runner.invoke(
        app,
        ["resume", str(repo), "--person", "alice@example.com", "--no-llm"],
    )

    assert result.exit_code == 5
    assert "not confirmed" in result.stdout


def test_should_generate_resume_with_mock_provider_and_independent_prompt(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path, confirmed=True)
    config_path = repo / ".gca" / "config.yml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["llm"].update({"enabled": True, "provider": "mock"})
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    result = runner.invoke(
        app,
        ["resume", str(repo), "--person", "alice@example.com", "--json"],
    )

    assert result.exit_code == 0, result.stdout
    report = json.loads(result.stdout)["data"]
    assert report["run"]["providerId"] == "mock"
    assert report["run"]["promptVersion"] == "resume-v1"
    assert report["experienceBullets"]


def test_should_fallback_to_template_when_resume_provider_times_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path, confirmed=True)
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
        app, ["resume", str(repo), "--person", "alice@example.com", "--json"]
    )

    assert result.exit_code == 0, result.stdout
    report = json.loads(result.stdout)["data"]
    assert report["run"]["status"] == "PARTIAL"
    assert report["experienceBullets"]
    assert "TIMEOUT" in report["warnings"][0]


def test_should_skip_resume_provider_when_no_eligible_evidence(tmp_path: Path) -> None:
    repo = _repo(tmp_path, confirmed=True)
    config_path = repo / ".gca" / "config.yml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["llm"].update({"enabled": True, "provider": "mock"})
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "resume",
            str(repo),
            "--person",
            "alice@example.com",
            "--since",
            "2030-01-01",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.stdout
    report = json.loads(result.stdout)["data"]
    assert report["experienceBullets"] == []
    assert "no eligible Evidence" in report["warnings"][0]


def test_should_reject_invalid_resume_language(tmp_path: Path) -> None:
    repo = _repo(tmp_path, confirmed=True)

    result = runner.invoke(
        app,
        [
            "resume",
            str(repo),
            "--person",
            "alice@example.com",
            "--language",
            "fr-FR",
            "--no-llm",
        ],
    )

    assert result.exit_code == 4
    assert "Unsupported resume language" in result.stdout
