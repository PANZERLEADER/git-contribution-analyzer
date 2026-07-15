from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from git_contribution_analyzer.application.dto.gui import AssessmentRequest
from git_contribution_analyzer.application.facades import gui as gui_module
from git_contribution_analyzer.application.facades.gui import GuiApplicationFacade


def _request(**overrides: object) -> AssessmentRequest:
    values: dict[str, object] = {
        "repository": Path("repository"),
        "person_selectors": ("person@example.com",),
        "use_llm": False,
    }
    values.update(overrides)
    return AssessmentRequest(**values)  # type: ignore[arg-type]


def test_assess_should_route_to_single_run_without_period(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_assess(path: Path, **kwargs: Any) -> dict[str, Any]:
        calls.append({"path": path, **kwargs})
        return {"reportType": "WORK_ASSESSMENT", "warnings": []}

    monkeypatch.setattr(gui_module, "assess_work", fake_assess)

    report = GuiApplicationFacade().assess(_request())

    assert report["reportType"] == "WORK_ASSESSMENT"
    assert calls[0]["person_selectors"] == ("person@example.com",)
    assert calls[0]["filters"].time_basis == "AUTHORED"


def test_assess_should_route_to_series_with_period(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_series(path: Path, **kwargs: Any) -> dict[str, Any]:
        calls.append({"path": path, **kwargs})
        return {"reportType": "WORK_ASSESSMENT_SERIES", "warnings": []}

    monkeypatch.setattr(gui_module, "assess_work_series", fake_series)

    report = GuiApplicationFacade().assess(
        _request(
            period="month",
            since_text="2026-01-01",
            until_text="2026-03-31",
        )
    )

    assert report["reportType"] == "WORK_ASSESSMENT_SERIES"
    assert calls[0]["period"] == "month"


def test_assess_should_reject_reversed_time_range() -> None:
    with pytest.raises(ValueError, match=r"since.*until"):
        GuiApplicationFacade().assess(
            _request(since_text="2026-08-01", until_text="2026-07-31")
        )
