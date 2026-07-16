from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from git_contribution_analyzer.adapters.git.native_git import NativeGitHistory
from git_contribution_analyzer.adapters.git.repository_discovery import discover_repository
from git_contribution_analyzer.adapters.storage.sqlite.database import initialize_database
from git_contribution_analyzer.adapters.storage.sqlite.structural_baseline import (
    SqliteStructuralBaselineStore,
)
from git_contribution_analyzer.adapters.workspace.config import load_config
from git_contribution_analyzer.adapters.workspace.layout import WorkspaceLayout
from git_contribution_analyzer.adapters.workspace.locks import workspace_lock
from git_contribution_analyzer.application.ports.cancellation import (
    CancellationToken,
    NeverCancelledToken,
    OperationCancelled,
)
from git_contribution_analyzer.application.ports.progress import (
    NullProgressReporter,
    ProgressEvent,
    ProgressReporter,
)
from git_contribution_analyzer.application.ports.structural_baseline import (
    StructuralBaselineStore,
)
from git_contribution_analyzer.domain.errors import WorkspaceError
from git_contribution_analyzer.domain.models.structural_baseline import (
    StructuralRuleConfig,
    StructuralTimeStrategy,
)
from git_contribution_analyzer.domain.services.structural_baseline import (
    build_structural_baseline,
)


def rebuild_structural_baseline(
    path: Path,
    *,
    cutoff: datetime,
    branch: str | None = None,
    scope: str | None = None,
    time_strategy: StructuralTimeStrategy | None = None,
    progress: ProgressReporter | None = None,
    cancellation: CancellationToken | None = None,
) -> dict[str, Any]:
    active_progress = progress or NullProgressReporter()
    active_cancellation = cancellation or NeverCancelledToken()
    active_cancellation.raise_if_cancelled()
    repository = discover_repository(path)
    task_id = str(uuid4())
    layout = WorkspaceLayout.for_repository(repository.root)
    if not layout.root.is_dir():
        raise WorkspaceError("GCA workspace is not initialized; run 'gca init' first")
    initialize_database(layout.database)
    config = load_config(layout.config)
    actual_branch = branch or config.default_branch
    target_ref = (
        actual_branch
        if actual_branch.startswith("refs/")
        else f"refs/heads/{actual_branch}"
    )
    history = NativeGitHistory(repository.root)
    try:
        allowed_hashes = set(history.reachable_commits(target_ref))
    except Exception as exc:
        raise WorkspaceError(f"Unable to resolve structural target ref: {target_ref}") from exc
    store: StructuralBaselineStore = SqliteStructuralBaselineStore(
        layout.database,
        str(repository.root),
    )
    active_config = config.structural.to_rule_config(time_strategy=time_strategy)
    fingerprint = _filter_fingerprint(target_ref, scope, active_config)
    with workspace_lock(layout.locks / "workspace.lock"):
        active_cancellation.raise_if_cancelled()
        baseline_commit = store.latest_fact_commit(
            allowed_hashes=allowed_hashes,
            cutoff=cutoff,
            scope=scope,
        )
        cached = store.find_completed(
            branch=target_ref,
            scope=scope,
            cutoff=cutoff,
            baseline_commit=baseline_commit,
            filter_fingerprint=fingerprint,
            time_strategy=active_config.time_strategy.value,
        )
        if cached is not None:
            active_progress.report(
                ProgressEvent(
                    task_id=task_id,
                    operation="structural_rebuild",
                    stage="completed",
                    repository=repository.root,
                    current=1,
                    total=1,
                    message="Structural baseline cache hit",
                    occurred_at=datetime.now(UTC),
                )
            )
            return cached
        diagnostic_id = _diagnostic_id(task_id)
        store.begin_baseline(
            diagnostic_id,
            branch=target_ref,
            scope=scope,
            cutoff=cutoff,
            baseline_commit=baseline_commit,
            filter_fingerprint=fingerprint,
            config=active_config,
        )
        try:
            active_progress.report(
                _event(task_id, repository.root, "reading_facts", "Reading structural facts")
            )
            commits = store.load_commits(
                allowed_hashes=allowed_hashes,
                cutoff=cutoff,
                scope=scope,
            )
            active_cancellation.raise_if_cancelled()
            active_progress.report(
                _event(task_id, repository.root, "building_baseline", "Building baseline")
            )
            baseline = build_structural_baseline(
                commits,
                cutoff=cutoff,
                config=active_config,
                identity_context={
                    "repositoryId": store.repository_id(),
                    "branch": target_ref,
                    "scope": scope,
                },
            )
            active_cancellation.raise_if_cancelled()
            active_progress.report(
                _event(task_id, repository.root, "publishing_baseline", "Publishing baseline")
            )
            result = store.save_baseline(
                baseline,
                branch=target_ref,
                scope=scope,
                baseline_commit=baseline_commit,
                filter_fingerprint=fingerprint,
                diagnostic_id=diagnostic_id,
            )
        except OperationCancelled as exc:
            store.finish_baseline(
                diagnostic_id,
                status="CANCELLED",
                error_message=type(exc).__name__,
            )
            raise OperationCancelled(
                f"Operation cancelled; structural diagnostic: {diagnostic_id}"
            ) from exc
        except Exception as exc:
            store.finish_baseline(
                diagnostic_id,
                status="FAILED",
                error_message=type(exc).__name__,
            )
            raise WorkspaceError(
                f"Structural baseline build failed; diagnostic: {diagnostic_id}"
            ) from exc
    active_progress.report(
        ProgressEvent(
            task_id=task_id,
            operation="structural_rebuild",
            stage="completed",
            repository=repository.root,
            current=1,
            total=1,
            message="Structural baseline rebuilt",
            occurred_at=datetime.now(UTC),
        )
    )
    return result


