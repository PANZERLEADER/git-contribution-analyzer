from __future__ import annotations

from datetime import UTC, datetime

from git_contribution_analyzer.domain.services.assessment_periods import (
    build_period_comparison,
    split_periods,
)


def test_should_split_calendar_months_and_mark_partial_boundaries() -> None:
    periods = split_periods(
        datetime(2026, 1, 15, tzinfo=UTC),
        datetime(2026, 3, 10, tzinfo=UTC),
        "month",
    )

    assert [period.label for period in periods] == ["2026-01", "2026-02", "2026-03"]
    assert [period.partial for period in periods] == [True, False, True]
    assert periods[0].since == datetime(2026, 1, 15, tzinfo=UTC)
    assert periods[0].until == datetime(2026, 1, 31, 23, 59, 59, 999999, tzinfo=UTC)


def test_should_split_calendar_weeks_from_monday() -> None:
    periods = split_periods(
        datetime(2026, 1, 5, tzinfo=UTC),
        datetime(2026, 1, 18, 23, 59, 59, 999999, tzinfo=UTC),
        "week",
    )

    assert [period.label for period in periods] == ["2026-W02", "2026-W03"]
    assert all(not period.partial for period in periods)


def test_should_split_calendar_quarters_across_year_boundary() -> None:
    periods = split_periods(
        datetime(2025, 10, 1, tzinfo=UTC),
        datetime(2026, 3, 31, 23, 59, 59, 999999, tzinfo=UTC),
        "quarter",
    )

    assert [period.label for period in periods] == ["2025-Q4", "2026-Q1"]
    assert all(not period.partial for period in periods)


def test_should_calculate_period_over_period_and_year_over_year() -> None:
    current = {
        "completedItems": 12,
        "pendingItems": 1,
        "reworkItems": 2,
        "integrationItems": 1,
        "workloadPoints": 18,
        "difficultyPoints": 9,
    }
    previous = {**current, "completedItems": 8}
    previous_year = {**current, "completedItems": 6}

    comparison = build_period_comparison(current, previous, previous_year)

    assert comparison["periodOverPeriod"]["completedItems"] == {
        "absolute": 4,
        "percent": "50.0000",
    }
    assert comparison["yearOverYear"]["completedItems"] == {
        "absolute": 6,
        "percent": "100.0000",
    }
