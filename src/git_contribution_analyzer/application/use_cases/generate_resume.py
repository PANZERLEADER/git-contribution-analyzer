from __future__ import annotations

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
from git_contribution_analyzer.application.services.evidence_snapshot import (
    build_evidence_snapshot,
    build_snapshot_subject,
)
from git_contribution_analyzer.application.services.resume_generation import (
    build_deterministic_resume,
    enhance_resume,
)
from git_contribution_analyzer.application.use_cases.analyze_contributions import _branch_hashes
from git_contribution_analyzer.domain.errors import ConfigurationError, LlmProviderError
from git_contribution_analyzer.domain.models.analysis import AnalysisFilters
from git_contribution_analyzer.domain.models.resume import (
    ResumeLanguage,
    ResumeStyle,
    VerifiedOutcome,
)
from git_contribution_analyzer.domain.models.run import RunType

Clock = Callable[[], datetime]
IdGenerator = Callable[[], str]


def generate_resume(
    path: Path,
    *,
    person_selector: str,
    filters: AnalysisFilters | None = None,
    target_role: str = "",
    language: str = "zh-CN",
    style: str = "concise",
    max_bullets: int = 6,
    include_pending: bool = False,
    outcomes: tuple[VerifiedOutcome, ...] = (),
    clock: Clock | None = None,
    id_generator: IdGenerator | None = None,
    llm_provider: LlmProvider | None = None,
    allow_llm_fallback: bool = True,
) -> dict[str, Any]:
    if not 1 <= max_bullets <= 20:
        raise ConfigurationError("max bullets must be between 1 and 20")
    try:
        selected_language = ResumeLanguage(language)
        selected_style = ResumeStyle(style)
    except ValueError as exc:
        raise ConfigurationError("Unsupported resume language or style") from exc
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
    person = store.resolve_confirmed_person(person_selector)
    commits = store.load_commits(
        str(person["id"]),
        active_filters,
        allowed_hashes=_branch_hashes(repository.root, active_filters.branch),
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

    with workspace_lock(layout.locks / "workspace.lock"):
        store.start_run(
            run_id=run_id,
            person_id=str(person["id"]),
            parameters={
                "person": person_selector,
                "filters": active_filters.as_dict(),
                "targetRole": target_role,
                "language": language,
                "style": style,
                "maxBullets": max_bullets,
                "includePending": include_pending,
                "llm": llm_provider is not None,
            },
            baseline_commit=baseline,
            started_at=started_at,
            run_type=RunType.RESUME,
        )
        try:
            content = build_deterministic_resume(
                subject,
                language=selected_language,
                style=selected_style,
                max_bullets=max_bullets,
                include_pending=include_pending,
                outcomes=outcomes,
            )
            report = {
                "schemaVersion": "1.0",
                "reportType": "RESUME",
                "run": {
                    "id": run_id,
                    "runType": RunType.RESUME.value,
                    "parentRunId": None,
                    "status": "COMPLETED",
                    "startedAt": started_at.isoformat(),
                    "completedAt": started_at.isoformat(),
                    "ruleVersion": "resume-claim-rules-v1",
                    "providerId": "none",
                    "model": None,
                    "promptVersion": None,
                    "semanticSchemaVersion": None,
                },
                "snapshot": snapshot.as_reference(),
                "person": {"id": subject.person.id, "name": subject.person.name},
                "targetRole": target_role,
                "language": selected_language.value,
                "style": selected_style.value,
                **content,
                "evidence": [
                    {
                        "id": entry.id,
                        "type": entry.evidence_type,
                        "summary": entry.summary,
                        "commitHashes": list(entry.commit_hashes),
                        "paths": list(entry.paths),
                        "metrics": dict(entry.metrics),
                    }
                    for entry in subject.evidence
                ],
                "warnings": [],
                "limitations": [
                    "Resume candidates are evidence-backed drafts and require human review.",
                    "Git evidence does not prove business outcomes or sole ownership.",
                ],
            }
            status = "COMPLETED"
            provider_id = "none"
            if llm_provider is not None:
                provider_id = llm_provider.provider_id
                if not report["experienceBullets"]:
                    report["warnings"].append(
                        "LLM resume generation skipped: no eligible Evidence available."
                    )
                else:
                    audited_provider = CachedAuditedProvider(
                        llm_provider,
                        SqliteLlmAuditStore(layout.database),
                        run_id=run_id,
                    )
                    try:
                        enhancement = enhance_resume(
                            report=report,
                            snapshot=snapshot,
                            provider=audited_provider,
                            outcomes=outcomes,
                            max_bullets=max_bullets,
                        )
                        report.update(enhancement.content)
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
                            f"LLM resume generation unavailable ({exc.code}); "
                            "conservative templates retained."
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
