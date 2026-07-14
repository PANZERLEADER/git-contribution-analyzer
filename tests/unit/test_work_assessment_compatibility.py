from __future__ import annotations

import json
from pathlib import Path

from jsonschema import validate

from git_contribution_analyzer.adapters.reporting.work_assessment_markdown import (
    render_work_assessment_markdown,
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
