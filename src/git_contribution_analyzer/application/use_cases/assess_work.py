from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from git_contribution_analyzer.adapters.git.repository_discovery import discover_repository
from git_contribution_analyzer.adapters.llm.cache import CachedAuditedProvider
from git_contribution_analyzer.adapters.storage.sqlite.analysis import SqliteAnalysisStore
from git_contribution_analyzer.adapters.storage.sqlite.database import initialize_database
from git_contribution_analyzer.adapters.storage.sqlite.llm_audit import SqliteLlmAuditStore
from git_contribution_analyzer.adapters.workspace.layout import WorkspaceLayout
from git_contribution_analyzer.adapters.workspace.locks import workspace_lock
from git_contribution_analyzer.application.ports.llm import LlmProvider
from git_contribution_analyzer.application.services.assessment_explanation import (
    explain_assessment,
)
from git_contribution_analyzer.application.services.evidence_snapshot import (
    build_evidence_snapshot,
    build_snapshot_subject,
)
from git_contribution_analyzer.application.services.person_selection import select_people
from git_contribution_analyzer.application.use_cases.analyze_contributions import _branch_hashes
from git_contribution_analyzer.domain.errors import LlmProviderError
from git_contribution_analyzer.domain.models.analysis import AnalysisFilters
from git_contribution_analyzer.domain.models.person_selection import PersonSelection
from git_contribution_analyzer.domain.models.ranking import RankingConfig
from git_contribution_analyzer.domain.models.run import RunType
from git_contribution_analyzer.domain.models.snapshot import EvidenceSnapshot, SnapshotSubject
from git_contribution_analyzer.domain.models.work_assessment import (
    CompletionBucket,
    DifficultyLevel,
    SizeBand,
    WorkItemAssessment,
    WorkloadBaseline,
)
from git_contribution_analyzer.domain.services.difficulty_rules import assess_difficulty
from git_contribution_analyzer.domain.services.ranking_rules import build_ranking
from git_contribution_analyzer.domain.services.workload_rules import (
    assess_item_size,
    build_workload_baseline,
    classify_completion,
)

Clock = Callable[[], datetime]
IdGenerator = Callable[[], str]


def assess_work(
    path: Path,
    *,
    person_selectors: tuple[str, ...] = (),
    all_people: bool = False,
    exclude_selectors: tuple[str, ...] = (),
    rank_by: tuple[str, ...] = (),
    ranking_config: RankingConfig | None = None,
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
    active_filters = filters or AnalysisFilters()
    now = clock or (lambda: datetime.now(UTC))
    next_id = id_generator or (lambda: str(uuid4()))
    run_id = next_id()
    started_at = now()
    baseline = store.baseline_commit()
    allowed_hashes = _branch_hashes(repository.root, active_filters.branch)

    with workspace_lock(layout.locks / "workspace.lock"):
        people, selection = select_people(
            store,
            person_selectors=person_selectors,
            all_people=all_people,
            exclude_selectors=exclude_selectors,
        )
        subjects, identity_warnings = _load_subjects(
            store,
            active_filters,
            allowed_hashes,
            people=people,
        )
        scope_type = "PROJECT" if all_people or len(subjects) > 1 else "PERSON"
        snapshot = build_evidence_snapshot(
            repository_root=repository.root,
            baseline_commit=baseline,
            filters=active_filters,
            scope_type=scope_type,
            subjects=subjects,
            identity_warnings=identity_warnings,
            created_at=started_at,
        )
        person_id = snapshot.subjects[0].person.id if scope_type == "PERSON" else None
        store.start_run(
            run_id=run_id,
            person_id=person_id,
            parameters={
                "persons": list(person_selectors),
                "all": all_people,
                "excludePersons": list(exclude_selectors),
                "selection": selection.as_dict(),
                "rankBy": list(rank_by),
                "rankingConfig": (
                    ranking_config.as_dict() if ranking_config is not None else None
                ),
                "filters": active_filters.as_dict(),
                "llm": llm_provider is not None,
            },
            baseline_commit=baseline,
            started_at=started_at,
            run_type=RunType.WORK_ASSESSMENT,
        )
        try:
            report = _build_assessment_report(
                run_id,
                started_at,
                snapshot,
                selection=selection,
                rank_by=rank_by,
                ranking_config=ranking_config,
            )
            status = "COMPLETED"
            provider_id = "none"
            if llm_provider is not None:
                provider_id = llm_provider.provider_id
                if not any(subject.evidence for subject in snapshot.subjects):
                    report["warnings"].append(
                        "LLM assessment explanation skipped: no Evidence available."
                    )
                else:
                    audited_provider = CachedAuditedProvider(
                        llm_provider,
                        SqliteLlmAuditStore(layout.database),
                        run_id=run_id,
                    )
                    try:
                        enhancement = explain_assessment(
                            report, snapshot, audited_provider
                        )
                        report["explanation"] = enhancement.explanation
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
                            f"LLM assessment explanation unavailable ({exc.code}); "
                            "deterministic assessment retained."
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
                persist_details=False,
            )
            return report
        except Exception as exc:
            store.fail_run(run_id, now(), str(exc))
            raise


