from __future__ import annotations

from datetime import timedelta, timezone

import pytest

from git_contribution_analyzer.application.services import time_boundaries


def test_should_interpret_naive_boundary_in_system_timezone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    china = timezone(timedelta(hours=8))
    monkeypatch.setattr(
        time_boundaries,
        "localize_system_time",
        lambda value: value.replace(tzinfo=china),
    )

    parsed = time_boundaries.parse_boundary("2026-07-01T09:30:00", end_of_day=False)

    assert parsed.isoformat() == "2026-07-01T09:30:00+08:00"


def test_should_preserve_explicit_timezone_boundary() -> None:
    parsed = time_boundaries.parse_boundary(
        "2026-07-01T09:30:00+02:00",
        end_of_day=False,
    )

    assert parsed.isoformat() == "2026-07-01T09:30:00+02:00"


def test_shared_service_should_interpret_naive_boundary_in_system_timezone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    china = timezone(timedelta(hours=8))
    monkeypatch.setattr(
        time_boundaries,
        "localize_system_time",
        lambda value: value.replace(tzinfo=china),
    )

    since, until = time_boundaries.parse_boundaries(
        "2026-07-01",
        "2026-07-31",
    )

    assert since is not None
    assert until is not None
    assert since.isoformat() == "2026-07-01T00:00:00+08:00"
    assert until.isoformat() == "2026-07-31T23:59:59.999999+08:00"


def test_shared_service_should_reject_since_after_until() -> None:
    with pytest.raises(ValueError, match=r"since.*until"):
        time_boundaries.parse_boundaries("2026-08-01", "2026-07-31")
