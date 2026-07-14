from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CapabilityAssessment:
    capability: str
    confidence: str
    rationale: str
    evidence_ids: tuple[str, ...]
    gaps: tuple[str, ...] = ()