def _load_subjects(
    store: SqliteAnalysisStore,
    filters: AnalysisFilters,
    allowed_hashes: set[str] | None,
    *,
    people: tuple[dict[str, Any], ...],
) -> tuple[tuple[SnapshotSubject, ...], tuple[str, ...]]:
    subjects: list[SnapshotSubject] = []
    warnings: list[str] = []
    for person in people:
        commits = store.load_commits(str(person["id"]), filters, allowed_hashes=allowed_hashes)
        subjects.append(build_snapshot_subject(person, commits))
        if not bool(person["confirmed"]):
            warnings.append(f"Unconfirmed identity: {person['name']} ({person['id']}).")
    return tuple(subjects), tuple(warnings)


def _build_assessment_report(
    run_id: str,
    started_at: datetime,
    snapshot: EvidenceSnapshot,
    *,
    selection: PersonSelection,
    rank_by: tuple[str, ...],
    ranking_config: RankingConfig | None,
) -> dict[str, Any]:
    completed_items = tuple(
        item
        for subject in snapshot.subjects
        for item in subject.contribution_items
        if classify_completion(item) is CompletionBucket.COMPLETED
    )
    workload_baseline = build_workload_baseline(completed_items)
    serialized_subjects = [
        _serialize_subject(subject, workload_baseline) for subject in snapshot.subjects
    ]
    assessments = [
        assessment
        for subject in serialized_subjects
        for assessment in subject["itemAssessments"]
    ]
    completed = [
        assessment
        for assessment in assessments
        if assessment["completionBucket"] == CompletionBucket.COMPLETED.value
    ]
    modules = Counter(
        module
        for subject in snapshot.subjects
        for item in subject.contribution_items
        if classify_completion(item) is CompletionBucket.COMPLETED
        for module in item.modules
    )
    work_types = Counter(entry["workType"] for entry in completed)
    domains = Counter(
        item.group_key.split(":", maxsplit=1)[0]
        for subject in snapshot.subjects
        for item in subject.contribution_items
        if classify_completion(item) is CompletionBucket.COMPLETED
    )
    return {
        "schemaVersion": "2.0",
        "reportType": "WORK_ASSESSMENT",
        "scopeType": snapshot.scope_type,
        "run": {
            "id": run_id,
            "runType": RunType.WORK_ASSESSMENT.value,
            "parentRunId": None,
            "status": "COMPLETED",
            "startedAt": started_at.isoformat(),
            "completedAt": started_at.isoformat(),
            "ruleVersion": "work-assessment-v2",
            "providerId": "none",
            "model": None,
            "promptVersion": None,
            "semanticSchemaVersion": None,
        },
        "snapshot": snapshot.as_reference(),
        "selection": selection.as_dict(),
        "ranking": build_ranking(
            serialized_subjects,
            rank_by,
            snapshot_id=snapshot.id,
            config=ranking_config,
        ),
        "subjects": serialized_subjects,
        "workloadSummary": {
            "completedItems": len(completed),
            "pendingItems": sum(
                entry["completionBucket"] == CompletionBucket.PENDING.value
                for entry in assessments
            ),
            "reworkItems": sum(
                entry["completionBucket"] == CompletionBucket.REWORK.value
                for entry in assessments
            ),
            "integrationItems": sum(
                len(subject["integrationWork"]) for subject in serialized_subjects
            ),
            "sizeDistribution": _distribution(completed, "size", "band", SizeBand),
        },
        "difficultyDistribution": _distribution(
            completed, "difficulty", "level", DifficultyLevel
        ),
        "technicalSummary": {
            "headline": (
                f"Completed work spans {len(modules)} technical modules and "
                f"{len(work_types)} change types."
            ),
            "modules": [
                {"name": name, "items": count}
                for name, count in sorted(modules.items(), key=lambda value: (-value[1], value[0]))
            ],
            "workTypes": dict(sorted(work_types.items())),
        },
        "businessSummary": {
            "headline": f"Completed work covers {len(domains)} evidence-derived domains.",
            "domains": [
                {"name": name, "items": count}
                for name, count in sorted(domains.items(), key=lambda value: (-value[1], value[0]))
            ],
        },
        "evidence": [
            {
                "personId": subject.person.id,
                "id": entry.id,
                "type": entry.evidence_type,
                "summary": entry.summary,
                "commitHashes": list(entry.commit_hashes),
                "paths": list(entry.paths),
                "metrics": dict(entry.metrics),
            }
            for subject in snapshot.subjects
            for entry in subject.evidence
        ],
        "explanation": None,
        "identityWarnings": list(snapshot.identity_warnings),
        "warnings": [],
        "limitations": [
            "Work size describes effective change scope, not time spent or employee value.",
            "Difficulty is a versioned rules inference and must be reviewed with "
            "its evidence gaps.",
            "Git evidence does not prove business outcomes, sole ownership, or working hours.",
        ],
    }


