from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from git_contribution_analyzer.adapters.git.repository_discovery import discover_repository
from git_contribution_analyzer.adapters.storage.sqlite.analysis import SqliteAnalysisStore
from git_contribution_analyzer.adapters.storage.sqlite.database import initialize_database
from git_contribution_analyzer.adapters.workspace.layout import WorkspaceLayout
from git_contribution_analyzer.adapters.workspace.locks import workspace_lock
from git_contribution_analyzer.application.services.evidence_snapshot import (
    build_evidence_snapshot,
    build_snapshot_subject,
)
from git_contribution_analyzer.application.use_cases.analyze_contributions import (
    _branch_hashes,
    _build_report,
)
from git_contribution_analyzer.domain.models.analysis import AnalysisFilters

Clock = Callable[[], datetime]
IdGenerator = Callable[[], str]


def analyze_project(
    path: Path,
    *,
    filters: AnalysisFilters | None = None,
    clock: Clock | None = None,
    id_generator: IdGenerator | None = None,
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
        store.start_run(
            run_id=run_id,
            person_id=None,
            parameters={"all": True, "filters": active_filters.as_dict(), "llm": False},
            baseline_commit=baseline,
            started_at=started_at,
        )
        try:
            people_reports: list[dict[str, Any]] = []
            identity_warnings: list[str] = []
            subjects = []
            for person_record in store.list_people_for_analysis():
                commits = store.load_commits(
                    person_record["id"], active_filters, allowed_hashes=allowed_hashes
                )
                if not commits:
                    continue
                person = {
                    key: person_record[key]
                    for key in ("id", "name", "email", "kind", "confirmed")
                }
                subject = build_snapshot_subject(person, commits)
                subjects.append(subject)
                person_report = _build_report(
                    run_id=run_id,
                    started_at=started_at,
                    completed_at=started_at,
                    baseline=baseline,
                    person=person,
                    filters=active_filters,
                    commits=commits,
                    items=subject.contribution_items,
                    evidence=subject.evidence,
                    capabilities=subject.capabilities,
                )
                people_reports.append(person_report)
                if not person_record["confirmed"]:
                    aliases = ", ".join(
                        sorted({alias["name"] for alias in person_record["aliases"]})
                    )
                    identity_warnings.append(
                        f"Unconfirmed identity: {person['name']} <{person['email']}>; "
                        f"aliases: {aliases or person['name']}."
                    )
            build_evidence_snapshot(
                repository_root=repository.root,
                baseline_commit=baseline,
                filters=active_filters,
                scope_type="PROJECT",
                subjects=tuple(subjects),
                identity_warnings=tuple(identity_warnings),
                created_at=started_at,
            )
            people_reports.sort(
                key=lambda report: (
                    -report["summary"]["commits"],
                    report["person"]["name"].casefold(),
                    report["person"]["email"].casefold(),
                )
            )
            completed_at = now()
            report = _build_project_report(
                run_id=run_id,
                started_at=started_at,
                completed_at=completed_at,
                baseline=baseline,
                repository_root=str(repository.root),
                filters=active_filters,
                people_reports=people_reports,
                identity_warnings=identity_warnings,
            )
            store.complete_run(
                run_id=run_id,
                completed_at=completed_at,
                report=report,
                persist_details=False,
            )
            return report
        except Exception as exc:
            store.fail_run(run_id, now(), str(exc))
            raise


def _build_project_report(
    *,
    run_id: str,
    started_at: datetime,
    completed_at: datetime,
    baseline: str | None,
    repository_root: str,
    filters: AnalysisFilters,
    people_reports: list[dict[str, Any]],
    identity_warnings: list[str],
) -> dict[str, Any]:
    commit_types: Counter[str] = Counter()
    deliveries: Counter[str] = Counter()
    modules: Counter[str] = Counter()
    capability_people: defaultdict[str, set[str]] = defaultdict(set)
    capability_refs: defaultdict[str, set[str]] = defaultdict(set)
    domain_totals: defaultdict[str, Counter[str]] = defaultdict(Counter)
    domain_people: defaultdict[str, set[str]] = defaultdict(set)
    domain_refs: defaultdict[str, set[str]] = defaultdict(set)

    for person_report in people_reports:
        person_id = person_report["person"]["id"]
        commit_types.update(person_report["commitTypes"])
        deliveries.update(person_report["deliveryStatuses"])
        modules.update(
            {entry["name"]: entry["commits"] for entry in person_report["modules"]}
        )
        for capability in person_report["capabilities"]:
            capability_people[capability["capability"]].add(person_id)
            capability_refs[capability["capability"]].update(
                f"{person_id}:{value}" for value in capability["evidenceIds"]
            )
        for domain in person_report["businessSummary"]["domains"]:
            domain_people[domain["name"]].add(person_id)
            domain_totals[domain["name"]].update(
                {
                    "contributionItems": domain["contributionItems"],
                    "commits": domain["commits"],
                    "landedCommits": domain["landedCommits"],
                }
            )
            domain_refs[domain["name"]].update(
                f"{person_id}:{value}" for value in domain["evidenceIds"]
            )

    dominant_modules = [
        {"name": name, "commits": count}
        for name, count in sorted(modules.items(), key=lambda value: (-value[1], value[0]))
    ]
    domains: list[dict[str, Any]] = [
        {
            "name": name,
            "people": len(domain_people[name]),
            "contributionItems": totals["contributionItems"],
            "commits": totals["commits"],
            "landedCommits": totals["landedCommits"],
            "evidenceRefs": sorted(domain_refs[name])[:50],
        }
        for name, totals in domain_totals.items()
    ]
    domains.sort(
        key=lambda value: (-int(value["commits"]), str(value["name"]))
    )
    technical = {
        "headline": f"{len(people_reports)} Git people contributed across {len(modules)} modules.",
        "dominantModules": dominant_modules[:15],
        "changeProfile": [
            {"type": name, "commits": count}
            for name, count in sorted(
                commit_types.items(), key=lambda value: (-value[1], value[0])
            )
        ],
        "capabilities": [
            {
                "capability": name,
                "people": len(capability_people[name]),
                "evidenceRefs": sorted(capability_refs[name])[:50],
            }
            for name in sorted(capability_people)
        ],
    }
    business = {
        "headline": f"Deterministic clustering identified {len(domains)} project business domains.",
        "domains": domains,
        "limitations": [
            "Business domains are inferred from commit scopes and clustering keys.",
            "Git evidence does not prove business outcome, ownership, or value delivered.",
        ],
    }
    summary_fields = (
        "commits",
        "mergeCommits",
        "filesChanged",
        "insertions",
        "deletions",
        "generatedFiles",
    )
    return {
        "schemaVersion": "1.0",
        "reportType": "PROJECT",
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
        "repository": repository_root,
        "filters": filters.as_dict(),
        "summary": {
            "people": len(people_reports),
            "confirmedPeople": sum(
                report["person"]["confirmed"] for report in people_reports
            ),
            "unconfirmedPeople": sum(
                not report["person"]["confirmed"] for report in people_reports
            ),
            **{
                field: sum(report["summary"][field] for report in people_reports)
                for field in summary_fields
            },
            "firstAuthoredAt": min(
                (
                    report["summary"]["firstAuthoredAt"]
                    for report in people_reports
                    if report["summary"]["firstAuthoredAt"]
                ),
                default=None,
            ),
            "lastAuthoredAt": max(
                (
                    report["summary"]["lastAuthoredAt"]
                    for report in people_reports
                    if report["summary"]["lastAuthoredAt"]
                ),
                default=None,
            ),
        },
        "commitTypes": dict(sorted(commit_types.items())),
        "deliveryStatuses": dict(sorted(deliveries.items())),
        "technicalSummary": technical,
        "businessSummary": business,
        "people": people_reports,
        "identityWarnings": identity_warnings,
        "warnings": [],
        "limitations": [
            "Unconfirmed identities are reported separately and are not automatically merged.",
            "Commit counts and line counts are context, not a performance score.",
        ],
    }
