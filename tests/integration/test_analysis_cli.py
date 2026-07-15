from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from jsonschema import validate
from sqlalchemy import create_engine, text
from typer.testing import CliRunner

from git_contribution_analyzer.adapters.llm.mock import MockLlmProvider
from git_contribution_analyzer.adapters.storage.sqlite.analysis import SqliteAnalysisStore
from git_contribution_analyzer.application.use_cases.analyze_contributions import (
    analyze_contributions,
)
from git_contribution_analyzer.cli.app import app
from git_contribution_analyzer.domain.errors import LlmTimeoutError
from tests.helpers.git_repo_builder import GitRepoBuilder

runner = CliRunner()


def _initialize_confirmed_alice(repo: Path) -> None:
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


def _enable_mock_llm(repo: Path, *, allow_fallback: bool) -> None:
    config_path = repo / ".gca" / "config.yml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["llm"].update(
        {
            "enabled": True,
            "provider": "mock",
            "model": "deterministic",
            "allowFallbackToRules": allow_fallback,
        }
    )
    config_path.write_text(
        yaml.safe_dump(config, sort_keys=False), encoding="utf-8", newline="\n"
    )


def test_should_reject_analysis_for_unconfirmed_identity(tmp_path: Path) -> None:
    repo = tmp_path / "unconfirmed"
    builder = GitRepoBuilder.create(repo)
    builder.commit_text(
        "api/user.py",
        "USER = True\n",
        "feat(api): add user",
        name="Alice",
        email="alice@example.com",
    )
    assert runner.invoke(app, ["init", str(repo)]).exit_code == 0

    result = runner.invoke(
        app,
        ["analyze", str(repo), "--person", "alice@example.com", "--no-llm", "--json"],
    )

    assert result.exit_code == 5
    assert "not confirmed" in result.stdout