def _serialize_subject(
    subject: SnapshotSubject, workload_baseline: WorkloadBaseline
) -> dict[str, Any]:
    item_assessments = [
        _assess_item(subject.person.id, item, workload_baseline)
        for item in subject.contribution_items
    ]
    return {
        "person": {
            "id": subject.person.id,
            "name": subject.person.name,
            "email": subject.person.email,
            "kind": subject.person.kind,
            "confirmed": subject.person.confirmed,
        },
        "completedWork": _ids_for_bucket(item_assessments, CompletionBucket.COMPLETED),
        "pendingWork": _ids_for_bucket(item_assessments, CompletionBucket.PENDING),
        "rework": _ids_for_bucket(item_assessments, CompletionBucket.REWORK),
        "integrationWork": [
            {"commitHash": commit.hash, "subject": commit.subject}
            for commit in subject.commits
            if commit.merge
        ],
        "itemAssessments": [_serialize_item_assessment(value) for value in item_assessments],
    }


def _assess_item(
    person_id: str,
    item: Any,
    workload_baseline: WorkloadBaseline,
) -> WorkItemAssessment:
    completion = classify_completion(item)
    work_types = sorted({commit.commit_type for commit in item.commits})
    paths = set(item.paths)
    support = tuple(
        name
        for name, present in (
            ("TEST", any("test" in path.casefold() for path in paths)),
            ("DOCUMENTATION", any(path.casefold().endswith(".md") for path in paths)),
            ("MIGRATION", any("migration" in path.casefold() for path in paths)),
            (
                "CONFIGURATION",
                any(
                    path.casefold().endswith((".yml", ".yaml", ".toml"))
                    for path in paths
                ),
            ),
        )
        if present
    )
    return WorkItemAssessment(
        contribution_item_id=item.id,
        person_id=person_id,
        completion_bucket=completion,
        delivery_statuses=tuple(sorted({commit.delivery_status for commit in item.commits})),
        work_type=work_types[0] if len(work_types) == 1 else "MIXED",
        size=assess_item_size(item, baseline=workload_baseline),
        difficulty=assess_difficulty(item),
        engineering_support=support,
        evidence_ids=item.evidence_ids,
    )


def _serialize_item_assessment(value: WorkItemAssessment) -> dict[str, Any]:
    return {
        "contributionItemId": value.contribution_item_id,
        "personId": value.person_id,
        "completionBucket": value.completion_bucket.value,
        "deliveryStatuses": list(value.delivery_statuses),
        "workType": value.work_type,
        "size": {
            "band": value.size.band.value,
            "effectiveFiles": value.size.effective_files,
            "effectiveChurn": value.size.effective_churn,
            "moduleSpan": value.size.module_span,
            "baselineSampleSize": value.size.baseline_sample_size,
            "baselineMode": value.size.baseline_mode,
            "ruleVersion": value.size.rule_version,
            "evidenceIds": list(value.size.evidence_ids),
            "excludedChanges": list(value.size.excluded_changes),
            "confidence": value.size.confidence,
            "gaps": list(value.size.gaps),
        },
        "difficulty": {
            "level": value.difficulty.level.value,
            "dimensionSignals": [
                {
                    "dimension": signal.dimension,
                    "code": signal.code,
                    "severity": signal.severity,
                    "description": signal.description,
                    "evidenceIds": list(signal.evidence_ids),
                }
                for signal in value.difficulty.dimension_signals
            ],
            "ruleVersion": value.difficulty.rule_version,
            "evidenceIds": list(value.difficulty.evidence_ids),
            "confidence": value.difficulty.confidence,
            "gaps": list(value.difficulty.gaps),
        },
        "engineeringSupport": list(value.engineering_support),
        "evidenceIds": list(value.evidence_ids),
        "warnings": list(value.warnings),
    }


def _ids_for_bucket(
    assessments: list[WorkItemAssessment], bucket: CompletionBucket
) -> list[str]:
    return [
        value.contribution_item_id
        for value in assessments
        if value.completion_bucket is bucket
    ]


def _distribution(
    entries: list[dict[str, Any]],
    group: str,
    field: str,
    values: type[SizeBand] | type[DifficultyLevel],
) -> dict[str, int]:
    counts = Counter(entry[group][field] for entry in entries)
    return {value.value: counts[value.value] for value in values}
