from __future__ import annotations

import csv
import io

import pytest

from git_contribution_analyzer.adapters.reporting.work_assessment_csv import (
    render_work_assessment_csv,
)
from git_contribution_analyzer.domain.errors import ReportError


def _report() -> dict[str, object]:
    return {
        "schemaVersion": "2.0",
        "reportType": "WORK_ASSESSMENT",
        "subjects": [
            {
                "person": {
                    "id": "p1",
                    "name": '张三, "平台"',
                    "email": "person@example.com",
                },
                "itemAssessments": [
                    {"completionBucket": "COMPLETED"},
                    {"completionBucket": "REWORK"},
                ],
            }
        ],
        "ranking": {
            "dimensions": [
                {
                    "dimension": "workload",
                    "entries": [
                        {
                            "personId": "p1",
                            "rank": 1,
                            "rawValue": "3.0000",
                            "confidence": "HIGH",
                            "gaps": [],
                        }
                    ],
                }
            ],
            "composite": None,
        },
    }


def test_should_render_bom_crlf_csv_without_email_by_default() -> None:
    rendered = render_work_assessment_csv(_report())

    assert rendered.startswith("\ufeff")
    assert "\r\n" in rendered
    assert "person_email" not in rendered.split("\r\n", maxsplit=1)[0]
    rows = list(csv.DictReader(io.StringIO(rendered.removeprefix("\ufeff"))))
    assert rows[0]["person_name"] == '张三, "平台"'
    assert "person@example.com" not in rendered


def test_should_include_email_only_when_requested() -> None:
    rendered = render_work_assessment_csv(_report(), include_email=True)

    assert "person_email" in rendered.split("\r\n", maxsplit=1)[0]
    assert "person@example.com" in rendered


def test_should_reject_v1_csv_export() -> None:
    with pytest.raises(ReportError, match="v2"):
        render_work_assessment_csv(
            {"schemaVersion": "1.0", "reportType": "WORK_ASSESSMENT"}
        )
