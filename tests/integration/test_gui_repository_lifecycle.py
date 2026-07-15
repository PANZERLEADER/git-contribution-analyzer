from __future__ import annotations

import os
import time
from pathlib import Path

from PySide6.QtGui import QGuiApplication

from git_contribution_analyzer.adapters.gui.controller import GuiController
from git_contribution_analyzer.adapters.gui.settings import GuiSettings
from git_contribution_analyzer.adapters.gui.task_runner import RepositoryTaskRunner
from tests.helpers.git_repo_builder import GitRepoBuilder


def _wait_until(predicate: object, timeout: float = 10.0) -> None:
    application = QGuiApplication.instance() or QGuiApplication([])
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        application.processEvents()
        if predicate():  # type: ignore[operator]
            return
        time.sleep(0.01)
    raise AssertionError("Timed out waiting for GUI lifecycle")


def test_gui_should_complete_repository_assessment_lifecycle(tmp_path: Path) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("QT_QUICK_BACKEND", "software")
    repository = tmp_path / "GUI 验证 repository"
    builder = GitRepoBuilder.create(repository)
    builder.commit_text(
        "src/app.py",
        "print('gui')\n",
        "feat: add gui lifecycle",
        name="Alice",
        email="alice@example.com",
    )
    controller = GuiController(
        task_runner=RepositoryTaskRunner(max_threads=2),
        settings=GuiSettings(tmp_path / "gui-settings.ini"),
    )

    controller.openRepository(str(repository))
    _wait_until(lambda: bool(controller.repositoryPath) and not controller.busy)
    assert controller.workspaceInitialized is False

    controller.initializeRepository()
    _wait_until(lambda: controller.workspaceInitialized and not controller.busy)
    assert controller.indexedCommits == 1

    controller.mapIdentity("Alice", "alice@example.com", "Alice", "alice@example.com")
    _wait_until(lambda: not controller.busy)

    controller.runAssessment(
        {
            "persons": ["alice@example.com"],
            "allPeople": False,
            "timeBasis": "authored",
            "useLlm": False,
        }
    )
    _wait_until(lambda: bool(controller.currentRunId) and not controller.busy)

    assert controller.completedItems == 1
    assert controller.workItemsModel.rowCount() == 1
    assert controller.evidenceModel.rowCount() >= 1
