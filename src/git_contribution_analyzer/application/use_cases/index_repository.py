from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from git_contribution_analyzer.adapters.git.native_git import NativeGitHistory
from git_contribution_analyzer.adapters.git.repository_discovery import discover_repository
from git_contribution_analyzer.adapters.storage.sqlite.git_index import SqliteGitIndexStore
from git_contribution_analyzer.adapters.workspace.config import load_config
from git_contribution_analyzer.adapters.workspace.layout import WorkspaceLayout
from git_contribution_analyzer.adapters.workspace.locks import workspace_lock
from git_contribution_analyzer.application.ports.cancellation import (
    CancellationToken,
    NeverCancelledToken,
)
from git_contribution_analyzer.application.ports.progress import (
    NullProgressReporter,
    ProgressEvent,
    ProgressReporter,
)
from git_contribution_analyzer.domain.errors import WorkspaceError
from git_contribution_analyzer.domain.models.git_history import CommitDelivery, GitCommit


def index_repository(
    path: Path,
    *,
    full_rebuild: bool,
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
    config = load_config(layout.config)
    history = NativeGitHistory(repository.root)
    store = SqliteGitIndexStore(layout.database, str(repository.root))

    with workspace_lock(layout.locks / "workspace.lock"):
        active_cancellation.raise_if_cancelled()
        active_progress.report(
            _event(task_id, repository.root, "reading_commits", "Reading Git commits")
        )
        all_hashes = history.list_commit_hashes()
        existing = set() if full_rebuild else store.existing_commit_hashes()
        new_hashes = tuple(commit_hash for commit_hash in all_hashes if commit_hash not in existing)
        new_commits = history.read_commits(new_hashes)

        active_cancellation.raise_if_cancelled()
        active_progress.report(
            _event(
                task_id,
                repository.root,
                "resolving_delivery",
                "Resolving delivery status",
            )
        )
        existing_relations = [] if full_rebuild else store.relation_summaries()
        relation_rows = existing_relations + [_relation_row(commit) for commit in new_commits]
        deliveries = _resolve_delivery(history, relation_rows, config.default_branch)
        git_refs = history.list_refs()
        active_cancellation.raise_if_cancelled()
        active_progress.report(
            _event(task_id, repository.root, "writing_index", "Writing repository index")
        )
        store.write_index(
            git_refs,
            new_commits,
            deliveries,
            clear_existing=full_rebuild,
        )
        stats = store.stats()
        _update_metadata(layout, stats, git_refs, config.default_branch)

    result = {
        **stats,
        "newCommits": len(new_commits),
        "targetRef": f"refs/heads/{config.default_branch}",
        "indexStatus": "up-to-date",
    }
    active_progress.report(
        ProgressEvent(
            task_id=task_id,
            operation="index" if full_rebuild else "sync",
            stage="completed",
            repository=repository.root,
            current=1,
            total=1,
            message="Repository index updated",
            occurred_at=datetime.now(UTC),
        )
    )
    return result


def _event(task_id: str, repository: Path, stage: str, message: str) -> ProgressEvent:
    return ProgressEvent(
        task_id=task_id,
        operation="index",
        stage=stage,
        repository=repository,
        message=message,
        occurred_at=datetime.now(UTC),
    )


def _relation_row(commit: GitCommit) -> dict[str, Any]:
    return {
        "hash": commit.hash,
        "patch_id": commit.patch_id,
        "reverts_hash": commit.reverts_hash,
    }


def _resolve_delivery(
    history: NativeGitHistory,
    relations: list[dict[str, Any]],
    default_branch: str,
) -> tuple[CommitDelivery, ...]:
    target_ref = f"refs/heads/{default_branch}"
    hashes = tuple(str(row["hash"]) for row in relations)
    landed_hashes = history.reachable_commits(target_ref).intersection(hashes)
    release_tags = history.first_release_tags(landed_hashes)
    deliveries: dict[str, CommitDelivery] = {}
    for row in relations:
        commit_hash = str(row["hash"])
        landed = commit_hash in landed_hashes
        release_ref = release_tags.get(commit_hash)
        status = "RELEASED" if release_ref else "LANDED" if landed else "AUTHORED_ONLY"
        deliveries[commit_hash] = CommitDelivery(
            commit_hash=commit_hash,
            target_ref=target_ref,
            status=status,
            release_ref=release_ref,
        )

    delivered_by_patch: dict[str, str] = {}
    for row in relations:
        patch_id = row.get("patch_id")
        delivery = deliveries[str(row["hash"])]
        if patch_id and delivery.status in {"LANDED", "RELEASED"}:
            delivered_by_patch.setdefault(str(patch_id), delivery.commit_hash)
    for row in relations:
        patch_id = row.get("patch_id")
        commit_hash = str(row["hash"])
        duplicate = delivered_by_patch.get(str(patch_id)) if patch_id else None
        if (
            duplicate
            and duplicate != commit_hash
            and deliveries[commit_hash].status == "AUTHORED_ONLY"
        ):
            current = deliveries[commit_hash]
            deliveries[commit_hash] = CommitDelivery(
                commit_hash=commit_hash,
                target_ref=target_ref,
                status=current.status,
                release_ref=current.release_ref,
                related_commit_hash=duplicate,
            )

    for row in relations:
        reverted_prefix = row.get("reverts_hash")
        revert_hash = str(row["hash"])
        if not reverted_prefix or deliveries[revert_hash].status not in {"LANDED", "RELEASED"}:
            continue
        reverted_hash = next(
            (commit_hash for commit_hash in hashes if commit_hash.startswith(str(reverted_prefix))),
            None,
        )
        if reverted_hash is None:
            continue
        current = deliveries[reverted_hash]
        deliveries[reverted_hash] = CommitDelivery(
            commit_hash=reverted_hash,
            target_ref=target_ref,
            status="REVERTED",
            release_ref=current.release_ref,
            related_commit_hash=revert_hash,
        )
    return tuple(deliveries[commit_hash] for commit_hash in hashes)


def _update_metadata(
    layout: WorkspaceLayout,
    stats: dict[str, int],
    git_refs: tuple[Any, ...],
    default_branch: str,
) -> None:
    metadata = json.loads(layout.metadata.read_text(encoding="utf-8"))
    target_ref = f"refs/heads/{default_branch}"
    indexed_commit = next(
        (git_ref.commit_hash for git_ref in git_refs if git_ref.name == target_ref),
        None,
    )
    metadata.update(
        {
            "indexedCommit": indexed_commit,
            "indexedCommits": stats["indexedCommits"],
            "identities": stats["identities"],
            "unresolvedIdentities": stats["unresolvedIdentities"],
            "refs": stats["refs"],
            "lastSync": datetime.now(UTC).isoformat(),
            "indexStatus": "up-to-date",
        }
    )
    layout.metadata.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
