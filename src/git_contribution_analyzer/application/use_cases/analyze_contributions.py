from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from git_contribution_analyzer.adapters.git.native_git import NativeGitHistory
from git_contribution_analyzer.adapters.git.repository_discovery import discover_repository
from git_contribution_analyzer.adapters.llm.cache import CachedAuditedProvider
from git_contribution_analyzer.adapters.storage.sqlite.analysis import SqliteAnalysisStore
from git_contribution_analyzer.adapters.storage.sqlite.database import initialize_database
from git_contribution_analyzer.adapters.storage.sqlite.llm_audit import SqliteLlmAuditStore
from git_contribution_analyzer.adapters.workspace.layout import WorkspaceLayout
from git_contribution_analyzer.adapters.workspace.locks import workspace_lock
from git_contribution_analyzer.application.ports.llm import LlmProvider
from git_contribution_analyzer.application.services.evidence_snapshot import (
    build_evidence_snapshot,
    build_snapshot_subject,
)
from git_contribution_analyzer.application.services.semantic_enhancement import enhance_report
from git_contribution_analyzer.domain.errors import LlmProviderError
from git_contribution_analyzer.domain.models.analysis import AnalysisFilters
from git_contribution_analyzer.domain.models.contribution import (
    ContributionCommit,
    ContributionItem,
    Evidence,
)
from git_contribution_analyzer.domain.services.dimensional_summary import (
    build_dimensional_summaries,
)

Clock = Callable[[], datetime]
IdGenerator = Callable[[], str]


def analyze_contributions(
    path: Path,
    *,
    person_selector: str,
    filters: AnalysisFilters | None = None,
    clock: Clock | None = None,
    id_generator: IdGenerator | None = None,
    llm_provider: LlmProvider | None = None,
    allow_llm_fallback: bool = True,
) -> dict[str, Any]:
    repository = discover_repository(path)
    layout = WorkspaceLayout.for_repository(repository.root)
    initialize_database(layout.database)
    store = SqliteAnalysisStore(layout.database, str(repository.root))
    person = store.resolve_confirmed_person(person_selector)
    active_filters = filters or AnalysisFilters()
    now = clock or (lambda: datetime.now(UTC))
    next_id = id_generator or (lambda: str(uuid4()))
    run_id = next_id()
    started_at = now()
    baseline = store.baseline_commit()
    parameters = {
        "person": person_selector,
        "filters": active_filters.as_dict(),
        "llm": llm_provider is not None,
    }
    allowed_hashes = _branch_hashes(repository.root, active_filters.branch)

    with workspace_lock(layout.locks / "workspace.lock"):
        store.start_run(
            run_id=run_id,
            person_id=person["id"],
            parameters=parameters,
            baseline_commit=baseline,
            started_at=started_at,
        )
        try:
            commits = store.load_commits(
                person["id"], active_filters, allowed_hashes=allowed_hashes
            )
            subject = build_snapshot_subject(person, commits)
            snapshot = build_evidence_snapshot(
                repository_root=repository.root,
                baseline_commit=baseline,
                filters=active_filters,
                scope_type="PERSON",
                subjects=(subject,),
                identity_warnings=(),
                created_at=started_at,
            )
            subject = snapshot.subjects[0]
            report = _build_report(
                run_id=run_id,
                started_at=started_at,
                completed_at=started_at,
                baseline=baseline,
                person=person,
                filters=active_filters,
                commits=subject.commits,
                items=subject.contribution_items,
                evidence=subject.evidence,
                capabilities=subject.capabilities,
            )
            status = "COMPLETED"
            provider_id = "none"
            if llm_provider is not None:
                provider_id = llm_provider.provider_id
                report["run"].update(
                    {
                        "providerId": provider_id,
                        "model": llm_provider.model,
                    }
                )
            if llm_provider is not None and not subject.evidence:
                report["warnings"].append(
                    "LLM semantic enhancement skipped: no Evidence available."
                )
            elif llm_provider is not None:
                audited_provider = CachedAuditedProvider(
                    llm_provider,
                    SqliteLlmAuditStore(layout.database),
                    run_id=run_id,
                )
                try:
                    enhancement = enhance_report(report, audited_provider)
                    report["semantic"] = enhancement.semantic
                    report["run"].update(
                        {
                            "providerId": enhancement.completion.provider_id,
                            "model": enhancement.completion.model,
                            "promptVersion": enhancement.task.prompt_version,
                            "semanticSchemaVersion": enhancement.task.schema_version,
                        }
                    )
                except LlmProviderError as exc:
                    if not allow_llm_fallback:
                        raise
                    status = "PARTIAL"
                    report["warnings"].append(
                        f"LLM semantic enhancement unavailable ({exc.code}); "
                        "deterministic evidence retained."
                    )
                    report["run"]["providerId"] = provider_id
            report["run"]["status"] = status
            completed_at = now()
            report["run"]["completedAt"] = completed_at.isoformat()
            store.complete_run(
                run_id=run_id,
                completed_at=completed_at,
                report=report,
                status=status,
                provider_id=provider_id,
            )
            return report
        except Exception as exc:
            store.fail_run(run_id, now(), str(exc))
            raise


