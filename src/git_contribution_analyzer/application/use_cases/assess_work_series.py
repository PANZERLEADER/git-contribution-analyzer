from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from git_contribution_analyzer.adapters.git.native_git import NativeGitHistory
from git_contribution_analyzer.adapters.git.repository_discovery import discover_repository
from git_contribution_analyzer.adapters.storage.sqlite.analysis import SqliteAnalysisStore
from git_contribution_analyzer.adapters.storage.sqlite.database import initialize_database
from git_contribution_analyzer.adapters.workspace.config import load_config
from git_contribution_analyzer.adapters.workspace.layout import WorkspaceLayout
from git_contribution_analyzer.application.ports.llm import LlmProvider
from git_contribution_analyzer.application.use_cases.assess_work import (
    assess_work,
    build_assessment_workload_baseline,
)
from git_contribution_analyzer.domain.models.analysis import AnalysisFilters
from git_contribution_analyzer.domain.models.ranking import RankingConfig
from git_contribution_analyzer.domain.models.run import RunType
from git_contribution_analyzer.domain.services.assessment_periods import (
    build_period_comparison,
    split_periods,
    summarize_assessment,
)


def assess_work_series(
    path: Path,
    *,
    period: str,
    person_selectors: tuple[str, ...] = (),
    all_people: bool = False,
    exclude_selectors: tuple[str, ...] = (),
    rank_by: tuple[str, ...] = (),
    ranking_config: RankingConfig | None = None,
    filters: AnalysisFilters,
    llm_provider: LlmProvider | None = None,
    allow_llm_fallback: bool = True,
) -> dict[str, Any]:
    if filters.since is None or filters.until is None:
        raise ValueError("Periodic assessment requires both since and until")
    windows = split_periods(filters.since, filters.until, period)
    repository = discover_repository(path)
    layout = WorkspaceLayout.for_repository(repository.root)
    config = load_config(layout.config)
    history = NativeGitHistory(repository.root)
    integration_times = (
        history.integration_times(f"refs/heads/{config.default_branch}")
        if filters.time_basis in {"MERGED", "LANDED"}
        else {}
    )
    release_times = history.release_times() if filters.time_basis == "RELEASED" else {}
    workload_baseline = build_assessment_workload_baseline(
        path,
        person_selectors=person_selectors,
        all_people=all_people,
        exclude_selectors=exclude_selectors,
        filters=filters,
        integration_times=integration_times,
        release_times=release_times,
    )
    child_reports = [
        assess_work(
            path,
            person_selectors=person_selectors,
            all_people=all_people,
            exclude_selectors=exclude_selectors,
            rank_by=rank_by,
            ranking_config=ranking_config,
            filters=replace(filters, since=window.since, until=window.until),
            llm_provider=llm_provider,
            allow_llm_fallback=allow_llm_fallback,
            workload_baseline=workload_baseline,
            integration_times=integration_times,
            release_times=release_times,
        )
        for window in windows
    ]

    initialize_database(layout.database)
    store = SqliteAnalysisStore(layout.database, str(repository.root))
    started_at = datetime.now(UTC)
    run_id = str(uuid4())
    summaries = [summarize_assessment(report) for report in child_reports]
    by_comparison_key: dict[tuple[int, int], dict[str, int]] = {}
    serialized_periods = []
    for index, (window, report, summary) in enumerate(
        zip(windows, child_reports, summaries, strict=True)
    ):
        previous = summaries[index - 1] if index else None
        previous_year = by_comparison_key.get(
            (window.comparison_key[0] - 1, window.comparison_key[1])
        )
        serialized_periods.append(
            {
                "label": window.label,
                "since": window.since.isoformat(),
                "until": window.until.isoformat(),
                "partial": window.partial,
                "runId": report["run"]["id"],
                "status": report["run"]["status"],
                "metrics": summary,
                "comparison": build_period_comparison(summary, previous, previous_year),
            }
        )
        by_comparison_key[window.comparison_key] = summary

    warnings = [
        "Partial boundary periods should not be compared directly with complete periods."
        for window in windows
        if window.partial
    ][:1]
    report = {
        "schemaVersion": "1.0",
        "reportType": "WORK_ASSESSMENT_SERIES",
        "run": {
            "id": run_id,
            "runType": RunType.WORK_ASSESSMENT_SERIES.value,
            "status": "COMPLETED",
            "startedAt": started_at.isoformat(),
            "completedAt": started_at.isoformat(),
            "ruleVersion": "work-assessment-series-v1",
        },
        "period": period.casefold(),
        "timeBasis": filters.time_basis,
        "range": {
            "since": filters.since.isoformat(),
            "until": filters.until.isoformat(),
        },
        "periods": serialized_periods,
        "warnings": warnings,
        "limitations": [
            "Period comparisons are valid only for the same repository, cohort, filters, "
            "and rule versions.",
            "Git evidence does not measure hours worked or employee value.",
        ],
    }
    store.start_run(
        run_id=run_id,
        person_id=None,
        parameters={
            "period": period.casefold(),
            "timeBasis": filters.time_basis,
            "filters": filters.as_dict(),
            "childRunIds": [entry["runId"] for entry in serialized_periods],
        },
        baseline_commit=store.baseline_commit(),
        started_at=started_at,
        run_type=RunType.WORK_ASSESSMENT_SERIES,
    )
    completed_at = datetime.now(UTC)
    report["run"]["completedAt"] = completed_at.isoformat()
    store.complete_run(
        run_id=run_id,
        completed_at=completed_at,
        report=report,
        persist_details=False,
    )
    return report
