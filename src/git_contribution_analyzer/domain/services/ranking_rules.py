from __future__ import annotations

import hashlib
import json
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from git_contribution_analyzer.domain.models.ranking import RankingConfig

RANKING_RULE_VERSION = "performance-ranking-v1"
SUPPORTED_DIMENSIONS = ("workload", "difficulty", "delivery")
FOUR_PLACES = Decimal("0.0001")
SIZE_POINTS = {
    "SMALL": Decimal(1),
    "MEDIUM": Decimal(3),
    "LARGE": Decimal(6),
    "XLARGE": Decimal(10),
}
DIFFICULTY_POINTS = {
    "ROUTINE": Decimal(1),
    "STANDARD": Decimal(2),
    "COMPLEX": Decimal(4),
    "HIGH_RISK": Decimal(6),
}


def build_ranking(
    subjects: list[dict[str, Any]],
    dimensions: tuple[str, ...],
    *,
    snapshot_id: str,
    config: RankingConfig | None = None,
) -> dict[str, Any]:
    active_dimensions = dimensions or (SUPPORTED_DIMENSIONS if config is not None else ())
    if not active_dimensions:
        return {
            "enabled": False,
            "ruleVersion": None,
            "cohortFingerprint": None,
            "dimensions": [],
            "composite": None,
            "config": None,
        }
    aggregates = {
        str(subject["person"]["id"]): _aggregate_subject(subject)
        for subject in subjects
    }
    dimension_results = [
        _rank_dimension(dimension, aggregates) for dimension in active_dimensions
    ]
    fingerprint_payload = {
        "snapshotId": snapshot_id,
        "ruleVersion": RANKING_RULE_VERSION,
        "personIds": sorted(aggregates),
        "dimensions": list(active_dimensions),
        "config": config.as_dict() if config is not None else None,
    }
    fingerprint = hashlib.sha256(
        json.dumps(
            fingerprint_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return {
        "enabled": True,
        "ruleVersion": RANKING_RULE_VERSION,
        "cohortFingerprint": fingerprint,
        "dimensions": dimension_results,
        "composite": _build_composite(aggregates, config) if config is not None else None,
        "config": config.as_dict() if config is not None else None,
    }


def _aggregate_subject(subject: dict[str, Any]) -> dict[str, Any]:
    items = subject["itemAssessments"]
    completed = [item for item in items if item["completionBucket"] == "COMPLETED"]
    rework = [item for item in items if item["completionBucket"] == "REWORK"]
    workload = sum(
        (SIZE_POINTS[item["size"]["band"]] for item in completed),
        start=Decimal(0),
    )
    difficulty = sum(
        (DIFFICULTY_POINTS[item["difficulty"]["level"]] for item in completed),
        start=Decimal(0),
    )
    if completed:
        rework_ratio = Decimal(len(rework)) / Decimal(len(completed))
        penalty_ratio = min(rework_ratio * Decimal("0.15"), Decimal("0.30"))
        delivery = Decimal(len(completed)) * (Decimal(1) - penalty_ratio)
    else:
        delivery = Decimal(0)
    completed_evidence = {
        evidence_id for item in completed for evidence_id in item["evidenceIds"]
    }
    delivery_evidence = completed_evidence | {
        evidence_id for item in rework for evidence_id in item["evidenceIds"]
    }
    gaps = sorted(
        {
            gap
            for item in completed
            for gap in [*item["size"]["gaps"], *item["difficulty"]["gaps"]]
        }
    )
    confidence = "LOW" if not completed else ("MEDIUM" if gaps else "HIGH")
    return {
        "workload": workload,
        "difficulty": difficulty,
        "delivery": delivery,
        "workloadEvidenceIds": sorted(completed_evidence),
        "difficultyEvidenceIds": sorted(completed_evidence),
        "deliveryEvidenceIds": sorted(delivery_evidence),
        "confidence": confidence,
        "gaps": gaps,
    }


def _rank_dimension(
    dimension: str, aggregates: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    values = {
        person_id: _quantize(aggregate[dimension])
        for person_id, aggregate in aggregates.items()
    }
    ranks = {
        value: rank
        for rank, value in enumerate(sorted(set(values.values()), reverse=True), start=1)
    }
    entries = []
    for person_id in sorted(values, key=lambda value: (-values[value], value)):
        raw_value = values[person_id]
        aggregate = aggregates[person_id]
        entries.append(
            {
                "personId": person_id,
                "rawValue": _serialize_decimal(raw_value),
                "rank": ranks[raw_value],
                "tieKey": _serialize_decimal(raw_value),
                "evidenceIds": aggregate[f"{dimension}EvidenceIds"],
                "confidence": aggregate["confidence"],
                "gaps": aggregate["gaps"],
            }
        )
    return {"dimension": dimension, "entries": entries}


def _build_composite(
    aggregates: dict[str, dict[str, Any]], config: RankingConfig
) -> dict[str, Any]:
    maxima = {
        dimension: max(
            (aggregate[dimension] for aggregate in aggregates.values()),
            default=Decimal(0),
        )
        for dimension in SUPPORTED_DIMENSIONS
    }
    rows: dict[str, dict[str, Any]] = {}
    for person_id, aggregate in aggregates.items():
        normalized = {
            dimension: (
                Decimal(0)
                if maxima[dimension] == 0
                else aggregate[dimension] / maxima[dimension] * Decimal(100)
            )
            for dimension in SUPPORTED_DIMENSIONS
        }
        weighted = {
            "workload": normalized["workload"] * config.weights.workload,
            "difficulty": normalized["difficulty"] * config.weights.difficulty,
            "delivery": normalized["delivery"] * config.weights.delivery,
        }
        total = sum(weighted.values(), start=Decimal(0))
        tie_key = (
            _quantize(total),
            _quantize(normalized["workload"]),
            _quantize(normalized["difficulty"]),
            _quantize(normalized["delivery"]),
        )
        rows[person_id] = {
            "normalized": normalized,
            "weighted": weighted,
            "total": total,
            "tieKey": tie_key,
        }
    ranked_keys = sorted(
        {row["tieKey"] for row in rows.values()},
        reverse=True,
    )
    ranks = {key: rank for rank, key in enumerate(ranked_keys, start=1)}
    entries = []
    for person_id in sorted(
        rows,
        key=lambda value: (*(-part for part in rows[value]["tieKey"]), value),
    ):
        row = rows[person_id]
        entries.append(
            {
                "personId": person_id,
                "totalScore": _serialize_decimal(row["total"]),
                "totalRank": ranks[row["tieKey"]],
                "normalized": {
                    dimension: _serialize_decimal(row["normalized"][dimension])
                    for dimension in SUPPORTED_DIMENSIONS
                },
                "weighted": {
                    dimension: _serialize_decimal(row["weighted"][dimension])
                    for dimension in SUPPORTED_DIMENSIONS
                },
                "tieKey": [_serialize_decimal(value) for value in row["tieKey"]],
            }
        )
    return {
        "normalization": config.normalization,
        "ties": config.ties,
        "entries": entries,
    }


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)


def _serialize_decimal(value: Decimal) -> str:
    return format(_quantize(value), ".4f")
