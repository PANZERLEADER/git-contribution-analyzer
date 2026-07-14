from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class ClaimStrength(StrEnum):
    CONTRIBUTED = "CONTRIBUTED"
    IMPLEMENTED = "IMPLEMENTED"
    LED = "LED"


class ResumeStyle(StrEnum):
    CONCISE = "concise"
    STAR = "star"
    XYZ = "xyz"


class ResumeLanguage(StrEnum):
    ZH_CN = "zh-CN"
    EN_US = "en-US"


@dataclass(frozen=True, slots=True)
class VerifiedOutcome:
    id: str
    text: str
    source: str
    verified_by: str
    verified_at: date
    kind: str = "OUTCOME"


@dataclass(frozen=True, slots=True)
class ResumeClaim:
    text: str
    claim_strength: ClaimStrength
    contribution_item_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    verified_outcome_ids: tuple[str, ...]
    confidence: str
    pending: bool


@dataclass(frozen=True, slots=True)
class SkillEvidence:
    skill: str
    evidence_ids: tuple[str, ...]
    contribution_item_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OmittedClaim:
    candidate: str
    reason_code: str
    missing_evidence: tuple[str, ...]
