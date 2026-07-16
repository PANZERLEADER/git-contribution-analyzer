from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from git_contribution_analyzer.adapters.storage.sqlite.database import create_database_engine
from git_contribution_analyzer.adapters.storage.sqlite.models import (
    commits,
    repositories,
    structural_baselines,
    structural_commit_facts,
    structural_edge_counts,
    structural_edge_occurrences,
    structural_file_counts,
    structural_file_occurrences,
    structural_materializations,
)
from git_contribution_analyzer.domain.errors import WorkspaceError
from git_contribution_analyzer.domain.models.contribution import ContributionCommit
from git_contribution_analyzer.domain.models.git_history import GitCommit
from git_contribution_analyzer.domain.models.structural_baseline import (
    StructuralBaseline,
    StructuralRuleConfig,
)
from git_contribution_analyzer.domain.services.contribution_rules import is_generated_path
from git_contribution_analyzer.domain.services.structural_baseline import (
    STRUCTURAL_FACT_RULE_VERSION,
    STRUCTURAL_METRIC_RULE_VERSION,
    STRUCTURAL_THRESHOLD_VERSION,
)


class SqliteStructuralBaselineStore:
    def __init__(self, database_path: Path, repository_root: str) -> None:
        self.database_path = database_path
        self.repository_root = repository_root

    def repository_id(self) -> str:
        engine = create_database_engine(self.database_path)
        try:
            with engine.connect() as connection:
                value = connection.execute(
                    select(repositories.c.id).where(
                        repositories.c.root_path == self.repository_root
                    )
                ).scalar_one_or_none()
                if value is None:
                    raise WorkspaceError(f"Repository is not registered: {self.repository_root}")
                return str(value)
        finally:
            engine.dispose()

    def sync_commit_facts(
        self,
        git_commits: Iterable[GitCommit],
        *,
        clear_existing: bool,
        maximum_context_paths: int = 200,
    ) -> dict[str, int]:
        engine = create_database_engine(self.database_path)
        inserted_commits = 0
        inserted_files = 0
        inserted_edges = 0
        try:
            with engine.begin() as connection:
                repository_id = connection.execute(
                    select(repositories.c.id).where(
                        repositories.c.root_path == self.repository_root
                    )
                ).scalar_one()
                if clear_existing:
                    connection.execute(
                        delete(structural_baselines).where(
                            structural_baselines.c.repository_id == repository_id
                        )
                    )
                    connection.execute(
                        delete(structural_commit_facts).where(
                            structural_commit_facts.c.repository_id == repository_id
                        )
                    )
                for commit in git_commits:
                    paths, excluded_reason = _eligible_git_paths(commit)
                    capped = len(paths) > maximum_context_paths
                    edges = () if capped else tuple(combinations(paths, 2))
                    statement = sqlite_insert(structural_commit_facts).values(
                        repository_id=repository_id,
                        commit_hash=commit.hash,
                        fact_rule_version=STRUCTURAL_FACT_RULE_VERSION,
                        occurred_at=commit.committed_at.astimezone(UTC),
                        path_count=len(paths),
                        edge_count=len(edges),
                        context_capped=capped,
                        excluded_reason=excluded_reason,
                    )
                    result = connection.execute(
                        statement.on_conflict_do_nothing(
                            index_elements=[
                                structural_commit_facts.c.repository_id,
                                structural_commit_facts.c.commit_hash,
                                structural_commit_facts.c.fact_rule_version,
                            ]
                        )
                    )
                    if result.rowcount == 0:
                        continue
                    inserted_commits += 1
                    if paths:
                        connection.execute(
                            insert(structural_file_occurrences),
                            [
                                {
                                    "repository_id": repository_id,
                                    "commit_hash": commit.hash,
                                    "fact_rule_version": STRUCTURAL_FACT_RULE_VERSION,
                                    "path": path,
                                }
                                for path in paths
                            ],
                        )
                        inserted_files += len(paths)
                    if edges:
                        connection.execute(
                            insert(structural_edge_occurrences),
                            [
                                {
                                    "repository_id": repository_id,
                                    "commit_hash": commit.hash,
                                    "fact_rule_version": STRUCTURAL_FACT_RULE_VERSION,
                                    "left_path": left,
                                    "right_path": right,
                                }
                                for left, right in edges
                            ],
                        )
                        inserted_edges += len(edges)
        finally:
            engine.dispose()
        return {
            "processedCommits": inserted_commits,
            "fileOccurrences": inserted_files,
            "edgeOccurrences": inserted_edges,
        }

    def load_commits(
        self,
        *,
        allowed_hashes: set[str],
        cutoff: datetime,
        scope: str | None,
    ) -> tuple[ContributionCommit, ...]:
        engine = create_database_engine(self.database_path)
        try:
            with engine.connect() as connection:
                repository_id = connection.execute(
                    select(repositories.c.id).where(
                        repositories.c.root_path == self.repository_root
                    )
                ).scalar_one()
                rows = connection.execute(
                    select(
                        structural_commit_facts.c.commit_hash,
                        structural_commit_facts.c.occurred_at,
                        structural_commit_facts.c.context_capped,
                        commits.c.subject,
                        commits.c.is_merge,
                        commits.c.patch_id,
                    )
                    .join(
                        commits,
                        (commits.c.repository_id == structural_commit_facts.c.repository_id)
                        & (commits.c.hash == structural_commit_facts.c.commit_hash),
                    )
                    .where(
                        structural_commit_facts.c.repository_id == repository_id,
                        structural_commit_facts.c.fact_rule_version
                        == STRUCTURAL_FACT_RULE_VERSION,
                        structural_commit_facts.c.occurred_at < cutoff.astimezone(UTC),
                    )
                    .order_by(
                        structural_commit_facts.c.occurred_at,
                        structural_commit_facts.c.commit_hash,
                    )
                ).mappings()
                selected = [row for row in rows if str(row["commit_hash"]) in allowed_hashes]
                hashes = tuple(str(row["commit_hash"]) for row in selected)
                path_rows = connection.execute(
                    select(
                        structural_file_occurrences.c.commit_hash,
                        structural_file_occurrences.c.path,
                    ).where(
                        structural_file_occurrences.c.repository_id == repository_id,
                        structural_file_occurrences.c.fact_rule_version
                        == STRUCTURAL_FACT_RULE_VERSION,
                    )
                )
                paths_by_commit: dict[str, list[str]] = {value: [] for value in hashes}
                normalized_scope = scope.replace("\\", "/").strip("/") if scope else None
                for commit_hash, path in path_rows:
                    actual_hash = str(commit_hash)
                    actual_path = str(path)
                    if actual_hash not in paths_by_commit:
                        continue
                    if normalized_scope and not (
                        actual_path == normalized_scope
                        or actual_path.startswith(f"{normalized_scope}/")
                    ):
                        continue
                    paths_by_commit[actual_hash].append(actual_path)
        finally:
            engine.dispose()

        result: list[ContributionCommit] = []
        for row in selected:
            commit_hash = str(row["commit_hash"])
            paths = tuple(sorted(set(paths_by_commit[commit_hash])))
            if not paths:
                continue
            occurred_at = _aware_utc(row["occurred_at"])
            result.append(
                ContributionCommit(
                    hash=commit_hash,
                    subject=str(row["subject"]),
                    authored_at=occurred_at,
                    commit_type="STRUCTURAL_FACT",
                    delivery_status="LANDED",
                    paths=paths,
                    modules=tuple(sorted({_module(path) for path in paths})),
                    insertions=1,
                    deletions=0,
                    files_changed=len(paths),
                    merge=bool(row["is_merge"]),
                    binary_files=0,
                    generated_files=0,
                    patch_id=str(row["patch_id"]) if row["patch_id"] else None,
                    period_at=occurred_at,
                )
            )
        return tuple(result)

    def latest_fact_commit(
        self,
        *,
        allowed_hashes: set[str],
        cutoff: datetime,
        scope: str | None,
    ) -> str | None:
        engine = create_database_engine(self.database_path)
        try:
            with engine.connect() as connection:
                repository_id = connection.execute(
                    select(repositories.c.id).where(
                        repositories.c.root_path == self.repository_root
                    )
                ).scalar_one()
                normalized_scope = scope.replace("\\", "/").strip("/") if scope else None
                statement = (
                    select(
                        structural_commit_facts.c.commit_hash,
                        structural_commit_facts.c.occurred_at,
                    )
                    .join(
                        structural_file_occurrences,
                        (
                            structural_file_occurrences.c.repository_id
                            == structural_commit_facts.c.repository_id
                        )
                        & (
                            structural_file_occurrences.c.commit_hash
                            == structural_commit_facts.c.commit_hash
                        )
                        & (
                            structural_file_occurrences.c.fact_rule_version
                            == structural_commit_facts.c.fact_rule_version
                        ),
                    )
                    .where(
                        structural_commit_facts.c.repository_id == repository_id,
                        structural_commit_facts.c.fact_rule_version
                        == STRUCTURAL_FACT_RULE_VERSION,
                        structural_commit_facts.c.occurred_at < cutoff.astimezone(UTC),
                    )
                )
                if normalized_scope:
                    statement = statement.where(
                        (structural_file_occurrences.c.path == normalized_scope)
                        | structural_file_occurrences.c.path.startswith(
                            f"{normalized_scope}/"
                        )
                    )
                rows = connection.execute(
                    statement.distinct().order_by(
                        structural_commit_facts.c.occurred_at.desc(),
                        structural_commit_facts.c.commit_hash.desc(),
                    )
                )
                for commit_hash, _occurred_at in rows:
                    value = str(commit_hash)
                    if value in allowed_hashes:
                        return value
                return None
        finally:
            engine.dispose()

    def save_baseline(
        self,
        baseline: StructuralBaseline,
        *,
        branch: str,
        scope: str | None,
        baseline_commit: str | None,
        filter_fingerprint: str,
        diagnostic_id: str | None = None,
    ) -> dict[str, Any]:
        payload = serialize_baseline(
            baseline,
            branch=branch,
            scope=scope,
            baseline_commit=baseline_commit,
            status="COMPLETED",
        )
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        content_hash = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        engine = create_database_engine(self.database_path)
        try:
            with engine.begin() as connection:
                repository_id = connection.execute(
                    select(repositories.c.id).where(
                        repositories.c.root_path == self.repository_root
                    )
                ).scalar_one()
                if diagnostic_id is not None:
                    connection.execute(
                        delete(structural_baselines).where(
                            structural_baselines.c.id == diagnostic_id
                        )
                    )
                connection.execute(
                    delete(structural_baselines).where(structural_baselines.c.id == baseline.id)
                )
                connection.execute(
                    insert(structural_baselines).values(
                        id=baseline.id,
                        repository_id=repository_id,
                        baseline_commit=baseline_commit,
                        cutoff_at=baseline.cutoff.astimezone(UTC),
                        branch=branch,
                        scope=scope,
                        filter_fingerprint=filter_fingerprint,
                        time_strategy=baseline.config.time_strategy.value,
                        fact_rule_version=STRUCTURAL_FACT_RULE_VERSION,
                        metric_rule_version=STRUCTURAL_METRIC_RULE_VERSION,
                        threshold_version=STRUCTURAL_THRESHOLD_VERSION,
                        status="COMPLETED",
                        eligible_commit_count=baseline.summary.eligible_commits,
                        eligible_file_count=baseline.summary.eligible_files,
                        raw_edge_count=baseline.summary.raw_edges,
                        completed_at=datetime.now(UTC),
                    )
                )
                if baseline.file_counts:
                    connection.execute(
                        insert(structural_file_counts),
                        [
                            {
                                "baseline_id": baseline.id,
                                "path": value.path,
                                "change_count": value.change_count,
                                "recent_change_count": value.recent_change_count,
                            }
                            for value in baseline.file_counts
                        ],
                    )
                if baseline.edge_counts:
                    connection.execute(
                        insert(structural_edge_counts),
                        [
                            {
                                "baseline_id": baseline.id,
                                "left_path": value.left_path,
                                "right_path": value.right_path,
                                "co_change_count": value.co_change_count,
                                "recent_co_change_count": value.recent_co_change_count,
                            }
                            for value in baseline.edge_counts
                        ],
                    )
                connection.execute(
                    insert(structural_materializations).values(
                        baseline_id=baseline.id,
                        metric_rule_version=STRUCTURAL_METRIC_RULE_VERSION,
                        threshold_version=STRUCTURAL_THRESHOLD_VERSION,
                        content_hash=content_hash,
                        result_json=encoded,
                    )
                )
        finally:
            engine.dispose()
        return payload

    def begin_baseline(
        self,
        build_id: str,
        *,
        branch: str,
        scope: str | None,
        cutoff: datetime,
        baseline_commit: str | None,
        filter_fingerprint: str,
        config: StructuralRuleConfig,
    ) -> None:
        engine = create_database_engine(self.database_path)
        try:
            with engine.begin() as connection:
                repository_id = connection.execute(
                    select(repositories.c.id).where(
                        repositories.c.root_path == self.repository_root
                    )
                ).scalar_one()
                connection.execute(
                    insert(structural_baselines).values(
                        id=build_id,
                        repository_id=repository_id,
                        baseline_commit=baseline_commit,
                        cutoff_at=cutoff.astimezone(UTC),
                        branch=branch,
                        scope=scope,
                        filter_fingerprint=filter_fingerprint,
                        time_strategy=config.time_strategy.value,
                        fact_rule_version=STRUCTURAL_FACT_RULE_VERSION,
                        metric_rule_version=STRUCTURAL_METRIC_RULE_VERSION,
                        threshold_version=STRUCTURAL_THRESHOLD_VERSION,
                        status="BUILDING",
                        eligible_commit_count=0,
                        eligible_file_count=0,
                        raw_edge_count=0,
                    )
                )
        finally:
            engine.dispose()

    def finish_baseline(
        self,
        build_id: str,
        *,
        status: str,
        error_message: str,
    ) -> None:
        if status not in {"FAILED", "CANCELLED"}:
            raise ValueError(f"Unsupported diagnostic status: {status}")
        engine = create_database_engine(self.database_path)
        try:
            with engine.begin() as connection:
                connection.execute(
                    update(structural_baselines)
                    .where(structural_baselines.c.id == build_id)
                    .values(
                        status=status,
                        error_message=error_message,
                        completed_at=datetime.now(UTC),
                    )
                )
        finally:
            engine.dispose()

    def mark_stale(self, baseline_ids: Iterable[str]) -> int:
        ids = tuple(sorted(set(baseline_ids)))
        if not ids:
            return 0
        engine = create_database_engine(self.database_path)
        try:
            with engine.begin() as connection:
                result = connection.execute(
                    update(structural_baselines)
                    .where(
                        structural_baselines.c.id.in_(ids),
                        structural_baselines.c.status == "COMPLETED",
                    )
                    .values(status="STALE")
                )
                return int(result.rowcount or 0)
        finally:
            engine.dispose()

    def find_completed(
        self,
        *,
        branch: str,
        scope: str | None,
        cutoff: datetime,
        baseline_commit: str | None,
        filter_fingerprint: str,
        time_strategy: str,
    ) -> dict[str, Any] | None:
        engine = create_database_engine(self.database_path)
        try:
            with engine.connect() as connection:
                repository_id = connection.execute(
                    select(repositories.c.id).where(
                        repositories.c.root_path == self.repository_root
                    )
                ).scalar_one()
                scope_filter = (
                    structural_baselines.c.scope.is_(None)
                    if scope is None
                    else structural_baselines.c.scope == scope
                )
                rows = connection.execute(
                    select(
                        structural_baselines.c.baseline_commit,
                        structural_materializations.c.result_json,
                    )
                    .join(
                        structural_materializations,
                        structural_materializations.c.baseline_id
                        == structural_baselines.c.id,
                    )
                    .where(
                        structural_baselines.c.repository_id == repository_id,
                        structural_baselines.c.status == "COMPLETED",
                        structural_baselines.c.branch == branch,
                        scope_filter,
                        structural_baselines.c.cutoff_at == cutoff.astimezone(UTC),
                        structural_baselines.c.filter_fingerprint == filter_fingerprint,
                        structural_baselines.c.time_strategy == time_strategy,
                        structural_baselines.c.fact_rule_version
                        == STRUCTURAL_FACT_RULE_VERSION,
                        structural_baselines.c.metric_rule_version
                        == STRUCTURAL_METRIC_RULE_VERSION,
                        structural_baselines.c.threshold_version
                        == STRUCTURAL_THRESHOLD_VERSION,
                    )
                    .order_by(structural_baselines.c.completed_at.desc())
                )
                for stored_baseline_commit, encoded in rows:
                    commit = (
                        str(stored_baseline_commit) if stored_baseline_commit else None
                    )
                    if commit == baseline_commit:
                        return dict(json.loads(str(encoded)))
                return None
        finally:
            engine.dispose()

    def show(self, baseline_id: str) -> dict[str, Any] | None:
        engine = create_database_engine(self.database_path)
        try:
            with engine.connect() as connection:
                repository_id = connection.execute(
                    select(repositories.c.id).where(
                        repositories.c.root_path == self.repository_root
                    )
                ).scalar_one()
                value = connection.execute(
                    select(structural_materializations.c.result_json)
                    .join(
                        structural_baselines,
                        structural_baselines.c.id == structural_materializations.c.baseline_id,
                    )
                    .where(
                        structural_baselines.c.repository_id == repository_id,
                        structural_materializations.c.baseline_id == baseline_id,
                    )
                ).scalar_one_or_none()
                return dict(json.loads(str(value))) if value else None
        finally:
            engine.dispose()

    def status(self) -> dict[str, Any]:
        engine = create_database_engine(self.database_path)
        try:
            with engine.connect() as connection:
                repository_id = connection.execute(
                    select(repositories.c.id).where(
                        repositories.c.root_path == self.repository_root
                    )
                ).scalar_one()
                count = int(
                    connection.execute(
                        select(func.count()).select_from(structural_baselines).where(
                            structural_baselines.c.repository_id == repository_id,
                            structural_baselines.c.status == "COMPLETED",
                        )
                    ).scalar_one()
                )
                latest = connection.execute(
                    select(structural_baselines.c.id)
                    .where(
                        structural_baselines.c.repository_id == repository_id,
                        structural_baselines.c.status == "COMPLETED",
                    )
                    .order_by(
                        structural_baselines.c.cutoff_at.desc(),
                        structural_baselines.c.created_at.desc(),
                    )
                    .limit(1)
                ).scalar_one_or_none()
                facts = int(
                    connection.execute(
                        select(func.count()).select_from(structural_commit_facts).where(
                            structural_commit_facts.c.repository_id == repository_id
                        )
                    ).scalar_one()
                )
                status_counts = {
                    status: int(
                        connection.execute(
                            select(func.count()).select_from(structural_baselines).where(
                                structural_baselines.c.repository_id == repository_id,
                                structural_baselines.c.status == status,
                            )
                        ).scalar_one()
                    )
                    for status in ("BUILDING", "FAILED", "CANCELLED", "STALE")
                }
                orphan = int(
                    connection.execute(
                        select(func.count())
                        .select_from(
                            structural_baselines.outerjoin(
                                structural_materializations,
                                structural_materializations.c.baseline_id
                                == structural_baselines.c.id,
                            )
                        )
                        .where(
                            structural_baselines.c.repository_id == repository_id,
                            structural_baselines.c.status == "COMPLETED",
                            structural_materializations.c.baseline_id.is_(None),
                        )
                    ).scalar_one()
                )
                latest_diagnostic = connection.execute(
                    select(structural_baselines.c.id)
                    .where(
                        structural_baselines.c.repository_id == repository_id,
                        structural_baselines.c.status.in_(
                            ("BUILDING", "FAILED", "CANCELLED", "STALE")
                        ),
                    )
                    .order_by(structural_baselines.c.created_at.desc())
                    .limit(1)
                ).scalar_one_or_none()
                return {
                    "baselineCount": count,
                    "latestBaselineId": str(latest) if latest else None,
                    "processedCommits": facts,
                    "factRuleVersion": STRUCTURAL_FACT_RULE_VERSION,
                    "unhealthyBaselines": (
                        status_counts["BUILDING"] + status_counts["FAILED"] + orphan
                    ),
                    "orphanBaselines": orphan,
                    "buildingBaselines": status_counts["BUILDING"],
                    "failedBaselines": status_counts["FAILED"],
                    "cancelledBaselines": status_counts["CANCELLED"],
                    "staleBaselines": status_counts["STALE"],
                    "latestDiagnosticId": (
                        str(latest_diagnostic) if latest_diagnostic else None
                    ),
                }
        finally:
            engine.dispose()

    def completed_baseline_refs(self) -> tuple[dict[str, str | None], ...]:
        engine = create_database_engine(self.database_path)
        try:
            with engine.connect() as connection:
                repository_id = connection.execute(
                    select(repositories.c.id).where(
                        repositories.c.root_path == self.repository_root
                    )
                ).scalar_one()
                rows = connection.execute(
                    select(
                        structural_baselines.c.id,
                        structural_baselines.c.branch,
                        structural_baselines.c.baseline_commit,
                    ).where(
                        structural_baselines.c.repository_id == repository_id,
                        structural_baselines.c.status == "COMPLETED",
                    )
                ).mappings()
                return tuple(
                    {
                        "baselineId": str(row["id"]),
                        "branch": str(row["branch"]),
                        "baselineCommit": (
                            str(row["baseline_commit"])
                            if row["baseline_commit"]
                            else None
                        ),
                    }
                    for row in rows
                )
        finally:
            engine.dispose()

    def prune(self, keep: int) -> dict[str, int]:
        if keep < 0:
            raise ValueError("keep must not be negative")
        engine = create_database_engine(self.database_path)
        try:
            with engine.begin() as connection:
                repository_id = connection.execute(
                    select(repositories.c.id).where(
                        repositories.c.root_path == self.repository_root
                    )
                ).scalar_one()
                ids = list(
                    connection.execute(
                        select(structural_baselines.c.id)
                        .where(structural_baselines.c.repository_id == repository_id)
                        .order_by(
                            structural_baselines.c.cutoff_at.desc(),
                            structural_baselines.c.created_at.desc(),
                        )
                    ).scalars()
                )
                deleted = ids[keep:]
                if deleted:
                    connection.execute(
                        delete(structural_baselines).where(
                            structural_baselines.c.id.in_(deleted)
                        )
                    )
                return {"deletedBaselines": len(deleted), "remainingBaselines": len(ids[:keep])}
        finally:
            engine.dispose()