def _branch_hashes(repository_root: Path, branch: str | None) -> set[str] | None:
    if not branch:
        return None
    ref_name = branch if branch.startswith("refs/") else f"refs/heads/{branch}"
    return set(NativeGitHistory(repository_root).reachable_commits(ref_name))


def _build_report(
    *,
    run_id: str,
    started_at: datetime,
    completed_at: datetime,
    baseline: str | None,
    person: dict[str, Any],
    filters: AnalysisFilters,
    commits: tuple[ContributionCommit, ...],
    items: tuple[ContributionItem, ...],
    evidence: tuple[Evidence, ...],
    capabilities: tuple[Any, ...],
) -> dict[str, Any]:
    non_merge = tuple(commit for commit in commits if not commit.merge)
    commit_types = Counter(commit.commit_type for commit in non_merge)
    deliveries = Counter(commit.delivery_status for commit in commits)
    module_counts = Counter(module for commit in non_merge for module in commit.modules)
    technical_summary, business_summary = build_dimensional_summaries(
        commits, items, capabilities
    )
    return {
        "schemaVersion": "1.0",
        "reportType": "PERSON",
        "run": {
            "id": run_id,
            "status": "COMPLETED",
            "startedAt": started_at.isoformat(),
            "completedAt": completed_at.isoformat(),
            "baselineCommit": baseline,
            "ruleVersion": "rules-v1",
            "providerId": "none",
            "model": None,
            "promptVersion": None,
            "semanticSchemaVersion": None,
        },
        "person": person,
        "filters": filters.as_dict(),
        "summary": {
            "commits": len(commits),
            "mergeCommits": sum(commit.merge for commit in commits),
            "filesChanged": sum(commit.files_changed for commit in non_merge),
            "insertions": sum(commit.insertions for commit in non_merge),
            "deletions": sum(commit.deletions for commit in non_merge),
            "binaryFiles": sum(commit.binary_files for commit in commits),
            "generatedFiles": sum(commit.generated_files for commit in commits),
            "firstAuthoredAt": commits[0].authored_at.isoformat() if commits else None,
            "lastAuthoredAt": commits[-1].authored_at.isoformat() if commits else None,
        },
        "commitTypes": dict(sorted(commit_types.items())),
        "deliveryStatuses": dict(sorted(deliveries.items())),
        "modules": [
            {"name": module, "commits": count}
            for module, count in sorted(module_counts.items())
        ],
        "contributionItems": [_serialize_item(item) for item in items],
        "capabilities": [
            {
                "capability": assessment.capability,
                "confidence": assessment.confidence,
                "rationale": assessment.rationale,
                "evidenceIds": list(assessment.evidence_ids),
                "gaps": list(assessment.gaps),
            }
            for assessment in capabilities
        ],
        "technicalSummary": technical_summary,
        "businessSummary": business_summary,
        "evidence": [_serialize_evidence(entry) for entry in evidence],
        "semantic": None,
        "warnings": [],
        "limitations": [
            "Git evidence does not prove business outcome or sole ownership.",
            "Commit and line counts are context, not a performance score.",
            "Low-confidence clusters require human review before use in performance decisions.",
        ],
    }


def _serialize_item(item: ContributionItem) -> dict[str, Any]:
    deliveries = Counter(commit.delivery_status for commit in item.commits)
    return {
        "id": item.id,
        "groupKey": item.group_key,
        "title": item.title,
        "confidence": item.confidence,
        "commitHashes": [commit.hash for commit in item.commits],
        "commitTypes": dict(sorted(Counter(c.commit_type for c in item.commits).items())),
        "deliveryStatuses": dict(sorted(deliveries.items())),
        "modules": list(item.modules),
        "paths": list(item.paths),
        "insertions": sum(commit.insertions for commit in item.commits),
        "deletions": sum(commit.deletions for commit in item.commits),
        "firstAuthoredAt": item.commits[0].authored_at.isoformat(),
        "lastAuthoredAt": item.commits[-1].authored_at.isoformat(),
        "evidenceIds": list(item.evidence_ids),
    }


def _serialize_evidence(entry: Evidence) -> dict[str, Any]:
    return {
        "id": entry.id,
        "type": entry.evidence_type,
        "summary": entry.summary,
        "commitHashes": list(entry.commit_hashes),
        "paths": list(entry.paths),
        "metrics": dict(entry.metrics),
    }
