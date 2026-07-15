from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

from jsonschema import validate
from typer.testing import CliRunner

from git_contribution_analyzer.cli.app import app
from tests.helpers.git_repo_builder import GitRepoBuilder

runner = CliRunner()
ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _repository(tmp_path: Path) -> Path:
    repo = tmp_path / "period-assessment"
    builder = GitRepoBuilder.create(repo)
    builder.commit_text(
        "src/january.py",
        "JANUARY = True\n",
        "feat: january",
        name="Alice",
        email="alice@example.com",
        authored_at=datetime(2026, 1, 15, 12, tzinfo=UTC),
        committed_at=datetime(2026, 2, 15, 12, tzinfo=UTC),
    )
    builder.commit_text(
        "src/february.py",
        "FEBRUARY = True\n",
        "feat: february",
        name="Alice",
        email="alice@example.com",
        authored_at=datetime(2026, 2, 20, 12, tzinfo=UTC),
    )
    assert runner.invoke(app, ["init", str(repo)]).exit_code == 0
    mapped = runner.invoke(
        app,
        [
            "identities", "map", str(repo),
            "--name", "Alice", "--email", "alice@example.com",
            "--person-name", "Alice", "--person-email", "alice@example.com",
        ],
    )
    assert mapped.exit_code == 0, mapped.stdout
    return repo


def test_should_reject_reversed_assessment_boundaries(tmp_path: Path) -> None:
    repo = _repository(tmp_path)

    result = runner.invoke(
        app,
        [
            "assess", str(repo), "--person", "alice@example.com",
            "--since", "2026-03-01", "--until", "2026-01-01", "--no-llm",
        ],
    )

    assert result.exit_code == 2
    output = ANSI_ESCAPE.sub("", result.stdout + result.stderr)
    assert "--since must be earlier" in output


def test_should_generate_monthly_series_with_trends_in_one_command(tmp_path: Path) -> None:
    repo = _repository(tmp_path)

    result = runner.invoke(
        app,
        [
            "assess", str(repo), "--person", "alice@example.com",
            "--since", "2026-01-01", "--until", "2026-02-28",
            "--period", "month", "--time-basis", "authored", "--no-llm", "--json",
        ],
    )

    assert result.exit_code == 0, result.stdout
    report = json.loads(result.stdout)["data"]
    schema = json.loads(
        (Path(__file__).parents[2] / "schemas/work-assessment-series/v1.json").read_text(
            encoding="utf-8"
        )
    )
    validate(report, schema)
    assert report["reportType"] == "WORK_ASSESSMENT_SERIES"
    assert report["period"] == "month"
    assert report["timeBasis"] == "AUTHORED"
    assert report["inputTimeZone"] == "SYSTEM"
    assert [entry["label"] for entry in report["periods"]] == ["2026-01", "2026-02"]
    assert all(entry["runId"] for entry in report["periods"])
    assert report["periods"][1]["comparison"]["periodOverPeriod"] is not None
    baseline_sizes = set()
    for entry in report["periods"]:
        child = runner.invoke(
            app, ["runs", "show", entry["runId"], str(repo), "--json"]
        )
        assert child.exit_code == 0, child.stdout
        child_report = json.loads(child.stdout)["data"]
        baseline_sizes.update(
            item["size"]["baselineSampleSize"]
            for subject in child_report["subjects"]
            for item in subject["itemAssessments"]
        )
    assert baseline_sizes == {2}
    replayed = runner.invoke(
        app,
        ["report", str(repo), "--run", report["run"]["id"], "--format", "markdown"],
    )
    assert replayed.exit_code == 0, replayed.stdout
    assert "Work Assessment Series" in replayed.stdout


def test_should_filter_by_committer_time(tmp_path: Path) -> None:
    repo = _repository(tmp_path)

    result = runner.invoke(
        app,
        [
            "assess", str(repo), "--person", "alice@example.com",
            "--since", "2026-01-01", "--until", "2026-01-31",
            "--time-basis", "committed", "--no-llm", "--json",
        ],
    )

    assert result.exit_code == 0, result.stdout
    report = json.loads(result.stdout)["data"]
    assert report["snapshot"]["filters"]["timeBasis"] == "COMMITTED"
    assert report["workloadSummary"]["completedItems"] == 0


