from __future__ import annotations

import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from git_contribution_analyzer.cli.app import app
from tests.helpers.golden_repository import build_dual_track_golden_repository

runner = CliRunner()


def _run(*arguments: str) -> object:
    result = runner.invoke(app, list(arguments))
    assert result.exit_code == 0, result.stdout
    return result


def test_should_complete_dual_track_golden_lifecycle_in_unicode_path(
    tmp_path: Path,
) -> None:
    fixture = build_dual_track_golden_repository(tmp_path / "golden 仓库 with spaces")
    repo = fixture.path

    _run("init", str(repo))
    _run(
        "identities",
        "map",
        str(repo),
        "--name",
        fixture.alice_name,
        "--email",
        fixture.alice_email,
        "--person-name",
        fixture.alice_name,
        "--person-email",
        fixture.alice_email,
    )

    analysis = _run(
        "analyze",
        str(repo),
        "--person",
        fixture.alice_email,
        "--no-llm",
        "--json",
    )
    analysis_report = json.loads(analysis.stdout)["data"]
    assert analysis_report["summary"]["commits"] >= 8

    assessment = _run(
        "assess",
        str(repo),
        "--person",
        fixture.alice_email,
        "--no-llm",
        "--json",
    )
    assessment_report = json.loads(assessment.stdout)["data"]
    assert assessment_report["workloadSummary"]["completedItems"] >= 3
    assert assessment_report["workloadSummary"]["pendingItems"] >= 1
    assert assessment_report["workloadSummary"]["reworkItems"] >= 1
    difficulty_levels = {
        item["difficulty"]["level"]
        for item in assessment_report["subjects"][0]["itemAssessments"]
    }
    assert "HIGH_RISK" in difficulty_levels
    assert "ROUTINE" in difficulty_levels

    project_assessment = _run(
        "assess", str(repo), "--all", "--no-llm", "--json"
    )
    project_report = json.loads(project_assessment.stdout)["data"]
    assert project_report["scopeType"] == "PROJECT"
    assert len(project_report["subjects"]) == 1
    assert any(
        exclusion["reason"] == "UNCONFIRMED"
        for exclusion in project_report["selection"]["exclusions"]
    )
    assert project_report["ranking"]["enabled"] is False
    assert project_report["ranking"]["dimensions"] == []

    _run(
        "identities",
        "map",
        str(repo),
        "--name",
        fixture.bob_name,
        "--email",
        fixture.bob_email,
        "--person-name",
        fixture.bob_name,
        "--person-email",
        fixture.bob_email,
    )
    ranking_config = tmp_path / "ranking.yml"
    ranking_config.write_text(
        """schemaVersion: "1.0"
rankingRuleVersion: performance-ranking-v1
weights:
  workload: 0.45
  difficulty: 0.35
  delivery: 0.20
normalization: cohort-max
ties: dense
""",
        encoding="utf-8",
    )
    ranked = _run(
        "assess",
        str(repo),
        "--person",
        fixture.alice_email,
        "--person",
        fixture.bob_email,
        "--ranking-config",
        str(ranking_config),
        "--no-llm",
        "--json",
    )
    ranked_report = json.loads(ranked.stdout)["data"]
    assert ranked_report["ranking"]["enabled"] is True
    assert ranked_report["ranking"]["composite"]["entries"]

    csv_path = tmp_path / "reports" / "team.csv"
    _run(
        "report",
        str(repo),
        "--run",
        ranked_report["run"]["id"],
        "--format",
        "csv",
        "--output",
        str(csv_path),
    )
    csv_payload = csv_path.read_bytes()
    assert csv_payload.startswith(b"\xef\xbb\xbf")
    assert fixture.alice_email.encode() not in csv_payload
    assert fixture.bob_email.encode() not in csv_payload

    merged = _run(
        "identities",
        "merge",
        str(repo),
        "--source",
        fixture.alice_email,
        "--target",
        fixture.bob_email,
        "--yes",
        "--json",
    )
    merge_event = json.loads(merged.stdout)["data"]
    merged_assessment = _run(
        "assess",
        str(repo),
        "--person",
        fixture.bob_email,
        "--no-llm",
        "--json",
    )
    assert len(json.loads(merged_assessment.stdout)["data"]["evidence"]) > 1
    _run(
        "identities",
        "unmerge",
        str(repo),
        "--merge-id",
        merge_event["mergeId"],
        "--yes",
        "--json",
    )

    resume = _run(
        "resume",
        str(repo),
        "--person",
        fixture.alice_email,
        "--language",
        "en-US",
        "--style",
        "concise",
        "--no-llm",
        "--json",
    )
    resume_report = json.loads(resume.stdout)["data"]
    assert resume_report["experienceBullets"]
    assert fixture.alice_email not in resume.stdout
    assert fixture.bob_email not in resume.stdout

    outcomes = tmp_path / "verified outcomes.yml"
    outcomes.write_text(
        """outcomes:
  - id: OUT-001
    text: Reduced API latency by 35%
    source: benchmark-report.md
    verifiedBy: engineering-lead
    verifiedAt: 2026-01-15
""",
        encoding="utf-8",
    )
    config_path = repo / ".gca" / "config.yml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["llm"].update({"enabled": True, "provider": "mock"})
    config_path.write_text(
        yaml.safe_dump(config, sort_keys=False), encoding="utf-8", newline="\n"
    )
    enhanced_resume = _run(
        "resume",
        str(repo),
        "--person",
        fixture.alice_email,
        "--verified-outcomes",
        str(outcomes),
        "--json",
    )
    assert json.loads(enhanced_resume.stdout)["data"]["run"]["providerId"] == "mock"

    runs = _run("runs", "list", str(repo), "--json")
    run_entries = json.loads(runs.stdout)["data"]["runs"]
    assert {entry["runType"] for entry in run_entries} >= {
        "ANALYSIS",
        "WORK_ASSESSMENT",
        "RESUME",
    }

    latest_run_id = run_entries[0]["id"]
    shown = _run("runs", "show", latest_run_id, str(repo), "--json")
    assert json.loads(shown.stdout)["data"]["run"]["id"] == latest_run_id

    markdown_path = tmp_path / "reports" / "resume.md"
    json_path = tmp_path / "reports" / "resume.json"
    _run(
        "report",
        str(repo),
        "--run",
        latest_run_id,
        "--format",
        "markdown",
        "--output",
        str(markdown_path),
    )
    _run(
        "report",
        str(repo),
        "--run",
        latest_run_id,
        "--format",
        "json",
        "--output",
        str(json_path),
    )
    assert "Resume Draft" in markdown_path.read_text(encoding="utf-8")
    assert json.loads(json_path.read_text(encoding="utf-8"))["run"]["id"] == latest_run_id
