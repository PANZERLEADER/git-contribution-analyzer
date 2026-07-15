from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

SUPPORTED_PERIODS = ("week", "month", "quarter")
TREND_METRICS = (
    "completedItems",
    "pendingItems",
    "reworkItems",
    "integrationItems",
    "workloadPoints",
    "difficultyPoints",
)
SIZE_POINTS = {"SMALL": 1, "MEDIUM": 3, "LARGE": 6, "XLARGE": 10}
DIFFICULTY_POINTS = {"ROUTINE": 1, "STANDARD": 2, "COMPLEX": 4, "HIGH_RISK": 6}


@dataclass(frozen=True, slots=True)
class AssessmentPeriod:
    label: str
    since: datetime
    until: datetime
    partial: bool
    comparison_key: tuple[int, int]


def split_periods(since: datetime, until: datetime, period: str) -> tuple[AssessmentPeriod, ...]:
    normalized = period.casefold()
    if normalized not in SUPPORTED_PERIODS:
        raise ValueError(f"Unsupported assessment period: {period}")
    if since > until:
        raise ValueError("since must be earlier than or equal to until")

    periods: list[AssessmentPeriod] = []
    cursor = since
    while cursor <= until:
        start, next_start, label, comparison_key = _calendar_bounds(cursor, normalized)
        period_since = max(cursor, start)
        period_until = min(until, next_start - timedelta(microseconds=1))
        periods.append(
            AssessmentPeriod(
                label=label,
                since=period_since,
                until=period_until,
                partial=(
                    period_since != start
                    or period_until != next_start - timedelta(microseconds=1)
                ),
                comparison_key=comparison_key,
            )
        )
        cursor = next_start
    return tuple(periods)


def build_period_comparison(
    current: dict[str, int],
    previous: dict[str, int] | None,
    previous_year: dict[str, int] | None,
) -> dict[str, Any]:
    return {
        "periodOverPeriod": _metric_changes(current, previous),
        "yearOverYear": _metric_changes(current, previous_year),
    }


def summarize_assessment(report: dict[str, Any]) -> dict[str, int]:
    workload = report["workloadSummary"]
    completed = [
        item
        for subject in report["subjects"]
        for item in subject["itemAssessments"]
        if item["completionBucket"] == "COMPLETED"
    ]
    return {
        "completedItems": int(workload["completedItems"]),
        "pendingItems": int(workload["pendingItems"]),
        "reworkItems": int(workload["reworkItems"]),
        "integrationItems": int(workload["integrationItems"]),
        "workloadPoints": sum(SIZE_POINTS[item["size"]["band"]] for item in completed),
        "difficultyPoints": sum(
            DIFFICULTY_POINTS[item["difficulty"]["level"]] for item in completed
        ),
    }


def _metric_changes(
    current: dict[str, int], previous: dict[str, int] | None
) -> dict[str, dict[str, int | str | None]] | None:
    if previous is None:
        return None
    result: dict[str, dict[str, int | str | None]] = {}
    for metric in TREND_METRICS:
        current_value = current[metric]
        previous_value = previous[metric]
        percent = None
        if previous_value != 0:
            percent = str(
                ((Decimal(current_value - previous_value) / Decimal(previous_value)) * 100)
                .quantize(Decimal("0.0001"))
            )
        elif current_value == 0:
            percent = "0.0000"
        result[metric] = {
            "absolute": current_value - previous_value,
            "percent": percent,
        }
    return result


def _calendar_bounds(
    value: datetime, period: str
) -> tuple[datetime, datetime, str, tuple[int, int]]:
    midnight = value.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "week":
        start = midnight - timedelta(days=value.weekday())
        next_start = start + timedelta(days=7)
        iso_year, iso_week, _weekday = start.isocalendar()
        return start, next_start, f"{iso_year}-W{iso_week:02d}", (iso_year, iso_week)
    if period == "month":
        start = midnight.replace(day=1)
        next_start = (
            start.replace(year=start.year + 1, month=1)
            if start.month == 12
            else start.replace(month=start.month + 1)
        )
        return start, next_start, f"{start.year}-{start.month:02d}", (start.year, start.month)

    quarter = (value.month - 1) // 3 + 1
    start_month = (quarter - 1) * 3 + 1
    start = midnight.replace(month=start_month, day=1)
    next_start = (
        start.replace(year=start.year + 1, month=1)
        if start_month == 10
        else start.replace(month=start_month + 3)
    )
    return start, next_start, f"{start.year}-Q{quarter}", (start.year, quarter)
