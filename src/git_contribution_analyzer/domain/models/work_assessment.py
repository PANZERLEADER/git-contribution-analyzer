from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SizeBand(StrEnum):
    SMALL = "SMALL"
    MEDIUM = "MEDIUM"
    LARGE = "LARGE"
    XLARGE = "XLARGE"


class DifficultyLevel(StrEnum):
    ROUTINE = "ROUTINE"
    STANDARD = "STANDARD"
    COMPLEX = "COMPLEX"
    HIGH_RISK = "HIGH_RISK"


class CompletionBucket(StrEnum):
    COMPLETED = "COMPLETED"
    PENDING = "PENDING"
    REWORK = "REWORK"
    INTEGRATION = "INTEGRATION"


@dataclass(frozen=True, slots=True)
class WorkItemSizeAssessment:
    band: SizeBand
    effective_files: int
    effective_churn: int
    module_span: int
    baseline_sample_size: int
    baseline_mode: str
    rule_version: str
    evidence_ids: tuple[str, ...]
    excluded_changes: tuple[str, ...] = ()
    confidence: str = "MEDIUM"
    gaps: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class WorkloadBaseline:
    sample_size: int
    churn_percentiles: tuple[int, int, int]
    file_percentiles: tuple[int, int, int]
    module_percentiles: tuple[int, int, int]


@dataclass(frozen=True, slots=True)
class DimensionSignal:
    dimension: str
    code: str
    severity: str
    description: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DifficultyAssessment:
    level: DifficultyLevel
    dimension_signals: tuple[DimensionSignal, ...]
    rule_version: str
    evidence_ids: tuple[str, ...]
    confidence: str
    gaps: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WorkItemAssessment:
    contribution_item_id: str
    person_id: str
    completion_bucket: CompletionBucket
    delivery_statuses: tuple[str, ...]
    work_type: str
    size: WorkItemSizeAssessment
    difficulty: DifficultyAssessment
    engineering_support: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    warnings: tuple[str, ...] = ()
