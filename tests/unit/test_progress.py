from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from git_contribution_analyzer.application.ports.progress import (
    NullProgressReporter,
    ProgressEvent,
)


def _event(**overrides: object) -> ProgressEvent:
    values = {
        "task_id": "task-1",
        "operation": "index",
        "stage": "reading_commits",
        "repository": Path("repository"),
        "current": 1,
        "total": 2,
        "message": "Reading commits",
        "occurred_at": datetime(2026, 7, 15, tzinfo=UTC),
    }
    values.update(overrides)
    return ProgressEvent(**values)  # type: ignore[arg-type]


def test_null_reporter_should_accept_events() -> None:
    NullProgressReporter().report(_event())


@pytest.mark.parametrize(
    ("current", "total"),
    [(-1, 2), (3, 2), (1, -1), (1, None)],
)
def test_progress_event_should_reject_invalid_counts(
    current: int | None,
    total: int | None,
) -> None:
    with pytest.raises(ValueError):
        _event(current=current, total=total)


@pytest.mark.parametrize("stage", ["", "Reading Commits", "reading-commits"])
def test_progress_stage_should_be_stable_identifier(stage: str) -> None:
    with pytest.raises(ValueError):
        _event(stage=stage)
