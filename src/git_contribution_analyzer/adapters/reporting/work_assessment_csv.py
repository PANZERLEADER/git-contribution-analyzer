from __future__ import annotations

import csv
import io
from typing import Any

from git_contribution_analyzer.domain.errors import ReportError

BASE_HEADER = [
    "person_id",
    "person_name",
    "total_rank",
    "total_score",
    "workload_rank",
    "workload_raw",
    "difficulty_rank",
    "difficulty_raw",
    "delivery_rank",
    "delivery_raw",
    "completed_items",
    "pending_items",
    "rework_items",
    "confidence",
    "gaps",
]


def render_work_assessment_csv(
    report: dict[str, Any], *, include_email: bool = False
) -> str:
    if report.get("reportType") != "WORK_ASSESSMENT" or report.get(
        "schemaVersion"
    ) != "2.0":
        raise ReportError("CSV export requires a persisted work-assessment/v2 run")
    ranking = report["ranking"]
    dimensions = {
        dimension["dimension"]: {
            entry["personId"]: entry for entry in dimension["entries"]
        }
        for dimension in ranking["dimensions"]
    }
    composite = {
        entry["personId"]: entry
        for entry in (ranking.get("composite") or {}).get("entries", [])
    }
    rows = [_subject_row(subject, dimensions, composite) for subject in report["subjects"]]
    rows.sort(key=_sort_key)
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    header = [*BASE_HEADER]
    if include_email:
        header.insert(2, "person_email")
    writer.writerow(header)
    for row in rows:
        values = [row[column] for column in BASE_HEADER]
        if include_email:
            values.insert(2, row["person_email"])
        writer.writerow(values)
    return "\ufeff" + output.getvalue()


def _subject_row(
    subject: dict[str, Any],
    dimensions: dict[str, dict[str, dict[str, Any]]],
    composite: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    person = subject["person"]
    person_id = str(person["id"])
    items = subject["itemAssessments"]
    dimension_entries = {
        name: entries.get(person_id) for name, entries in dimensions.items()
    }
    available_entries = [entry for entry in dimension_entries.values() if entry]
    confidence = (
        min((entry["confidence"] for entry in available_entries), default="")
        if available_entries
        else ""
    )
    gaps = sorted(
        {
            gap
            for entry in available_entries
            for gap in entry.get("gaps", [])
        }
    )
    result: dict[str, Any] = {
        "person_id": person_id,
        "person_name": person["name"],
        "person_email": person["email"],
        "completed_items": _count_bucket(items, "COMPLETED"),
        "pending_items": _count_bucket(items, "PENDING"),
        "rework_items": _count_bucket(items, "REWORK"),
        "confidence": confidence,
        "gaps": " | ".join(gaps),
    }
    composite_entry = composite.get(person_id, {})
    result["total_rank"] = composite_entry.get("totalRank", "")
    result["total_score"] = composite_entry.get("totalScore", "")
    for dimension in ("workload", "difficulty", "delivery"):
        entry = dimension_entries.get(dimension) or {}
        result[f"{dimension}_rank"] = entry.get("rank", "")
        result[f"{dimension}_raw"] = entry.get("rawValue", "")
    return result


def _sort_key(row: dict[str, Any]) -> tuple[int, int, str]:
    if row["total_rank"] != "":
        return (0, int(row["total_rank"]), str(row["person_id"]))
    for dimension in ("workload", "difficulty", "delivery"):
        rank = row[f"{dimension}_rank"]
        if rank != "":
            return (1, int(rank), str(row["person_id"]))
    return (2, 0, str(row["person_id"]))


def _count_bucket(items: list[dict[str, Any]], bucket: str) -> int:
    return sum(item["completionBucket"] == bucket for item in items)
