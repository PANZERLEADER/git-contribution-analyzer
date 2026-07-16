from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class StructuralTimeStrategy(StrEnum):
    LIFETIME = "LIFETIME"
    ROLLING_WINDOW = "ROLLING_WINDOW"
    DUAL_WINDOW = "DUAL_WINDOW"


@dataclass(frozen=True, slots=True)
class StructuralRuleConfig:
    time_strategy: StructuralTimeStrategy = StructuralTimeStrategy.LIFETIME
    minimum_baseline_commits: int = 2
    hotspot_percentile: float = 0.90
    minimum_co_change_count: int = 2
    minimum_subset_ratio: float = 0.75
    minimum_jaccard: float = 0.20
    minimum_hub_penalty: float = 0.0
    maximum_context_paths: int = 200
    rolling_window_days: int = 365

    def __post_init__(self) -> None:
        if self.minimum_baseline_commits < 1:
            raise ValueError("minimum_baseline_commits must be positive")
        if self.minimum_co_change_count < 1:
            raise ValueError("minimum_co_change_count must be positive")
        if self.maximum_context_paths < 1:
            raise ValueError("maximum_context_paths must be positive")
        if self.rolling_window_days < 1:
            raise ValueError("rolling_window_days must be positive")
        for name, value in (
            ("hotspot_percentile", self.hotspot_percentile),
            ("minimum_subset_ratio", self.minimum_subset_ratio),
            ("minimum_jaccard", self.minimum_jaccard),
            ("minimum_hub_penalty", self.minimum_hub_penalty),
        ):
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class StructuralFileCount:
    path: str
    change_count: int
    recent_change_count: int


@dataclass(frozen=True, slots=True)
class StructuralEdgeCount:
    left_path: str
    right_path: str
    co_change_count: int
    recent_co_change_count: int


@dataclass(frozen=True, slots=True)
class StructuralFileMetric:
    path: str
    change_count: int
    percentile: float
    recent_percentile: float
    confidence: str


@dataclass(frozen=True, slots=True)
class StructuralEdgeMetric:
    left_path: str
    right_path: str
    co_change_count: int
    subset_ratio: float
    left_conditional: float
    right_conditional: float
    jaccard: float
    hub_penalty: float
    cross_module: bool
    confidence: str


@dataclass(frozen=True, slots=True)
class StructuralBaselineSummary:
    eligible_commits: int
    eligible_files: int
    raw_edges: int
    capped_commits: int


@dataclass(frozen=True, slots=True)
class StructuralMaterialization:
    baseline_id: str
    file_metrics: tuple[StructuralFileMetric, ...]
    edge_metrics: tuple[StructuralEdgeMetric, ...]
    confidence: str
    gaps: tuple[str, ...]
    limitations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StructuralBaseline:
    id: str
    cutoff: datetime
    config: StructuralRuleConfig
    summary: StructuralBaselineSummary
    file_counts: tuple[StructuralFileCount, ...]
    edge_counts: tuple[StructuralEdgeCount, ...]
    materialization: StructuralMaterialization
    supporting_commits: Mapping[str, tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class WorkItemStructuralContext:
    baseline_id: str
    hotspot_exposures: tuple[StructuralFileMetric, ...]
    coupling_exposures: tuple[StructuralEdgeMetric, ...]
    confidence: str
    gaps: tuple[str, ...]
