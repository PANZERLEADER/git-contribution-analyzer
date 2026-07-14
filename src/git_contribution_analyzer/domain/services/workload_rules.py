from __future__ import annotations

from git_contribution_analyzer.domain.models.contribution import (
    ContributionCommit,
    ContributionItem,
)
from git_contribution_analyzer.domain.models.work_assessment import (
    CompletionBucket,
    SizeBand,
    WorkItemSizeAssessment,
    WorkloadBaseline,
)
from git_contribution_analyzer.domain.services.contribution_rules import is_generated_path

WORKLOAD_RULE_VERSION = "workload-rules-v1"


def classify_completion(item: ContributionItem) -> CompletionBucket:
    if item.commits and all(commit.merge for commit in item.commits):
        return CompletionBucket.INTEGRATION
    statuses = {commit.delivery_status for commit in item.commits}
    if "REVERTED" in statuses or any(
        commit.commit_type == "REVERT" for commit in item.commits
    ):
        return CompletionBucket.REWORK
    if statuses and statuses <= {"AUTHORED_ONLY"}:
        return CompletionBucket.PENDING
    if statuses.intersection({"LANDED", "RELEASED"}):
        return CompletionBucket.COMPLETED
    return CompletionBucket.PENDING


def assess_item_size(
    item: ContributionItem,
    *,
    baseline: WorkloadBaseline | None = None,
) -> WorkItemSizeAssessment:
    churn, effective_paths, excluded = _effective_metrics(item)
    modules = {
        path.replace("\\", "/").strip("/").split("/", maxsplit=1)[0]
        if "/" in path.replace("\\", "/").strip("/")
        else "root"
        for path in effective_paths
    }
    use_repository_baseline = baseline is not None and baseline.sample_size >= 20
    band = (
        _repository_band(churn, len(effective_paths), len(modules), baseline)
        if use_repository_baseline and baseline is not None
        else _static_band(churn, len(effective_paths), len(modules))
    )
    return WorkItemSizeAssessment(
        band=band,
        effective_files=len(effective_paths),
        effective_churn=churn,
        module_span=len(modules),
        baseline_sample_size=baseline.sample_size if baseline is not None else 0,
        baseline_mode="REPOSITORY" if use_repository_baseline else "STATIC_FALLBACK",
        rule_version=WORKLOAD_RULE_VERSION,
        evidence_ids=item.evidence_ids,
        excluded_changes=excluded,
        confidence="HIGH" if use_repository_baseline else "MEDIUM",
        gaps=() if use_repository_baseline else ("INSUFFICIENT_REPOSITORY_BASELINE",),
    )


def build_workload_baseline(items: tuple[ContributionItem, ...]) -> WorkloadBaseline:
    metrics = [_effective_metrics(item) for item in items]
    churn = sorted(value[0] for value in metrics)
    files = sorted(len(value[1]) for value in metrics)
    modules = sorted(
        len(
            {
                path.replace("\\", "/").strip("/").split("/", maxsplit=1)[0]
                if "/" in path.replace("\\", "/").strip("/")
                else "root"
                for path in value[1]
            }
        )
        for value in metrics
    )
    return WorkloadBaseline(
        sample_size=len(items),
        churn_percentiles=_percentiles(churn),
        file_percentiles=_percentiles(files),
        module_percentiles=_percentiles(modules),
    )


def _effective_metrics(
    item: ContributionItem,
) -> tuple[int, set[str], tuple[str, ...]]:
    commits, duplicate_count = _unique_effective_commits(item.commits)
    effective_paths: set[str] = set()
    churn = 0
    excluded: list[str] = []
    for commit in commits:
        if commit.merge:
            excluded.append(f"MERGE:{commit.hash}")
            continue
        eligible_paths = tuple(path for path in commit.paths if not is_generated_path(path))
        if not eligible_paths:
            excluded.append(f"NOISE_ONLY:{commit.hash}")
            continue
        if commit.binary_files >= len(commit.paths):
            excluded.append(f"BINARY_ONLY:{commit.hash}")
            continue
        effective_paths.update(eligible_paths)
        insertions = (
            commit.effective_insertions
            if commit.effective_insertions is not None
            else commit.insertions
        )
        deletions = (
            commit.effective_deletions
            if commit.effective_deletions is not None
            else commit.deletions
        )
        churn += insertions + deletions
    if duplicate_count:
        excluded.append(f"DUPLICATE_PATCHES:{duplicate_count}")
    return churn, effective_paths, tuple(sorted(excluded))


def _unique_effective_commits(
    commits: tuple[ContributionCommit, ...],
) -> tuple[tuple[ContributionCommit, ...], int]:
    seen: set[str] = set()
    result: list[ContributionCommit] = []
    duplicates = 0
    for commit in sorted(commits, key=lambda value: (value.authored_at, value.hash)):
        key = commit.patch_id or commit.hash
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        result.append(commit)
    return tuple(result), duplicates


def _static_band(churn: int, files: int, modules: int) -> SizeBand:
    if churn > 1000 or files > 30 or modules > 4:
        return SizeBand.XLARGE
    if churn > 300 or files > 10 or modules > 2:
        return SizeBand.LARGE
    if churn > 80 or files > 3 or modules > 1:
        return SizeBand.MEDIUM
    return SizeBand.SMALL


def _repository_band(
    churn: int,
    files: int,
    modules: int,
    baseline: WorkloadBaseline,
) -> SizeBand:
    candidates = (
        _percentile_band(churn, baseline.churn_percentiles),
        _percentile_band(files, baseline.file_percentiles),
        _percentile_band(modules, baseline.module_percentiles),
    )
    order = {band: index for index, band in enumerate(SizeBand)}
    band = max(candidates, key=lambda value: order[value])
    absolute = _static_band(churn, files, modules)
    return min((band, absolute), key=lambda value: order[value])


def _percentile_band(value: int, thresholds: tuple[int, int, int]) -> SizeBand:
    if value <= thresholds[0]:
        return SizeBand.SMALL
    if value <= thresholds[1]:
        return SizeBand.MEDIUM
    if value <= thresholds[2]:
        return SizeBand.LARGE
    return SizeBand.XLARGE


def _percentiles(values: list[int]) -> tuple[int, int, int]:
    if not values:
        return (0, 0, 0)

    def nearest_rank(percent: float) -> int:
        index = max(0, min(len(values) - 1, round((len(values) - 1) * percent)))
        return values[index]

    return nearest_rank(0.50), nearest_rank(0.75), nearest_rank(0.90)