def serialize_baseline(
    baseline: StructuralBaseline,
    *,
    branch: str,
    scope: str | None,
    baseline_commit: str | None,
    status: str,
) -> dict[str, Any]:
    return {
        "schemaVersion": "1.0",
        "baselineId": baseline.id,
        "status": status,
        "baselineCommit": baseline_commit,
        "cutoff": baseline.cutoff.isoformat(),
        "branch": branch,
        "scope": scope,
        "timeStrategy": baseline.config.time_strategy.value,
        "configuration": {
            "minimumBaselineCommits": baseline.config.minimum_baseline_commits,
            "hotspotPercentile": baseline.config.hotspot_percentile,
            "minimumCoChangeCount": baseline.config.minimum_co_change_count,
            "minimumSubsetRatio": baseline.config.minimum_subset_ratio,
            "minimumJaccard": baseline.config.minimum_jaccard,
            "minimumHubPenalty": baseline.config.minimum_hub_penalty,
            "maximumContextPaths": baseline.config.maximum_context_paths,
            "rollingWindowDays": baseline.config.rolling_window_days,
        },
        "ruleVersions": {
            "facts": STRUCTURAL_FACT_RULE_VERSION,
            "metrics": STRUCTURAL_METRIC_RULE_VERSION,
            "thresholds": STRUCTURAL_THRESHOLD_VERSION,
        },
        "summary": {
            "eligibleCommits": baseline.summary.eligible_commits,
            "eligibleFiles": baseline.summary.eligible_files,
            "rawEdges": baseline.summary.raw_edges,
            "cappedCommits": baseline.summary.capped_commits,
        },
        "materialization": {
            "hotspots": [
                {
                    "path": value.path,
                    "changeCount": value.change_count,
                    "percentile": value.percentile,
                    "recentPercentile": value.recent_percentile,
                    "confidence": value.confidence,
                }
                for value in baseline.materialization.file_metrics
            ],
            "couplings": [
                {
                    "leftPath": value.left_path,
                    "rightPath": value.right_path,
                    "coChangeCount": value.co_change_count,
                    "subsetRatio": value.subset_ratio,
                    "leftConditional": value.left_conditional,
                    "rightConditional": value.right_conditional,
                    "jaccard": value.jaccard,
                    "hubPenalty": value.hub_penalty,
                    "crossModule": value.cross_module,
                    "confidence": value.confidence,
                }
                for value in baseline.materialization.edge_metrics
            ],
            "confidence": baseline.materialization.confidence,
            "gaps": list(baseline.materialization.gaps),
            "limitations": list(baseline.materialization.limitations),
        },
    }


def _eligible_git_paths(commit: GitCommit) -> tuple[tuple[str, ...], str | None]:
    if commit.is_merge:
        return (), "MERGE"
    normalized = tuple(
        sorted(
            {
                path
                for change in commit.changes
                for path in (change.new_path or change.old_path,)
                if path and not is_generated_path(path)
            }
        )
    )
    if not normalized:
        return (), "NOISE_ONLY"
    if (
        all(change.is_binary for change in commit.changes)
        and commit.insertions + commit.deletions == 0
    ):
        return (), "BINARY_ONLY"
    return normalized, None


def _module(path: str) -> str:
    normalized = path.replace("\\", "/").strip("/")
    return normalized.split("/", maxsplit=1)[0] if "/" in normalized else "root"


def _aware_utc(value: Any) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError("Expected datetime")
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
