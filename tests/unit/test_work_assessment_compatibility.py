from __future__ import annotations

import json
from pathlib import Path

from jsonschema import validate

from git_contribution_analyzer.adapters.reporting.work_assessment_markdown import (
    render_work_assessment_markdown,
)
from git_contribution_analyzer.adapters.reporting.work_assessment_series_markdown import (
    render_work_assessment_series_markdown,
)

ROOT = Path(__file__).parents[2]


def test_should_replay_frozen_v1_work_assessment_as_markdown() -> None:
    report = json.loads(
        (ROOT / "tests/fixtures/work-assessment-v1.json").read_text(encoding="utf-8")
    )
    schema = json.loads(
        (ROOT / "schemas/work-assessment/v1.json").read_text(encoding="utf-8")
    )

    validate(report, schema)
    rendered = render_work_assessment_markdown(report)

    assert "# Work Assessment" in rendered
    assert "Legacy User" in rendered
    assert "selection" not in rendered.casefold()
    assert "ranking" not in rendered.casefold()


def test_should_publish_work_assessment_v2_schema() -> None:
    schema = json.loads(
        (ROOT / "schemas/work-assessment/v2.json").read_text(encoding="utf-8")
    )

    assert schema["$id"].endswith("/work-assessment/v2.json")
    assert schema["properties"]["schemaVersion"] == {"const": "2.0"}


def test_should_replay_series_created_before_input_timezone_was_recorded() -> None:
    report = {
        "schemaVersion": "1.0",
        "reportType": "WORK_ASSESSMENT_SERIES",
        "run": {
            "id": "legacy-series",
            "runType": "WORK_ASSESSMENT_SERIES",
            "status": "COMPLETED",
            "startedAt": "2026-01-01T00:00:00+00:00",
            "completedAt": "2026-01-01T00:01:00+00:00",
            "ruleVersion": "work-assessment-series-v1",
        },
        "period": "month",
        "timeBasis": "AUTHORED",
        "range": {
            "since": "2026-01-01T00:00:00+00:00",
            "until": "2026-01-31T23:59:59.999999+00:00",
        },
        "periods": [],
        "warnings": [],
        "limitations": [],
    }
    schema = json.loads(
        (ROOT / "schemas/work-assessment-series/v1.json").read_text(encoding="utf-8")
    )

    validate(report, schema)
    rendered = render_work_assessment_series_markdown(report)

    assert "Input time zone: **LEGACY_UTC**" in rendered