def get_structural_status(path: Path) -> dict[str, Any]:
    repository = discover_repository(path)
    layout = WorkspaceLayout.for_repository(repository.root)
    if not layout.root.is_dir():
        raise WorkspaceError("GCA workspace is not initialized; run 'gca init' first")
    initialize_database(layout.database)
    return SqliteStructuralBaselineStore(
        layout.database, str(repository.root)
    ).status()


def show_structural_baseline(path: Path, baseline_id: str) -> dict[str, Any]:
    repository = discover_repository(path)
    layout = WorkspaceLayout.for_repository(repository.root)
    if not layout.root.is_dir():
        raise WorkspaceError("GCA workspace is not initialized; run 'gca init' first")
    initialize_database(layout.database)
    result = SqliteStructuralBaselineStore(
        layout.database, str(repository.root)
    ).show(baseline_id)
    if result is None:
        raise WorkspaceError(f"Structural baseline not found: {baseline_id}")
    return result


def prune_structural_baselines(path: Path, *, keep: int) -> dict[str, int]:
    repository = discover_repository(path)
    layout = WorkspaceLayout.for_repository(repository.root)
    if not layout.root.is_dir():
        raise WorkspaceError("GCA workspace is not initialized; run 'gca init' first")
    initialize_database(layout.database)
    with workspace_lock(layout.locks / "workspace.lock"):
        return SqliteStructuralBaselineStore(
            layout.database, str(repository.root)
        ).prune(keep)


def _filter_fingerprint(
    branch: str,
    scope: str | None,
    config: StructuralRuleConfig,
) -> str:
    payload = {
        "branch": branch,
        "scope": scope,
        "timeStrategy": config.time_strategy.value,
        "minimumBaselineCommits": config.minimum_baseline_commits,
        "hotspotPercentile": config.hotspot_percentile,
        "minimumCoChangeCount": config.minimum_co_change_count,
        "minimumSubsetRatio": config.minimum_subset_ratio,
        "minimumJaccard": config.minimum_jaccard,
        "minimumHubPenalty": config.minimum_hub_penalty,
        "maximumContextPaths": config.maximum_context_paths,
        "rollingWindowDays": config.rolling_window_days,
        "generatedRule": "contribution-generated-v1",
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def default_structural_cutoff() -> datetime:
    return datetime.now(UTC)


def _diagnostic_id(task_id: str) -> str:
    return hashlib.sha256(task_id.encode("ascii")).hexdigest()


def _event(task_id: str, repository: Path, stage: str, message: str) -> ProgressEvent:
    return ProgressEvent(
        task_id=task_id,
        operation="structural_rebuild",
        stage=stage,
        repository=repository,
        message=message,
        occurred_at=datetime.now(UTC),
    )
