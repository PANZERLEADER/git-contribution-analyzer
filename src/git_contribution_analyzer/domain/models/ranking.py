from __future__ import annotations

from decimal import Decimal
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RankingWeights(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workload: Decimal = Field(ge=0, le=1)
    difficulty: Decimal = Field(ge=0, le=1)
    delivery: Decimal = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_values(self) -> Self:
        values = (self.workload, self.difficulty, self.delivery)
        if any(not value.is_finite() for value in values):
            raise ValueError("ranking weights must be finite")
        if sum(values, start=Decimal(0)) != Decimal(1):
            raise ValueError("ranking weights must sum exactly to 1.0")
        return self


class RankingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: str = Field(alias="schemaVersion", pattern=r"^1\.0$")
    ranking_rule_version: str = Field(
        alias="rankingRuleVersion", pattern=r"^performance-ranking-v1$"
    )
    weights: RankingWeights
    normalization: str = Field(pattern=r"^cohort-max$")
    ties: str = Field(pattern=r"^dense$")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "rankingRuleVersion": self.ranking_rule_version,
            "weights": {
                "workload": str(self.weights.workload),
                "difficulty": str(self.weights.difficulty),
                "delivery": str(self.weights.delivery),
            },
            "normalization": self.normalization,
            "ties": self.ties,
        }
