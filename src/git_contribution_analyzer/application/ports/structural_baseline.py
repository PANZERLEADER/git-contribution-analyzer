from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from git_contribution_analyzer.domain.models.contribution import ContributionCommit
from git_contribution_analyzer.domain.models.git_history import GitCommit
from git_contribution_analyzer.domain.models.structural_baseline import (
    StructuralBaseline,
    StructuralRuleConfig,
)


@runtime_checkable
class StructuralBaselineStore(Protocol):
    def repository_id(self) -> str: ...

    def sync_commit_facts(
        self,
        git_commits: Iterable[GitCommit],
        *,
        clear_existing: bool,
        maximum_context_paths: int = 200,
    ) -> dict[str, int]: ...

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
    ) -> None: ...

    def finish_baseline(
        self,
        build_id: str,
        *,
        status: str,
        error_message: str,
    ) -> None: ...

    def load_commits(
        self,
        *,
        allowed_hashes: set[str],
        cutoff: datetime,
        scope: str | None,
    ) -> tuple[ContributionCommit, ...]: ...

    def latest_fact_commit(
        self,
        *,
        allowed_hashes: set[str],
        cutoff: datetime,
        scope: str | None,
    ) -> str | None: ...

    def save_baseline(
        self,
        baseline: StructuralBaseline,
        *,
        branch: str,
        scope: str | None,
        baseline_commit: str | None,
        filter_fingerprint: str,
        diagnostic_id: str | None = None,
    ) -> dict[str, Any]: ...

    def mark_stale(self, baseline_ids: Iterable[str]) -> int: ...

    def find_completed(
        self,
        *,
        branch: str,
        scope: str | None,
        cutoff: datetime,
        baseline_commit: str | None,
        filter_fingerprint: str,
        time_strategy: str,
    ) -> dict[str, Any] | None: ...

    def show(self, baseline_id: str) -> dict[str, Any] | None: ...

    def status(self) -> dict[str, Any]: ...

    def completed_baseline_refs(self) -> tuple[dict[str, str | None], ...]: ...

    def prune(self, keep: int) -> dict[str, int]: ...
