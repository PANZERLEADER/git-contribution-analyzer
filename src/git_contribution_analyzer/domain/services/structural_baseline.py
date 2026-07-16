from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import asdict
from datetime import datetime, timedelta
from itertools import combinations
from types import MappingProxyType

from git_contribution_analyzer.domain.models.contribution import (
    ContributionCommit,
    ContributionItem,
)
from git_contribution_analyzer.domain.models.structural_baseline import (
    StructuralBaseline,
    StructuralBaselineSummary,
    StructuralEdgeCount,
    StructuralEdgeMetric,
    StructuralFileCount,
    StructuralFileMetric,
    StructuralMaterialization,
    StructuralRuleConfig,
    StructuralTimeStrategy,
    WorkItemStructuralContext,
)
from git_contribution_analyzer.domain.services.contribution_rules import is_generated_path

STRUCTURAL_FACT_RULE_VERSION = "structural-facts-v1"
STRUCTURAL_METRIC_RULE_VERSION = "structural-metrics-v1"
STRUCTURAL_THRESHOLD_VERSION = "structural-thresholds-community-v1"

_LIMITATIONS = (
    "Historical co-change is an association, not a runtime dependency.",
    "Historical hotspots are context signals, not individual performance conclusions.",
    "Mechanical and oversized changes may be excluded or lower confidence.",
)


def build_structural_baseline(
    commits: Iterable[ContributionCommit],
    *,
    cutoff: datetime,
    config: StructuralRuleConfig | None = None,
    identity_context: dict[str, str | None] | None = None,
) -> StructuralBaseline:
    active_config = config or StructuralRuleConfig()
    seen_patches: set[str] = set()
    file_commits: defaultdict[str, set[str]] = defaultdict(set)
    recent_file_commits: defaultdict[str, set[str]] = defaultdict(set)
    edge_commits: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
    recent_edge_commits: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
    supporting: defaultdict[str, set[str]] = defaultdict(set)
    eligible_hashes: list[str] = []
    capped_commits = 0
    recent_boundary = cutoff - timedelta(days=active_config.rolling_window_days)

    ordered = sorted(commits, key=lambda value: (_occurred_at(value), value.hash))
    for commit in ordered:
        occurred_at = _occurred_at(commit)
        if occurred_at >= cutoff or commit.merge:
            continue
        patch_key = commit.patch_id or commit.hash
        if patch_key in seen_patches:
            continue
        seen_patches.add(patch_key)
        paths = _eligible_paths(commit)
        if not paths:
            continue
        is_recent = occurred_at >= recent_boundary
        if active_config.time_strategy is StructuralTimeStrategy.ROLLING_WINDOW and not is_recent:
            continue
        eligible_hashes.append(commit.hash)
        for path in paths:
            file_commits[path].add(commit.hash)
            supporting[f"file:{path}"].add(commit.hash)
            if is_recent:
                recent_file_commits[path].add(commit.hash)
        if len(paths) > active_config.maximum_context_paths:
            capped_commits += 1
            continue
        for left_path, right_path in combinations(paths, 2):
            edge = (left_path, right_path)
            edge_commits[edge].add(commit.hash)
            supporting[_edge_key(edge)].add(commit.hash)
            if is_recent:
                recent_edge_commits[edge].add(commit.hash)

    file_counts = tuple(
        StructuralFileCount(
            path=path,
            change_count=len(hashes),
            recent_change_count=len(recent_file_commits[path]),
        )
        for path, hashes in sorted(file_commits.items())
    )
    edge_counts = tuple(
        StructuralEdgeCount(
            left_path=edge[0],
            right_path=edge[1],
            co_change_count=len(hashes),
            recent_co_change_count=len(recent_edge_commits[edge]),
        )
        for edge, hashes in sorted(edge_commits.items())
        if hashes
    )
    baseline_id = _baseline_id(
        eligible_hashes,
        cutoff,
        active_config,
        file_counts,
        edge_counts,
        identity_context or {},
    )
    summary = StructuralBaselineSummary(
        eligible_commits=len(eligible_hashes),
        eligible_files=len(file_counts),
        raw_edges=len(edge_counts),
        capped_commits=capped_commits,
    )
    materialization = _materialize(
        baseline_id,
        summary,
        file_counts,
        edge_counts,
        active_config,
    )
    immutable_supporting = MappingProxyType(
        {key: tuple(sorted(value)) for key, value in sorted(supporting.items())}
    )
    return StructuralBaseline(
        id=baseline_id,
        cutoff=cutoff,
        config=active_config,
        summary=summary,
        file_counts=file_counts,
        edge_counts=edge_counts,
        materialization=materialization,
        supporting_commits=immutable_supporting,
    )


def match_work_item_structural_context(
    item: ContributionItem,
    materialization: StructuralMaterialization,
) -> WorkItemStructuralContext:
    paths = {path.replace("\\", "/").strip("/") for path in item.paths}
    hotspots = tuple(entry for entry in materialization.file_metrics if entry.path in paths)
    couplings = tuple(
        entry
        for entry in materialization.edge_metrics
        if entry.left_path in paths and entry.right_path in paths
    )
    return WorkItemStructuralContext(
        baseline_id=materialization.baseline_id,
        hotspot_exposures=hotspots,
        coupling_exposures=couplings,
        confidence=materialization.confidence,
        gaps=materialization.gaps,
    )


