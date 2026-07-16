from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from PySide6.QtGui import QGuiApplication

from git_contribution_analyzer.adapters.gui.controller import GuiController
from git_contribution_analyzer.adapters.gui.settings import GuiSettings
from git_contribution_analyzer.adapters.gui.task_runner import RepositoryTaskRunner


class FakeFacade:
    def __init__(self) -> None:
        self.assessment_requests: list[object] = []

    def open_repository(self, path: Path) -> dict[str, Any]:
        return {
            "repository": str(path.resolve()),
            "workspaceInitialized": True,
            "databaseHealthy": True,
            "indexStatus": "up-to-date",
            "indexedCommits": 4,
            "identities": 2,
            "unresolvedIdentities": 0,
            "structural": {
                "baselineCount": 1,
                "latestBaselineId": "baseline-1",
                "processedCommits": 4,
                "unhealthyBaselines": 0,
            },
        }

    def structural_status(self, path: Path) -> dict[str, Any]:
        return {
            "baselineCount": 1,
            "latestBaselineId": "baseline-1",
            "processedCommits": 4,
            "unhealthyBaselines": 0,
        }

    def show_structural(self, path: Path, baseline_id: str) -> dict[str, Any]:
        return {
            "baselineId": baseline_id,
            "status": "COMPLETED",
            "materialization": {
                "hotspots": [{"path": "src/a.py", "changeCount": 4}],
                "couplings": [
                    {
                        "leftPath": "src/a.py",
                        "rightPath": "db/b.sql",
                        "coChangeCount": 3,
                    }
                ],
            },
        }

    def rebuild_structural(self, request: object, **kwargs: object) -> dict[str, Any]:
        return self.show_structural(Path("repository"), "baseline-2")

    def prune_structural(self, path: Path, *, keep: int) -> dict[str, int]:
        return {"deletedBaselines": 1, "remainingBaselines": keep}

    def assess(self, request: object, **kwargs: object) -> dict[str, Any]:
        self.assessment_requests.append(request)
        return {
            "reportType": "WORK_ASSESSMENT",
            "run": {"id": "run-1", "status": "COMPLETED"},
            "workloadSummary": {"completedItems": 3, "pendingItems": 1},
            "difficultyDistribution": {"HIGH": 1},
            "contributionItems": [{"id": "item-1", "title": "Feature"}],
            "evidence": [{"id": "ev-1", "summary": "Commit evidence"}],
            "warnings": [],
        }

    @staticmethod
    def map_error(error: Exception) -> object:
        return type(
            "Error",
            (),
            {"message": str(error), "title": "Error", "code": "TEST", "detail": ""},
        )()


def _wait_until(predicate: object, timeout: float = 3.0) -> None:
    os.environ.setdefault("QT_QUICK_BACKEND", "software")
    application = QGuiApplication.instance() or QGuiApplication([])
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        application.processEvents()
        if predicate():  # type: ignore[operator]
            return
        time.sleep(0.01)
    raise AssertionError("Timed out waiting for controller")


def test_controller_should_open_repository_and_remember_it(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    settings = GuiSettings(tmp_path / "settings.ini")
    controller = GuiController(
        facade=FakeFacade(),  # type: ignore[arg-type]
        task_runner=RepositoryTaskRunner(max_threads=1),
        settings=settings,
    )

    controller.openRepository(str(repository))

    _wait_until(lambda: controller.repositoryPath == str(repository.resolve()))
    assert controller.workspaceInitialized is True
    assert controller.indexedCommits == 4
    assert settings.recent_repositories()[0] == str(repository.resolve())


def test_controller_should_project_assessment_result(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    facade = FakeFacade()
    controller = GuiController(
        facade=facade,  # type: ignore[arg-type]
        task_runner=RepositoryTaskRunner(max_threads=1),
        settings=GuiSettings(tmp_path / "settings.ini"),
    )
    controller.openRepository(str(repository))
    _wait_until(lambda: bool(controller.repositoryPath))

    controller.runAssessment(
        {
            "persons": ["person@example.com"],
            "allPeople": False,
            "since": "2026-01-01",
            "until": "2026-03-31",
            "period": "",
            "timeBasis": "authored",
            "useLlm": False,
        }
    )

    _wait_until(lambda: controller.currentRunId == "run-1")
    assert controller.completedItems == 3
    assert controller.workItemsModel.rowCount() == 1
    assert controller.evidenceModel.rowCount() == 1
    assert len(facade.assessment_requests) == 1


def test_controller_should_project_structural_observations(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    controller = GuiController(
        facade=FakeFacade(),  # type: ignore[arg-type]
        task_runner=RepositoryTaskRunner(max_threads=1),
        settings=GuiSettings(tmp_path / "settings.ini"),
    )
    controller.openRepository(str(repository))
    _wait_until(lambda: controller.structuralLatestBaselineId == "baseline-1")

    controller.showStructural("")

    _wait_until(lambda: controller.structuralHotspotsModel.rowCount() == 1)
    assert controller.structuralBaselineCount == 1
    assert controller.structuralProcessedCommits == 4
    assert controller.structuralCouplingsModel.rowCount() == 1

    controller.rebuildStructural(
        {
            "cutoff": "2026-07-01T00:00:00Z",
            "branch": "main",
            "scope": "src",
            "timeStrategy": "lifetime",
        }
    )
    _wait_until(lambda: "baseline-2" in controller.currentReportJson)

    controller.pruneStructural(1)
    _wait_until(lambda: not controller.busy)
