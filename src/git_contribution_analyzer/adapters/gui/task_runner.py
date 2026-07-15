from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from git_contribution_analyzer.application.ports.cancellation import (
    CancellationSource,
    CancellationToken,
    OperationCancelled,
)
from git_contribution_analyzer.application.ports.progress import (
    ProgressEvent,
    ProgressReporter,
)

TaskOperation = Callable[[ProgressReporter, CancellationToken], Any]


class _TaskSignals(QObject):
    progress = Signal(str, dict)
    finished = Signal(str, str, str, object)


class _SignalProgressReporter:
    def __init__(self, task_id: str, signals: _TaskSignals) -> None:
        self._task_id = task_id
        self._signals = signals

    def report(self, event: ProgressEvent) -> None:
        self._signals.progress.emit(
            self._task_id,
            {
                "schemaVersion": event.schema_version,
                "operation": event.operation,
                "stage": event.stage,
                "repository": str(event.repository),
                "current": event.current,
                "total": event.total,
                "message": event.message,
                "occurredAt": event.occurred_at.isoformat(),
            },
        )


@dataclass(slots=True)
class _TaskRecord:
    task_id: str
    repository_key: str
    operation_name: str
    mutates_workspace: bool
    operation: TaskOperation
    cancellation: CancellationSource
    signals: _TaskSignals


class _TaskRunnable(QRunnable):
    def __init__(self, record: _TaskRecord) -> None:
        super().__init__()
        self.setAutoDelete(True)
        self._record = record

    @Slot()
    def run(self) -> None:
        record = self._record
        reporter = _SignalProgressReporter(record.task_id, record.signals)
        try:
            record.cancellation.token.raise_if_cancelled()
            result = record.operation(reporter, record.cancellation.token)
        except OperationCancelled as error:
            record.signals.finished.emit(
                record.task_id,
                record.repository_key,
                "cancelled",
                error,
            )
        except Exception as error:
            record.signals.finished.emit(
                record.task_id,
                record.repository_key,
                "failed",
                error,
            )
        else:
            record.signals.finished.emit(
                record.task_id,
                record.repository_key,
                "succeeded",
                result,
            )


class RepositoryTaskRunner(QObject):
    taskQueued = Signal(str, str)
    taskStarted = Signal(str, str)
    taskProgress = Signal(str, dict)
    taskSucceeded = Signal(str, object)
    taskFailed = Signal(str, object)
    taskCancelled = Signal(str)

    def __init__(self, *, max_threads: int = 4) -> None:
        super().__init__()
        self._pool = QThreadPool()
        self._pool.setMaxThreadCount(max(1, max_threads))
        self._queues: dict[str, deque[_TaskRecord]] = defaultdict(deque)
        self._active: dict[str, _TaskRecord] = {}

    def submit(
        self,
        repository: Path,
        operation_name: str,
        *,
        mutates_workspace: bool,
        operation: TaskOperation,
    ) -> str:
        task_id = str(uuid4())
        repository_key = str(repository.expanduser().resolve())
        signals = _TaskSignals()
        signals.progress.connect(self.taskProgress)
        signals.finished.connect(self._task_finished)
        record = _TaskRecord(
            task_id=task_id,
            repository_key=repository_key,
            operation_name=operation_name,
            mutates_workspace=mutates_workspace,
            operation=operation,
            cancellation=CancellationSource(),
            signals=signals,
        )
        self._queues[repository_key].append(record)
        self.taskQueued.emit(task_id, operation_name)
        self._start_next(repository_key)
        return task_id

    def cancel(self, task_id: str) -> bool:
        for active in self._active.values():
            if active.task_id == task_id:
                active.cancellation.cancel()
                return True
        for repository_key, queue in self._queues.items():
            for record in tuple(queue):
                if record.task_id == task_id:
                    queue.remove(record)
                    self.taskCancelled.emit(task_id)
                    if not queue and repository_key not in self._active:
                        self._queues.pop(repository_key, None)
                    return True
        return False

    def has_active_tasks(self) -> bool:
        return bool(self._active or any(self._queues.values()))

    def cancel_all(self) -> None:
        for active in self._active.values():
            active.cancellation.cancel()
        for queue in self._queues.values():
            while queue:
                record = queue.popleft()
                self.taskCancelled.emit(record.task_id)

    def wait_for_done(self, milliseconds: int = -1) -> bool:
        return self._pool.waitForDone(milliseconds)

    def _start_next(self, repository_key: str) -> None:
        if repository_key in self._active:
            return
        queue = self._queues.get(repository_key)
        if not queue:
            self._queues.pop(repository_key, None)
            return
        record = queue.popleft()
        self._active[repository_key] = record
        self.taskStarted.emit(record.task_id, record.operation_name)
        self._pool.start(_TaskRunnable(record))

    @Slot(str, str, str, object)
    def _task_finished(
        self,
        task_id: str,
        repository_key: str,
        state: str,
        payload: object,
    ) -> None:
        self._active.pop(repository_key, None)
        if state == "succeeded":
            self.taskSucceeded.emit(task_id, payload)
        elif state == "cancelled":
            self.taskCancelled.emit(task_id)
        else:
            self.taskFailed.emit(task_id, payload)
        self._start_next(repository_key)