def _materialize(
    baseline_id: str,
    summary: StructuralBaselineSummary,
    file_counts: tuple[StructuralFileCount, ...],
    edge_counts: tuple[StructuralEdgeCount, ...],
    config: StructuralRuleConfig,
) -> StructuralMaterialization:
    if summary.eligible_commits < config.minimum_baseline_commits:
        insufficient_gaps = ["INSUFFICIENT_STRUCTURAL_BASELINE"]
        if summary.capped_commits:
            insufficient_gaps.append("STRUCTURAL_CONTEXT_CAPPED")
        return StructuralMaterialization(
            baseline_id=baseline_id,
            file_metrics=(),
            edge_metrics=(),
            confidence="LOW",
            gaps=tuple(insufficient_gaps),
            limitations=_LIMITATIONS,
        )

    confidence = _confidence(summary.eligible_commits, config.minimum_baseline_commits)
    change_counts = tuple(entry.change_count for entry in file_counts)
    recent_counts = tuple(entry.recent_change_count for entry in file_counts)
    file_metrics = tuple(
        StructuralFileMetric(
            path=entry.path,
            change_count=entry.change_count,
            percentile=_percentile(entry.change_count, change_counts),
            recent_percentile=_percentile(entry.recent_change_count, recent_counts),
            confidence=confidence,
        )
        for entry in file_counts
        if _percentile(entry.change_count, change_counts) >= config.hotspot_percentile
    )
    by_path = {entry.path: entry.change_count for entry in file_counts}
    edge_metrics: list[StructuralEdgeMetric] = []
    for entry in edge_counts:
        left_count = by_path[entry.left_path]
        right_count = by_path[entry.right_path]
        subset_ratio = entry.co_change_count / min(left_count, right_count)
        left_conditional = entry.co_change_count / left_count
        right_conditional = entry.co_change_count / right_count
        union = left_count + right_count - entry.co_change_count
        jaccard = entry.co_change_count / union if union else 0.0
        hub_frequency = max(left_count, right_count) / summary.eligible_commits
        hub_penalty = max(0.0, 1.0 - hub_frequency)
        if (
            entry.co_change_count < config.minimum_co_change_count
            or subset_ratio < config.minimum_subset_ratio
            or jaccard < config.minimum_jaccard
            or hub_penalty < config.minimum_hub_penalty
        ):
            continue
        edge_metrics.append(
            StructuralEdgeMetric(
                left_path=entry.left_path,
                right_path=entry.right_path,
                co_change_count=entry.co_change_count,
                subset_ratio=round(subset_ratio, 6),
                left_conditional=round(left_conditional, 6),
                right_conditional=round(right_conditional, 6),
                jaccard=round(jaccard, 6),
                hub_penalty=round(hub_penalty, 6),
                cross_module=_module(entry.left_path) != _module(entry.right_path),
                confidence=confidence,
            )
        )
    edge_metrics.sort(
        key=lambda value: (
            -value.co_change_count,
            -value.jaccard,
            value.left_path,
            value.right_path,
        )
    )
    materialization_gaps = ("STRUCTURAL_CONTEXT_CAPPED",) if summary.capped_commits else ()
    return StructuralMaterialization(
        baseline_id=baseline_id,
        file_metrics=tuple(
            sorted(file_metrics, key=lambda value: (-value.percentile, value.path))
        ),
        edge_metrics=tuple(edge_metrics),
        confidence=confidence,
        gaps=materialization_gaps,
        limitations=_LIMITATIONS,
    )


def _eligible_paths(commit: ContributionCommit) -> tuple[str, ...]:
    if (
        commit.paths
        and commit.binary_files >= len(commit.paths)
        and commit.insertions + commit.deletions == 0
    ):
        return ()
    return tuple(
        sorted(
            {
                normalized
                for path in commit.paths
                if (normalized := path.replace("\\", "/").strip("/"))
                and not is_generated_path(normalized)
            }
        )
    )


def _occurred_at(commit: ContributionCommit) -> datetime:
    return commit.period_at or commit.authored_at


def _module(path: str) -> str:
    normalized = path.strip("/")
    return normalized.split("/", maxsplit=1)[0] if "/" in normalized else "root"


def _edge_key(edge: tuple[str, str]) -> str:
    return f"edge:{edge[0]}\u0000{edge[1]}"


def _percentile(value: int, values: tuple[int, ...]) -> float:
    if not values:
        return 0.0
    return round(sum(candidate <= value for candidate in values) / len(values), 6)


def _confidence(eligible_commits: int, minimum: int) -> str:
    return "HIGH" if eligible_commits >= max(10, minimum * 3) else "MEDIUM"


def _baseline_id(
    hashes: list[str],
    cutoff: datetime,
    config: StructuralRuleConfig,
    file_counts: tuple[StructuralFileCount, ...],
    edge_counts: tuple[StructuralEdgeCount, ...],
    identity_context: dict[str, str | None],
) -> str:
    payload = {
        "cutoff": cutoff.isoformat(),
        "config": {
            **asdict(config),
            "time_strategy": config.time_strategy.value,
        },
        "factRuleVersion": STRUCTURAL_FACT_RULE_VERSION,
        "metricRuleVersion": STRUCTURAL_METRIC_RULE_VERSION,
        "thresholdVersion": STRUCTURAL_THRESHOLD_VERSION,
        "identityContext": identity_context,
        "commits": hashes,
        "files": [asdict(value) for value in file_counts],
        "edges": [asdict(value) for value in edge_counts],
    }
    canonical = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
