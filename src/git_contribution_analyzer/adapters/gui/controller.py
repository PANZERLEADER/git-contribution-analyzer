from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot

from git_contribution_analyzer import __version__
from git_contribution_analyzer.adapters.gui.models.base_table import Column, DictTableModel
from git_contribution_analyzer.adapters.gui.settings import GuiSettings
from git_contribution_analyzer.adapters.gui.task_runner import RepositoryTaskRunner
from git_contribution_analyzer.application.dto.gui import (
    AssessmentRequest,
    ExportRequest,
    IdentityMapRequest,
    IdentityMergeRequest,
    ResumeRequest,
    StructuralBaselineRequest,
)
from git_contribution_analyzer.application.facades.gui import GuiApplicationFacade
from git_contribution_analyzer.application.ports.cancellation import CancellationToken
from git_contribution_analyzer.application.ports.progress import ProgressReporter

TaskCallable = Callable[[ProgressReporter, CancellationToken], Any]
SuccessCallback = Callable[[Any], None]


class GuiController(QObject):
    repositoryChanged = Signal()
    statusChanged = Signal()
    taskChanged = Signal()
    errorChanged = Signal()
    resultChanged = Signal()
    structuralChanged = Signal()
    recentChanged = Signal()
    notification = Signal(str)

    def __init__(
        self,
        *,
        facade: GuiApplicationFacade | None = None,
        task_runner: RepositoryTaskRunner | None = None,
        settings: GuiSettings | None = None,
    ) -> None:
        super().__init__()
        self._facade = facade or GuiApplicationFacade()
        self._runner = task_runner or RepositoryTaskRunner()
        self._settings = settings or GuiSettings()
        self._repository_path = ""
        self._status: dict[str, Any] = {}
        self._active_tasks: set[str] = set()
        self._task_stage = ""
        self._task_message = ""
        self._error_message = ""
        self._error_detail = ""
        self._current_run_id = ""
        self._completed_items = 0
        self._pending_items = 0
        self._current_report_json = ""
        self._callbacks: dict[str, SuccessCallback] = {}

        self._people_model = DictTableModel(
            columns=(
                Column("name", "Name"),
                Column("email", "Email"),
                Column("kind", "Kind"),
                Column("confirmed", "Confirmed"),
            )
        )
        self._work_items_model = DictTableModel(
            columns=(
                Column("id", "ID"),
                Column("title", "Work item"),
                Column("completion", "Completion"),
                Column("size", "Size"),
                Column("difficulty", "Difficulty"),
            )
        )
        self._evidence_model = DictTableModel(
            columns=(
                Column("id", "ID"),
                Column("type", "Type"),
                Column("summary", "Evidence"),
            )
        )
        self._runs_model = DictTableModel(
            columns=(
                Column("id", "Run ID"),
                Column("runType", "Type"),
                Column("status", "Status"),
                Column("startedAt", "Started"),
            )
        )
        self._trends_model = DictTableModel(
            columns=(
                Column("periodIndex", "Index"),
                Column("label", "Period"),
                Column("completedItems", "Completed"),
                Column("pendingItems", "Pending"),
                Column("commits", "Commits"),
            )
        )
        self._providers_model = DictTableModel(
            columns=(
                Column("id", "Provider"),
                Column("selected", "Selected"),
                Column("localExecution", "Local"),
                Column("requiresApiKey", "API key"),
            )
        )
        self._structural_hotspots_model = DictTableModel(
            columns=(
                Column("path", "Path"),
                Column("changeCount", "Changes"),
                Column("percentile", "Percentile"),
                Column("confidence", "Confidence"),
            )
        )
        self._structural_couplings_model = DictTableModel(
            columns=(
                Column("leftPath", "Left path"),
                Column("rightPath", "Right path"),
                Column("coChangeCount", "Co-changes"),
                Column("jaccard", "Jaccard"),
                Column("confidence", "Confidence"),
            )
        )

        self._runner.taskStarted.connect(self._task_started)
        self._runner.taskProgress.connect(self._task_progress)
        self._runner.taskSucceeded.connect(self._task_succeeded)
        self._runner.taskFailed.connect(self._task_failed)
        self._runner.taskCancelled.connect(self._task_cancelled)

    @Property(str, notify=repositoryChanged)
    def repositoryPath(self) -> str:
        return self._repository_path

    @Property(str, notify=repositoryChanged)
    def repositoryName(self) -> str:
        return Path(self._repository_path).name if self._repository_path else "No repository"

    @Property(str, constant=True)
    def appVersion(self) -> str:
        return __version__

    @Property(bool, constant=True)
    def chartsEnabled(self) -> bool:
        return os.environ.get("QT_QPA_PLATFORM", "").casefold() != "offscreen"

    @Property(bool, notify=statusChanged)
    def workspaceInitialized(self) -> bool:
        return bool(self._status.get("workspaceInitialized", False))

    @Property(bool, notify=statusChanged)
    def databaseHealthy(self) -> bool:
        return bool(self._status.get("databaseHealthy", False))

    @Property(str, notify=statusChanged)
    def indexStatus(self) -> str:
        return str(self._status.get("indexStatus", "not initialized"))

    @Property(int, notify=statusChanged)
    def indexedCommits(self) -> int:
        return int(self._status.get("indexedCommits", 0))

    @Property(int, notify=statusChanged)
    def identityCount(self) -> int:
        return int(self._status.get("identities", 0))

    @Property(int, notify=statusChanged)
    def unresolvedIdentityCount(self) -> int:
        return int(self._status.get("unresolvedIdentities", 0))

    @Property(int, notify=structuralChanged)
    def structuralBaselineCount(self) -> int:
        return int(self._structural_status().get("baselineCount", 0))

    @Property(str, notify=structuralChanged)
    def structuralLatestBaselineId(self) -> str:
        return str(self._structural_status().get("latestBaselineId") or "")

    @Property(int, notify=structuralChanged)
    def structuralProcessedCommits(self) -> int:
        return int(self._structural_status().get("processedCommits", 0))

    @Property(bool, notify=taskChanged)
    def busy(self) -> bool:
        return bool(self._active_tasks)

    @Property(str, notify=taskChanged)
    def taskStage(self) -> str:
        return self._task_stage

    @Property(str, notify=taskChanged)
    def taskMessage(self) -> str:
        return self._task_message

    @Property(str, notify=errorChanged)
    def errorMessage(self) -> str:
        return self._error_message

    @Property(str, notify=errorChanged)
    def errorDetail(self) -> str:
        return self._error_detail

    @Property(str, notify=resultChanged)
    def currentRunId(self) -> str:
        return self._current_run_id

    @Property(int, notify=resultChanged)
    def completedItems(self) -> int:
        return self._completed_items

    @Property(int, notify=resultChanged)
    def pendingItems(self) -> int:
        return self._pending_items

    @Property(str, notify=resultChanged)
    def currentReportJson(self) -> str:
        return self._current_report_json

    @Property(list, notify=recentChanged)
    def recentRepositories(self) -> list[str]:
        return self._settings.recent_repositories()

    @Property(QObject, constant=True)
    def peopleModel(self) -> QObject:
        return self._people_model

    @Property(QObject, constant=True)
    def workItemsModel(self) -> QObject:
        return self._work_items_model

    @Property(QObject, constant=True)
    def evidenceModel(self) -> QObject:
        return self._evidence_model

    @Property(QObject, constant=True)
    def runsModel(self) -> QObject:
        return self._runs_model

    @Property(QObject, constant=True)
    def trendsModel(self) -> QObject:
        return self._trends_model

    @Property(QObject, constant=True)
    def providersModel(self) -> QObject:
        return self._providers_model

    @Property(QObject, constant=True)
    def structuralHotspotsModel(self) -> QObject:
        return self._structural_hotspots_model

    @Property(QObject, constant=True)
    def structuralCouplingsModel(self) -> QObject:
        return self._structural_couplings_model

    @Slot(str)
    def openRepository(self, value: str) -> None:
        path = self._path_from_value(value)
        self._clear_error()
        self._submit(
            path,
            "open_repository",
            False,
            lambda reporter, token: self._facade.open_repository(path),
            lambda result: self._apply_open_repository(path, result),
        )

    @Slot()
    def initializeRepository(self) -> None:
        path = self._require_repository()
        if path is None:
            return
        self._submit(
            path,
            "initialize",
            True,
            lambda reporter, token: self._facade.initialize(
                path,
                progress=reporter,
                cancellation=token,
            ),
            lambda result: self._apply_status(result, "Workspace initialized"),
        )

    @Slot()
    def syncRepository(self) -> None:
        self._run_index(False)

    @Slot()
    def rebuildIndex(self) -> None:
        self._run_index(True)

    @Slot()
    def runDoctor(self) -> None:
        path = self._require_repository()
        if path is None:
            return
        self._submit(
            path,
            "doctor",
            False,
            lambda reporter, token: self._facade.doctor(path),
            lambda result: self._show_json_result(result, "Doctor completed"),
        )

    @Slot()
    def refreshStructural(self) -> None:
        path = self._require_repository()
        if path is None or not self.workspaceInitialized:
            return
        self._submit(
            path,
            "structural_status",
            False,
            lambda reporter, token: self._facade.structural_status(path),
            self._apply_structural_status,
        )

    @Slot("QVariantMap")
    def rebuildStructural(self, values: dict[str, Any]) -> None:
        path = self._require_repository()
        if path is None:
            return
        request = StructuralBaselineRequest(
            repository=path,
            cutoff_text=self._optional_text(values.get("cutoff")),
            branch=self._optional_text(values.get("branch")),
            scope=self._optional_text(values.get("scope")),
            time_strategy=str(values.get("timeStrategy", "lifetime")),
        )
        self._submit(
            path,
            "structural_rebuild",
            True,
            lambda reporter, token: self._facade.rebuild_structural(
                request,
                progress=reporter,
                cancellation=token,
            ),
            self._apply_structural_baseline,
        )

    @Slot(str)
    def showStructural(self, baseline_id: str) -> None:
        path = self._require_repository()
        if path is None:
            return
        target = baseline_id.strip() or str(
            self._structural_status().get("latestBaselineId") or ""
        )
        if not target:
            self.notification.emit("No structural baseline is available")
            return
        self._submit(
            path,
            "structural_show",
            False,
            lambda reporter, token: self._facade.show_structural(path, target),
            self._apply_structural_baseline,
        )

    @Slot(int)
    def pruneStructural(self, keep: int) -> None:
        path = self._require_repository()
        if path is None:
            return
        self._submit(
            path,
            "structural_prune",
            True,
            lambda reporter, token: self._facade.prune_structural(path, keep=keep),
            self._apply_structural_prune,
        )

    @Slot()
    def refreshIdentities(self) -> None:
        path = self._require_repository()
        if path is None or not self.workspaceInitialized:
            return
        self._submit(
            path,
            "identities",
            False,
            lambda reporter, token: self._facade.list_identities(path),
            self._apply_identities,
        )

    @Slot()
    def refreshRuns(self) -> None:
        path = self._require_repository()
        if path is None or not self.workspaceInitialized:
            return
        self._submit(
            path,
            "runs",
            False,
            lambda reporter, token: self._facade.list_runs(path),
            self._apply_runs,
        )

    @Slot()
    def refreshProviders(self) -> None:
        path = self._require_repository()
        if path is None or not self.workspaceInitialized:
            return
        self._submit(
            path,
            "providers",
            False,
            lambda reporter, token: self._facade.list_providers(path),
            self._apply_providers,
        )

    @Slot("QVariantMap")
    def runAssessment(self, values: dict[str, Any]) -> None:
        path = self._require_repository()
        if path is None:
            return
        request = AssessmentRequest(
            repository=path,
            person_selectors=tuple(str(item) for item in values.get("persons", [])),
            all_people=bool(values.get("allPeople", False)),
            exclude_selectors=tuple(str(item) for item in values.get("excludePersons", [])),
            rank_by=tuple(str(item) for item in values.get("rankBy", [])),
            since_text=self._optional_text(values.get("since")),
            until_text=self._optional_text(values.get("until")),
            period=self._optional_text(values.get("period")),
            branch=self._optional_text(values.get("branch")),
            release=self._optional_text(values.get("release")),
            scope=self._optional_text(values.get("scope")),
            delivery=self._optional_text(values.get("delivery")),
            time_basis=str(values.get("timeBasis", "authored")),
            use_llm=bool(values.get("useLlm", True)),
        )
        self._submit(
            path,
            "assess",
            True,
            lambda reporter, token: self._facade.assess(
                request,
                progress=reporter,
                cancellation=token,
            ),
            self._apply_report,
        )

    @Slot(str)
    def loadRun(self, run_id: str) -> None:
        path = self._require_repository()
        if path is None:
            return
        self._submit(
            path,
            "load_run",
            False,
            lambda reporter, token: self._facade.get_run(path, run_id),
            self._apply_report,
        )

    @Slot(str, str)
    def compareRuns(self, base_run_id: str, target_run_id: str) -> None:
        path = self._require_repository()
        if path is None:
            return
        self._submit(
            path,
            "compare_runs",
            False,
            lambda reporter, token: self._facade.compare_runs(path, base_run_id, target_run_id),
            lambda result: self._show_json_result(result, "Run comparison loaded"),
        )

    @Slot(str, str, str, bool, bool)
    def exportRun(
        self,
        run_id: str,
        report_format: str,
        target_value: str,
        include_email: bool,
        overwrite: bool,
    ) -> None:
        path = self._require_repository()
        if path is None:
            return
        request = ExportRequest(
            repository=path,
            run_id=run_id,
            report_format=report_format,
            target=self._path_from_value(target_value),
            include_email=include_email,
            overwrite=overwrite,
        )
        self._submit(
            path,
            "export",
            False,
            lambda reporter, token: self._facade.export_report(request),
            lambda result: self.notification.emit(f"Report written: {result}"),
        )

    @Slot(str, str, str, str)
    def mapIdentity(
        self,
        name: str,
        email: str,
        person_name: str,
        person_email: str,
    ) -> None:
        path = self._require_repository()
        if path is None:
            return
        request = IdentityMapRequest(
            repository=path,
            name=name,
            email=email,
            person_name=person_name,
            person_email=person_email,
        )
        self._submit(
            path,
            "map_identity",
            True,
            lambda reporter, token: self._facade.map_identity(request),
            lambda result: self._identity_changed("Identity mapped"),
        )

    @Slot(str, str, bool)
    def mergeIdentities(self, sources_text: str, target: str, preview_only: bool) -> None:
        path = self._require_repository()
        if path is None:
            return
        request = IdentityMergeRequest(
            repository=path,
            sources=self._split_values(sources_text),
            target=target.strip(),
        )
        operation_name = "preview_identity_merge" if preview_only else "merge_identities"

        def operation(reporter: ProgressReporter, token: CancellationToken) -> Any:
            del reporter, token
            if preview_only:
                return self._facade.preview_identity_merge(request)
            return self._facade.merge_identities(request)

        self._submit(
            path,
            operation_name,
            not preview_only,
            operation,
            lambda result: (
                self._show_json_result(result, "Merge preview loaded")
                if preview_only
                else self._identity_changed("Identities merged")
            ),
        )

    @Slot(str)
    def listIdentityMerges(self, status: str = "ALL") -> None:
        path = self._require_repository()
        if path is None:
            return
        self._submit(
            path,
            "list_identity_merges",
            False,
            lambda reporter, token: self._facade.list_identity_merges(path, status=status),
            lambda result: self._show_json_result(result, "Identity merge history loaded"),
        )

    @Slot(str)
    def unmergeIdentity(self, merge_id: str) -> None:
        path = self._require_repository()
        if path is None:
            return
        self._submit(
            path,
            "unmerge_identity",
            True,
            lambda reporter, token: self._facade.unmerge_identities(path, merge_id.strip()),
            lambda result: self._identity_changed("Identity merge reverted"),
        )

    @Slot("QVariantMap")
    def generateResume(self, values: dict[str, Any]) -> None:
        path = self._require_repository()
        if path is None:
            return
        request = ResumeRequest(
            repository=path,
            person_selector=str(values.get("person", "")),
            since_text=self._optional_text(values.get("since")),
            until_text=self._optional_text(values.get("until")),
            target_role=str(values.get("targetRole", "")),
            language=str(values.get("language", "zh-CN")),
            style=str(values.get("style", "concise")),
            max_bullets=int(values.get("maxBullets", 6)),
            include_pending=bool(values.get("includePending", False)),
            use_llm=bool(values.get("useLlm", True)),
        )
        self._submit(
            path,
            "resume",
            True,
            lambda reporter, token: self._facade.generate_resume(request),
            self._apply_report,
        )

    @Slot()
    def testProvider(self) -> None:
        path = self._require_repository()
        if path is None:
            return
        self._submit(
            path,
            "test_provider",
            False,
            lambda reporter, token: self._facade.test_provider(path),
            lambda result: self._show_json_result(result, "Provider check completed"),
        )

    @Slot(str)
    def cancelTask(self, task_id: str = "") -> None:
        target = task_id or next(iter(self._active_tasks), "")
        if target and self._runner.cancel(target):
            self._task_stage = "cancelling"
            self._task_message = "Waiting for a safe cancellation point"
            self.taskChanged.emit()

    @Slot()
    def clearError(self) -> None:
        self._clear_error()

    @Slot()
    def clearRecentRepositories(self) -> None:
        self._settings.clear_recent_repositories()
        self.recentChanged.emit()

    @Slot()
    def shutdown(self) -> None:
        self._runner.cancel_all()
        self._runner.wait_for_done(-1)

    def _run_index(self, full_rebuild: bool) -> None:
        path = self._require_repository()
        if path is None:
            return
        self._submit(
            path,
            "index" if full_rebuild else "sync",
            True,
            lambda reporter, token: self._facade.index(
                path,
                full_rebuild=full_rebuild,
                progress=reporter,
                cancellation=token,
            ),
            lambda result: self._refresh_status("Repository index updated"),
        )

    def _submit(
        self,
        repository: Path,
        operation_name: str,
        mutates_workspace: bool,
        operation: TaskCallable,
        success: SuccessCallback,
    ) -> None:
        self._clear_error()
        task_id = self._runner.submit(
            repository,
            operation_name,
            mutates_workspace=mutates_workspace,
            operation=operation,
        )
        self._callbacks[task_id] = success

    @Slot(str, str)
    def _task_started(self, task_id: str, operation_name: str) -> None:
        self._active_tasks.add(task_id)
        self._task_stage = operation_name
        self._task_message = operation_name.replace("_", " ").title()
        self.taskChanged.emit()

    @Slot(str, dict)
    def _task_progress(self, task_id: str, event: dict[str, Any]) -> None:
        if task_id not in self._active_tasks:
            return
        self._task_stage = str(event.get("stage", ""))
        self._task_message = str(event.get("message", ""))
        self.taskChanged.emit()

    @Slot(str, object)
    def _task_succeeded(self, task_id: str, payload: object) -> None:
        self._active_tasks.discard(task_id)
        callback = self._callbacks.pop(task_id, None)
        if callback is not None:
            callback(payload)
        self._finish_task_state()

    @Slot(str, object)
    def _task_failed(self, task_id: str, payload: object) -> None:
        self._active_tasks.discard(task_id)
        self._callbacks.pop(task_id, None)
        error = payload if isinstance(payload, Exception) else RuntimeError(str(payload))
        mapped = self._facade.map_error(error)
        self._error_message = f"{mapped.title}: {mapped.message}"
        self._error_detail = mapped.detail
        self.errorChanged.emit()
        self._finish_task_state()

    @Slot(str)
    def _task_cancelled(self, task_id: str) -> None:
        self._active_tasks.discard(task_id)
        self._callbacks.pop(task_id, None)
        self.notification.emit("Operation cancelled")
        self._finish_task_state()

    def _finish_task_state(self) -> None:
        if not self._active_tasks:
            self._task_stage = ""
            self._task_message = ""
        self.taskChanged.emit()

    def _apply_open_repository(self, path: Path, result: Any) -> None:
        self._repository_path = str(path.resolve())
        self._settings.remember_repository(path)
        self._status = dict(result)
        self.repositoryChanged.emit()
        self.statusChanged.emit()
        self.structuralChanged.emit()
        self.recentChanged.emit()
        if self.workspaceInitialized:
            self.refreshIdentities()
            self.refreshRuns()
            self.refreshProviders()

    def _apply_status(self, result: Any, message: str) -> None:
        self._status = dict(result)
        self.statusChanged.emit()
        self.structuralChanged.emit()
        self.notification.emit(message)
        self.refreshIdentities()
        self.refreshRuns()
        self.refreshProviders()

    def _refresh_status(self, message: str) -> None:
        path = self._require_repository()
        if path is None:
            return
        self._status = self._facade.status(path)
        self.statusChanged.emit()
        self.structuralChanged.emit()
        self.notification.emit(message)
        self.refreshIdentities()

    def _apply_identities(self, result: Any) -> None:
        self._people_model.set_rows(list(result.get("persons", [])))
        self._status["identities"] = int(result.get("count", 0))
        self.statusChanged.emit()

    def _apply_runs(self, result: Any) -> None:
        self._runs_model.set_rows(list(result.get("runs", [])))

    def _apply_providers(self, result: Any) -> None:
        self._providers_model.set_rows(list(result.get("providers", [])))

    def _apply_structural_status(self, result: Any) -> None:
        self._status["structural"] = dict(result)
        self.structuralChanged.emit()

    def _apply_structural_baseline(self, result: Any) -> None:
        data = dict(result)
        materialization = data.get("materialization", {})
        self._structural_hotspots_model.set_rows(list(materialization.get("hotspots", [])))
        self._structural_couplings_model.set_rows(
            list(materialization.get("couplings", []))
        )
        self._current_report_json = json.dumps(data, ensure_ascii=False, indent=2)
        self.resultChanged.emit()
        self.structuralChanged.emit()
        self.notification.emit("Structural observation loaded")
        self.refreshStructural()

    def _apply_structural_prune(self, result: Any) -> None:
        self._show_json_result(result, "Structural baselines pruned")
        self.refreshStructural()

    def _apply_report(self, report: Any) -> None:
        data = dict(report)
        run = data.get("run", {})
        self._current_run_id = str(run.get("id", ""))
        workload = data.get("workloadSummary", {})
        self._completed_items = int(workload.get("completedItems", 0))
        self._pending_items = int(workload.get("pendingItems", 0))
        self._work_items_model.set_rows(self._flatten_work_items(data))
        self._evidence_model.set_rows(list(data.get("evidence", [])))
        self._trends_model.set_rows(self._flatten_periods(data))
        self._current_report_json = json.dumps(data, ensure_ascii=False, indent=2)
        self.resultChanged.emit()
        self.notification.emit("Result loaded")
        self.refreshRuns()

    def _show_json_result(self, result: Any, message: str) -> None:
        self._current_report_json = json.dumps(result, ensure_ascii=False, indent=2)
        self.resultChanged.emit()
        self.notification.emit(message)

    def _identity_changed(self, message: str) -> None:
        self.notification.emit(message)
        self.refreshIdentities()

    def _require_repository(self) -> Path | None:
        if self._repository_path:
            return Path(self._repository_path)
        self._error_message = "Open a Git repository first"
        self._error_detail = ""
        self.errorChanged.emit()
        return None

    def _clear_error(self) -> None:
        if self._error_message or self._error_detail:
            self._error_message = ""
            self._error_detail = ""
            self.errorChanged.emit()

    def _structural_status(self) -> dict[str, Any]:
        value = self._status.get("structural", {})
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _path_from_value(value: str) -> Path:
        url = QUrl(value)
        return Path(url.toLocalFile()) if url.isLocalFile() else Path(value)

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        text = str(value or "").strip()
        return text or None

    @staticmethod
    def _split_values(value: str) -> tuple[str, ...]:
        return tuple(item.strip() for item in value.split(",") if item.strip())

    @staticmethod
    def _flatten_work_items(report: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in report.get("contributionItems", []):
            row = dict(item)
            assessment = row.get("assessment", {})
            if isinstance(assessment, dict):
                row.setdefault("completion", assessment.get("completion", ""))
                row.setdefault("size", assessment.get("size", ""))
                row.setdefault("difficulty", assessment.get("difficulty", ""))
            rows.append(row)
        for subject in report.get("subjects", []):
            person = subject.get("person", {})
            for assessment in subject.get("itemAssessments", []):
                size = assessment.get("size", {})
                difficulty = assessment.get("difficulty", {})
                item_id = str(assessment.get("contributionItemId", ""))
                rows.append(
                    {
                        "id": item_id,
                        "title": item_id,
                        "person": person.get("name", ""),
                        "completion": assessment.get("completionBucket", ""),
                        "size": size.get("band", "") if isinstance(size, dict) else size,
                        "difficulty": (
                            difficulty.get("level", "")
                            if isinstance(difficulty, dict)
                            else difficulty
                        ),
                        "evidenceIds": assessment.get("evidenceIds", []),
                    }
                )
        return rows

    @staticmethod
    def _flatten_periods(report: dict[str, Any]) -> list[dict[str, Any]]:
        rows = []
        for index, period in enumerate(report.get("periods", []), start=1):
            row = dict(period)
            row["periodIndex"] = index
            metrics = period.get("metrics", {})
            if isinstance(metrics, dict):
                row.update(metrics)
            rows.append(row)
        return rows
