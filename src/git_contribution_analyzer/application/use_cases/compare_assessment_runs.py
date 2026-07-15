from __future__ import annotations

from pathlib import Path
from typing import Any

from git_contribution_analyzer.application.use_cases.get_run import get_run
from git_contribution_analyzer.domain.errors import ReportError
from git_contribution_analyzer.domain.services.assessment_periods import (
    DIFFICULTY_POINTS,
    SIZE_POINTS,
    build_period_comparison,
    summarize_assessment,
)


def compare_assessment_runs(path: Path, base_run_id: str, target_run_id: str) -> dict[str, Any]:
    base = get_run(path, base_run_id)
    target = get_run(path, target_run_id)
    for run_id, report in ((base_run_id, base), (target_run_id, target)):
        if report.get("reportType") != "WORK_ASSESSMENT":
            raise ReportError(f"Run is not a work assessment: {run_id}")

    base_summary = summarize_assessment(base)
    target_summary = summarize_assessment(target)
    changes = build_period_comparison(target_summary, base_summary, None)["periodOverPeriod"]
    warnings = _comparability_warnings(base, target)
    return {
        "schemaVersion": "1.0",
        "reportType": "WORK_ASSESSMENT_COMPARISON",
        "baseRunId": str(base["run"]["id"]),
        "targetRunId": str(target["run"]["id"]),
        "baseSnapshotId": base["snapshot"].get("id"),
        "targetSnapshotId": target["snapshot"].get("id"),
        "changes": changes,
        "sizeDistributionChanges": _distribution_changes(
            base["workloadSummary"]["sizeDistribution"],
            target["workloadSummary"]["sizeDistribution"],
        ),
        "difficultyDistributionChanges": _distribution_changes(
            base["difficultyDistribution"], target["difficultyDistribution"]
        ),
        "subjects": _subject_changes(base, target),
        "warnings": warnings,
        "comparable": not warnings,
        "limitations": [
            "Deltas compare Git evidence under the stored rules; they do not measure hours "
            "or employee value."
        ],
    }


def _distribution_changes(base: dict[str, int], target: dict[str, int]) -> dict[str, int]:
    return {
        key: int(target.get(key, 0)) - int(base.get(key, 0))
        for key in sorted(set(base) | set(target))
    }


def _subject_changes(base: dict[str, Any], target: dict[str, Any]) -> list[dict[str, Any]]:
    base_subjects = {entry["person"]["id"]: entry for entry in base["subjects"]}
    target_subjects = {entry["person"]["id"]: entry for entry in target["subjects"]}
    result = []
    for person_id in sorted(set(base_subjects) | set(target_subjects)):
        base_subject = base_subjects.get(person_id)
        target_subject = target_subjects.get(person_id)
        base_metrics = _subject_metrics(base_subject)
        target_metrics = _subject_metrics(target_subject)
        selected_subject = target_subject or base_subject
        if selected_subject is None:
            continue
        person = selected_subject["person"]
        result.append(
            {
                "person": {"id": person["id"], "name": person["name"]},
                "base": base_metrics,
                "target": target_metrics,
                "changes": build_period_comparison(
                    target_metrics, base_metrics, None
                )["periodOverPeriod"],
            }
        )
    return result


def _subject_metrics(subject: dict[str, Any] | None) -> dict[str, int]:
    if subject is None:
        return {
            "completedItems": 0,
            "pendingItems": 0,
            "reworkItems": 0,
            "integrationItems": 0,
            "workloadPoints": 0,
            "difficultyPoints": 0,
        }
    items = subject["itemAssessments"]
    completed = [item for item in items if item["completionBucket"] == "COMPLETED"]
    return {
        "completedItems": len(completed),
        "pendingItems": sum(item["completionBucket"] == "PENDING" for item in items),
        "reworkItems": sum(item["completionBucket"] == "REWORK" for item in items),
        "integrationItems": len(subject["integrationWork"]),
        "workloadPoints": sum(SIZE_POINTS[item["size"]["band"]] for item in completed),
        "difficultyPoints": sum(
            DIFFICULTY_POINTS[item["difficulty"]["level"]] for item in completed
        ),
    }


def _comparability_warnings(base: dict[str, Any], target: dict[str, Any]) -> list[str]:
    warnings = []
    if base["run"].get("ruleVersion") != target["run"].get("ruleVersion"):
        warnings.append("Rule versions differ; metric deltas may not be directly comparable.")
    if base["snapshot"]["filters"].get("timeBasis", "AUTHORED") != target["snapshot"][
        "filters"
    ].get("timeBasis", "AUTHORED"):
        warnings.append("Assessment time bases differ.")
    if set(base["selection"]["includedPersonIds"]) != set(
        target["selection"]["includedPersonIds"]
    ):
        warnings.append("Assessment cohorts differ.")
    return warnings
