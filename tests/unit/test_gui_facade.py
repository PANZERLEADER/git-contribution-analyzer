from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from git_contribution_analyzer.application.dto.gui import (
    AssessmentRequest,
    StructuralBaselineRequest,
)
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


def test_structural_rebuild_should_parse_gui_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_rebuild(path: Path, **kwargs: Any) -> dict[str, Any]:
        calls.append({"path": path, **kwargs})
        return {"baselineId": "baseline-1", "status": "COMPLETED"}

    monkeypatch.setattr(gui_module, "rebuild_structural_baseline", fake_rebuild)

    result = GuiApplicationFacade().rebuild_structural(
        StructuralBaselineRequest(
            repository=Path("repository"),
            cutoff_text="2026-07-01T00:00:00Z",
            branch="main",
            scope="src",
            time_strategy="dual-window",
        )
    )

    assert result["baselineId"] == "baseline-1"
    assert calls[0]["cutoff"].isoformat() == "2026-07-01T00:00:00+00:00"
    assert calls[0]["branch"] == "main"
    assert calls[0]["scope"] == "src"
    assert calls[0]["time_strategy"].value == "DUAL_WINDOW"


def test_structural_facade_should_route_status_show_and_prune(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        gui_module,
        "get_structural_status",
        lambda path: {"baselineCount": 1, "latestBaselineId": "baseline-1"},
    )
    monkeypatch.setattr(
        gui_module,
        "show_structural_baseline",
        lambda path, baseline_id: {"baselineId": baseline_id},
    )
    monkeypatch.setattr(
        gui_module,
        "prune_structural_baselines",
        lambda path, *, keep: {"deletedBaselines": 2, "remainingBaselines": keep},
    )
    facade = GuiApplicationFacade()

    assert facade.structural_status(Path("repository"))["baselineCount"] == 1
    assert facade.show_structural(Path("repository"), "baseline-1")["baselineId"] == (
        "baseline-1"
    )
    assert facade.prune_structural(Path("repository"), keep=3) == {
        "deletedBaselines": 2,
        "remainingBaselines": 3,
    }
