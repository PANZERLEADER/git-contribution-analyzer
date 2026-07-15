from __future__ import annotations

import os
import time
from pathlib import Path
from threading import Event

from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QSignalSpy

from git_contribution_analyzer.adapters.gui.task_runner import RepositoryTaskRunner


def _application() -> QGuiApplication:
    os.environ.setdefault("QT_QUICK_BACKEND", "software")
    return QGuiApplication.instance() or QGuiApplication([])


def _wait_until(predicate: object, timeout: float = 3.0) -> None:
    application = _application()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        application.processEvents()
        if predicate():  # type: ignore[operator]
            return
        time.sleep(0.01)
    raise AssertionError("Timed out waiting for Qt task")


def test_runner_should_emit_success_result() -> None:
    runner = RepositoryTaskRunner(max_threads=2)
    spy = QSignalSpy(runner.taskSucceeded)

    task_id = runner.submit(
        Path("repository"),
        "status",
        mutates_workspace=False,
        operation=lambda reporter, token: {"healthy": True},
    )

    _wait_until(lambda: spy.count() == 1)
    arguments = spy.at(0)
    assert arguments[0] == task_id
    assert arguments[1] == {"healthy": True}


def test_same_repository_tasks_should_run_fifo() -> None:
    runner = RepositoryTaskRunner(max_threads=2)
    first_started = Event()
    release_first = Event()
    second_started = Event()
    succeeded = QSignalSpy(runner.taskSucceeded)

    def first(reporter: object, token: object) -> str:
        first_started.set()
        assert release_first.wait(timeout=3)
        return "first"

    def second(reporter: object, token: object) -> str:
        second_started.set()
        return "second"

    runner.submit(Path("repository"), "sync", mutates_workspace=True, operation=first)
    runner.submit(Path("repository"), "status", mutates_workspace=False, operation=second)

    _wait_until(first_started.is_set)
    assert second_started.is_set() is False
    release_first.set()
    _wait_until(lambda: succeeded.count() == 2)
    assert second_started.is_set() is True


def test_queued_task_should_cancel_without_starting() -> None:
    runner = RepositoryTaskRunner(max_threads=1)
    first_started = Event()
    release_first = Event()
    second_started = Event()
    cancelled = QSignalSpy(runner.taskCancelled)

    def first(reporter: object, token: object) -> str:
        first_started.set()
        assert release_first.wait(timeout=3)
        return "first"

    def second(reporter: object, token: object) -> str:
        second_started.set()
        return "second"

    runner.submit(Path("repository"), "sync", mutates_workspace=True, operation=first)
    task_id = runner.submit(
        Path("repository"),
        "index",
        mutates_workspace=True,
        operation=second,
    )
    _wait_until(first_started.is_set)

    assert runner.cancel(task_id) is True
    _wait_until(lambda: cancelled.count() == 1)
    release_first.set()

    assert cancelled.at(0)[0] == task_id
    assert second_started.is_set() is False
