from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Confidence = Literal["HIGH", "MEDIUM", "LOW"]


class SemanticClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    text: str = Field(min_length=1)
    evidence_ids: list[str] = Field(alias="evidenceIds", min_length=1)
    confidence: Confidence


class ContributionSummary(SemanticClaim):
    contribution_item_id: str = Field(alias="contributionItemId")


class CapabilityExplanation(SemanticClaim):
    capability: str = Field(min_length=1)


class SemanticEnhancement(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    overall_summary: list[SemanticClaim] = Field(alias="overallSummary", min_length=1)
    contribution_summaries: list[ContributionSummary] = Field(alias="contributionSummaries")
    capability_explanations: list[CapabilityExplanation] = Field(
        alias="capabilityExplanations"
    )
    resume_bullets: list[SemanticClaim] = Field(alias="resumeBullets")