def test_should_normalize_git_offsets_before_time_filtering(tmp_path: Path) -> None:
    repo = tmp_path / "offset-times"
    builder = GitRepoBuilder.create(repo)
    builder.commit_text(
        "src/offset.py",
        "OFFSET = True\n",
        "feat: offset timestamp",
        name="Alice",
        email="alice@example.com",
        authored_at=datetime(2026, 1, 1, 0, 30, tzinfo=timezone(timedelta(hours=8))),
    )
    assert runner.invoke(app, ["init", str(repo)]).exit_code == 0
    assert runner.invoke(
        app,
        [
            "identities", "map", str(repo), "--name", "Alice",
            "--email", "alice@example.com", "--person-name", "Alice",
            "--person-email", "alice@example.com",
        ],
    ).exit_code == 0

    result = runner.invoke(
        app,
        [
            "assess", str(repo), "--person", "alice@example.com",
            "--since", "2025-12-31T16:00:00+00:00",
            "--until", "2025-12-31T17:00:00+00:00",
            "--no-llm", "--json",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["data"]["workloadSummary"]["completedItems"] == 1


def test_should_use_merge_landing_and_release_event_times(tmp_path: Path) -> None:
    repo = tmp_path / "delivery-times"
    builder = GitRepoBuilder.create(repo)
    builder.commit_text(
        "README.md", "base\n", "docs: base",
        authored_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    builder.checkout("feature", create=True)
    builder.commit_text(
        "src/feature.py", "FEATURE = True\n", "feat: delivered feature",
        name="Alice", email="alice@example.com",
        authored_at=datetime(2026, 1, 10, tzinfo=UTC),
    )
    builder.checkout("main")
    builder.merge("feature", "merge: feature", committed_at=datetime(2026, 2, 10, tzinfo=UTC))
    builder.tag("v1.0.0", created_at=datetime(2026, 3, 10, tzinfo=UTC))
    assert runner.invoke(app, ["init", str(repo)]).exit_code == 0
    assert runner.invoke(
        app,
        [
            "identities", "map", str(repo), "--name", "Alice",
            "--email", "alice@example.com", "--person-name", "Alice",
            "--person-email", "alice@example.com",
        ],
    ).exit_code == 0

    def completed(basis: str, since: str, until: str) -> int:
        result = runner.invoke(
            app,
            [
                "assess", str(repo), "--person", "alice@example.com",
                "--since", since, "--until", until, "--time-basis", basis,
                "--no-llm", "--json",
            ],
        )
        assert result.exit_code == 0, result.stdout
        return int(json.loads(result.stdout)["data"]["workloadSummary"]["completedItems"])

    assert completed("landed", "2026-01-01", "2026-01-31") == 0
    assert completed("landed", "2026-02-01", "2026-02-28") >= 1
    assert completed("merged", "2026-02-01", "2026-02-28") >= 1
    assert completed("released", "2026-03-01", "2026-03-31") >= 1


def test_should_compare_two_historical_assessment_runs(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    run_ids = []
    for since, until in (("2026-01-01", "2026-01-31"), ("2026-02-01", "2026-02-28")):
        result = runner.invoke(
            app,
            [
                "assess", str(repo), "--person", "alice@example.com",
                "--since", since, "--until", until, "--no-llm", "--json",
            ],
        )
        assert result.exit_code == 0, result.stdout
        run_ids.append(json.loads(result.stdout)["data"]["run"]["id"])

    compared = runner.invoke(
        app,
        ["runs", "compare", run_ids[0], run_ids[1], str(repo), "--json"],
    )

    assert compared.exit_code == 0, compared.stdout
    comparison = json.loads(compared.stdout)["data"]
    schema = json.loads(
        (Path(__file__).parents[2] / "schemas/work-assessment-comparison/v1.json").read_text(
            encoding="utf-8"
        )
    )
    validate(comparison, schema)
    assert comparison["reportType"] == "WORK_ASSESSMENT_COMPARISON"
    assert comparison["baseRunId"] == run_ids[0]
    assert comparison["targetRunId"] == run_ids[1]
    assert "completedItems" in comparison["changes"]