def test_should_analyze_replay_and_render_reports_without_llm(tmp_path: Path) -> None:
    repo = tmp_path / "analysis"
    builder = GitRepoBuilder.create(repo)
    first = builder.commit_text(
        "api/UserController.java",
        "class UserController {}\n",
        "feat(api): add user endpoint PROJ-42",
        name="Alice",
        email="alice@example.com",
    )
    second = builder.commit_text(
        "tests/UserControllerTest.java",
        "class UserControllerTest {}\n",
        "test(api): cover user endpoint PROJ-42",
        name="Alice Dev",
        email="alice@example.com",
    )
    builder.commit_text(
        "service/BobService.java",
        "class BobService {}\n",
        "feat(service): unrelated work",
        name="Bob",
        email="bob@example.com",
    )
    builder.tag("v1.0.0")
    builder.checkout("feature/docs", create=True)
    third = builder.commit_text(
        "docs/users.md",
        "# Users\n",
        "docs: document users",
        name="Alice",
        email="alice@example.com",
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

    analyzed = runner.invoke(
        app,
        ["analyze", str(repo), "--person", "alice@example.com", "--no-llm", "--json"],
    )

    assert analyzed.exit_code == 0, analyzed.stdout
    analyzed_payload = json.loads(analyzed.stdout)
    schema_root = Path(__file__).parents[2] / "schemas"
    validate(
        analyzed_payload,
        json.loads((schema_root / "analysis" / "v1.json").read_text(encoding="utf-8")),
    )
    report = analyzed_payload["data"]
    validate(
        report,
        json.loads((schema_root / "report" / "v1.json").read_text(encoding="utf-8")),
    )
    assert report["schemaVersion"] == "1.0"
    assert report["run"]["status"] == "COMPLETED"
    assert report["person"]["email"] == "alice@example.com"
    assert report["summary"]["commits"] == 3
    reported_commits = {
        commit_hash
        for item in report["contributionItems"]
        for commit_hash in item["commitHashes"]
    }
    assert reported_commits == {
        first,
        second,
        third,
    }
    evidence_ids = {entry["id"] for entry in report["evidence"]}
    assert evidence_ids
    assert all(set(item["evidenceIds"]) <= evidence_ids for item in report["contributionItems"])
    assert report["technicalSummary"]["dominantModules"]
    assert report["businessSummary"]["domains"]
    assert report["structuralSignals"]["ruleVersion"] == "structural-signals-v1"
    assert report["structuralSignals"]["summary"]["analyzedCommits"] == 3
    assert report["structuralSignals"]["limitations"]
    dimension_claims = [
        *report["technicalSummary"]["highlights"],
        *report["businessSummary"]["highlights"],
    ]
    assert all(set(claim["evidenceIds"]) <= evidence_ids for claim in dimension_claims)

    run_id = report["run"]["id"]
    runs = runner.invoke(app, ["runs", "list", str(repo), "--json"])
    shown = runner.invoke(app, ["runs", "show", run_id, str(repo), "--json"])
    json_report = runner.invoke(
        app, ["report", str(repo), "--run", run_id, "--format", "json"]
    )
    markdown_report = runner.invoke(
        app, ["report", str(repo), "--run", run_id, "--format", "markdown"]
    )

    runs_payload = json.loads(runs.stdout)["data"]
    assert runs_payload["count"] == 1
    assert runs_payload["runs"][0]["startedAt"].endswith("+00:00")
    assert runs_payload["runs"][0]["completedAt"].endswith("+00:00")
    assert json.loads(shown.stdout)["data"] == report
    assert json.loads(json_report.stdout) == report
    assert "## Contribution Items" in markdown_report.stdout
    assert "## Structural Signals" in markdown_report.stdout
    assert "Evidence" in markdown_report.stdout
    assert "does not prove business outcome or sole ownership" in markdown_report.stdout

    scoped = runner.invoke(
        app,
        [
            "analyze",
            str(repo),
            "--person",
            "alice@example.com",
            "--scope",
            "api/",
            "--no-llm",
            "--json",
        ],
    )
    assert scoped.exit_code == 0
    assert json.loads(scoped.stdout)["data"]["summary"]["commits"] == 1


def test_should_apply_date_branch_release_and_delivery_filters(tmp_path: Path) -> None:
    repo = tmp_path / "filters"
    builder = GitRepoBuilder.create(repo)
    first = builder.commit_text(
        "api/first.py",
        "FIRST = True\n",
        "feat(api): first",
        name="Alice",
        email="alice@example.com",
    )
    builder.tag("v1.0.0")
    second = builder.commit_text(
        "api/second.py",
        "SECOND = True\n",
        "fix(api): second",
        name="Alice",
        email="alice@example.com",
    )
    builder.checkout("feature/unmerged", create=True)
    builder.commit_text(
        "api/third.py",
        "THIRD = True\n",
        "feat(api): third",
        name="Alice",
        email="alice@example.com",
    )
    runner.invoke(app, ["init", str(repo)])
    runner.invoke(
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

    def analyze(*arguments: str) -> dict:  # type: ignore[type-arg]
        result = runner.invoke(
            app,
            [
                "analyze",
                str(repo),
                "--person",
                "alice@example.com",
                "--no-llm",
                "--json",
                *arguments,
            ],
        )
        assert result.exit_code == 0, result.stdout
        return dict(json.loads(result.stdout)["data"])

    released = analyze("--release", "v1.0.0")
    landed = analyze("--delivery", "LANDED")
    main = analyze("--branch", "main")
    dated = analyze(
        "--since",
        "2026-01-01T12:00:30+00:00",
        "--until",
        "2026-01-01T12:01:30+00:00",
    )

    assert released["summary"]["commits"] == 1
    assert released["contributionItems"][0]["commitHashes"] == [first]
    assert landed["summary"]["commits"] == 1
    assert landed["contributionItems"][0]["commitHashes"] == [second]
    assert main["summary"]["commits"] == 2
    assert dated["summary"]["commits"] == 1
    assert dated["contributionItems"][0]["commitHashes"] == [second]


def test_should_enhance_analysis_with_mock_provider_and_persist_audit(tmp_path: Path) -> None:
    repo = tmp_path / "llm-success"
    builder = GitRepoBuilder.create(repo)
    builder.commit_text(
        "api/app.py",
        "APP = True\n",
        "feat(api): add app",
        name="Alice",
        email="alice@example.com",
    )
    _initialize_confirmed_alice(repo)
    _enable_mock_llm(repo, allow_fallback=True)

    result = runner.invoke(
        app, ["analyze", str(repo), "--person", "alice@example.com", "--json"]
    )

    assert result.exit_code == 0, result.stdout
    report = json.loads(result.stdout)["data"]
    assert report["run"]["status"] == "COMPLETED"
    assert report["run"]["providerId"] == "mock"
    assert report["run"]["promptVersion"] == "semantic-v1"
    assert report["semantic"]["overallSummary"][0]["evidenceIds"] == ["EV-001"]
    engine = create_engine(f"sqlite:///{(repo / '.gca' / 'index.sqlite').as_posix()}")
    try:
        with engine.connect() as connection:
            invocation = connection.execute(
                text(
                    "SELECT provider_id, status, prompt_version, schema_version "
                    "FROM llm_invocations"
                )
            ).mappings().one()
    finally:
        engine.dispose()
    assert dict(invocation) == {
        "provider_id": "mock",
        "status": "COMPLETED",
        "prompt_version": "semantic-v1",
        "schema_version": "semantic-v1",
    }


def test_should_partial_or_fail_when_provider_times_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "llm-timeout"
    builder = GitRepoBuilder.create(repo)
    builder.commit_text(
        "api/app.py",
        "APP = True\n",
        "feat(api): add app",
        name="Alice",
        email="alice@example.com",
    )
    _initialize_confirmed_alice(repo)

    def timeout(_provider: MockLlmProvider, _task: object) -> object:
        raise LlmTimeoutError()

    monkeypatch.setattr(MockLlmProvider, "complete", timeout)
    _enable_mock_llm(repo, allow_fallback=True)
    partial = runner.invoke(
        app, ["analyze", str(repo), "--person", "alice@example.com", "--json"]
    )

    assert partial.exit_code == 0, partial.stdout
    partial_payload = json.loads(partial.stdout)
    assert partial_payload["data"]["run"]["status"] == "PARTIAL"
    assert partial_payload["data"]["semantic"] is None
    assert "TIMEOUT" in partial_payload["warnings"][0]

    _enable_mock_llm(repo, allow_fallback=False)
    failed = runner.invoke(
        app, ["analyze", str(repo), "--person", "alice@example.com"]
    )
    runs = runner.invoke(app, ["runs", "list", str(repo), "--json"])

    assert failed.exit_code == 6
    assert "timed out" in failed.stdout
    statuses = [run["status"] for run in json.loads(runs.stdout)["data"]["runs"]]
    assert statuses == ["FAILED", "PARTIAL"]


def test_should_skip_llm_without_invocation_when_no_evidence(tmp_path: Path) -> None:
    repo = tmp_path / "llm-no-evidence"
    builder = GitRepoBuilder.create(repo)
    builder.commit_text(
        "api/app.py",
        "APP = True\n",
        "feat(api): add app",
        name="Alice",
        email="alice@example.com",
    )
    _initialize_confirmed_alice(repo)
    _enable_mock_llm(repo, allow_fallback=True)

    result = runner.invoke(
        app,
        [
            "analyze",
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
    assert report["run"]["status"] == "COMPLETED"
    assert report["semantic"] is None
    assert report["warnings"] == ["LLM semantic enhancement skipped: no Evidence available."]
    engine = create_engine(f"sqlite:///{(repo / '.gca' / 'index.sqlite').as_posix()}")
    try:
        with engine.connect() as connection:
            invocation_count = connection.execute(
                text("SELECT COUNT(*) FROM llm_invocations")
            ).scalar_one()
    finally:
        engine.dispose()
    assert invocation_count == 0


def test_should_reject_ambiguous_confirmed_person_name(tmp_path: Path) -> None:
    repo = tmp_path / "ambiguous"
    builder = GitRepoBuilder.create(repo)
    builder.commit_text(
        "one.txt", "one\n", "feat: one", name="Alias One", email="one@example.com"
    )
    builder.commit_text(
        "two.txt", "two\n", "feat: two", name="Alias Two", email="two@example.com"
    )
    runner.invoke(app, ["init", str(repo)])
    for alias_name, alias_email in (
        ("Alias One", "one@example.com"),
        ("Alias Two", "two@example.com"),
    ):
        mapped = runner.invoke(
            app,
            [
                "identities",
                "map",
                str(repo),
                "--name",
                alias_name,
                "--email",
                alias_email,
                "--person-name",
                "Engineer",
                "--person-email",
                alias_email,
            ],
        )
        assert mapped.exit_code == 0

    result = runner.invoke(
        app, ["analyze", str(repo), "--person", "Engineer", "--no-llm", "--json"]
    )

    assert result.exit_code == 5
    assert "exactly one identity" in result.stdout


def test_should_persist_failed_run_and_release_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "failed-run"
    builder = GitRepoBuilder.create(repo)
    builder.commit_text(
        "app.py", "APP = True\n", "feat: app", name="Alice", email="alice@example.com"
    )
    runner.invoke(app, ["init", str(repo)])
    runner.invoke(
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

    def fail_load(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("simulated analysis failure")

    monkeypatch.setattr(SqliteAnalysisStore, "load_commits", fail_load)
    failed = runner.invoke(
        app, ["analyze", str(repo), "--person", "alice@example.com", "--no-llm"]
    )
    runs = runner.invoke(app, ["runs", "list", str(repo), "--json"])

    assert failed.exit_code == 1
    payload = json.loads(runs.stdout)["data"]
    assert payload["count"] == 1
    assert payload["runs"][0]["status"] == "FAILED"
    assert payload["runs"][0]["error"] == "simulated analysis failure"


def test_should_produce_identical_json_with_fixed_clock_and_id(tmp_path: Path) -> None:
    repo = tmp_path / "deterministic"
    builder = GitRepoBuilder.create(repo)
    builder.commit_text(
        "api/app.py",
        "APP = True\n",
        "feat(api): deterministic PROJ-9",
        name="Alice",
        email="alice@example.com",
    )
    runner.invoke(app, ["init", str(repo)])
    runner.invoke(
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
    fixed_time = datetime(2026, 2, 1, tzinfo=UTC)
    fixed_id = "00000000-0000-0000-0000-000000000003"

    first = analyze_contributions(
        repo,
        person_selector="alice@example.com",
        clock=lambda: fixed_time,
        id_generator=lambda: fixed_id,
    )
    second = analyze_contributions(
        repo,
        person_selector="alice@example.com",
        clock=lambda: fixed_time,
        id_generator=lambda: fixed_id,
    )

    def canonical(value: object) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"))

    assert canonical(first) == canonical(second)


def test_should_record_completion_time_after_llm_finishes(tmp_path: Path) -> None:
    repo = tmp_path / "llm-completion-time"
    builder = GitRepoBuilder.create(repo)
    builder.commit_text(
        "api/app.py",
        "APP = True\n",
        "feat(api): add app",
        name="Alice",
        email="alice@example.com",
    )
    _initialize_confirmed_alice(repo)
    started = datetime(2026, 2, 1, tzinfo=UTC)
    completed = datetime(2026, 2, 1, 0, 1, tzinfo=UTC)
    current = [started]

    class TimeAdvancingProvider(MockLlmProvider):
        def complete(self, task: object) -> object:
            current[0] = completed
            return super().complete(task)  # type: ignore[arg-type]

    report = analyze_contributions(
        repo,
        person_selector="alice@example.com",
        clock=lambda: current[0],
        id_generator=lambda: "00000000-0000-0000-0000-000000000004",
        llm_provider=TimeAdvancingProvider(),
    )

    assert report["run"]["startedAt"] == started.isoformat()
    assert report["run"]["completedAt"] == completed.isoformat()


def test_should_analyze_all_git_people_with_project_dimensions(tmp_path: Path) -> None:
    repo = tmp_path / "project-analysis"
    builder = GitRepoBuilder.create(repo)
    builder.commit_text(
        "api/RoomController.java",
        "class RoomController {}\n",
        "feat(room): add room flow",
        name="Alice",
        email="alice@example.com",
    )
    builder.commit_text(
        "service/RechargeService.java",
        "class RechargeService {}\n",
        "fix(recharge): handle empty order",
        name="Bob",
        email="bob@example.com",
    )
    assert runner.invoke(app, ["init", str(repo)]).exit_code == 0

    analyzed = runner.invoke(
        app, ["analyze", str(repo), "--all", "--no-llm", "--json"]
    )

    assert analyzed.exit_code == 0, analyzed.stdout
    envelope = json.loads(analyzed.stdout)
    schema_root = Path(__file__).parents[2] / "schemas"
    validate(
        envelope,
        json.loads((schema_root / "analysis" / "v1.json").read_text(encoding="utf-8")),
    )
    report = envelope["data"]
    schema_path = schema_root / "project-report" / "v1.json"
    validate(report, json.loads(schema_path.read_text(encoding="utf-8")))
    assert report["reportType"] == "PROJECT"
    assert report["summary"]["people"] == 2
    assert report["summary"]["commits"] == 2
    assert {entry["person"]["email"] for entry in report["people"]} == {
        "alice@example.com",
        "bob@example.com",
    }
    assert all(entry["person"]["confirmed"] is False for entry in report["people"])
    assert all(entry["technicalSummary"] for entry in report["people"])
    assert all(entry["businessSummary"] for entry in report["people"])
    assert report["technicalSummary"]["dominantModules"]
    assert report["structuralSignals"]["ruleVersion"] == "structural-signals-v1"
    assert all(entry["structuralSignals"] for entry in report["people"])
    assert {entry["name"] for entry in report["businessSummary"]["domains"]} == {
        "room",
        "recharge",
    }
    assert len(report["identityWarnings"]) == 2
    assert report["run"]["providerId"] == "none"

    markdown = runner.invoke(
        app, ["report", str(repo), "--run", report["run"]["id"], "--format", "markdown"]
    )
    assert markdown.exit_code == 0
    assert "# Project Contribution Report" in markdown.stdout
    assert "## Technical Summary" in markdown.stdout
    assert "## Structural Signals" in markdown.stdout
    assert "## Business Summary" in markdown.stdout
    assert "## Contributors" in markdown.stdout


def test_should_reject_person_and_all_combination(git_repo: Path) -> None:
    result = runner.invoke(
        app,
        [
            "analyze",
            str(git_repo),
            "--person",
            "alice@example.com",
            "--all",
            "--no-llm",
        ],
    )

    assert result.exit_code == 2
    assert "mutually exclusive" in result.stderr
