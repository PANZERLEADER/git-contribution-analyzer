from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from git_contribution_analyzer.domain.errors import ConfigurationError
from git_contribution_analyzer.domain.models.resume import VerifiedOutcome


class _Outcome(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    source: str = Field(min_length=1)
    verified_by: str = Field(alias="verifiedBy", min_length=1)
    verified_at: date = Field(alias="verifiedAt")
    kind: str = "OUTCOME"


class _OutcomeFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcomes: list[_Outcome]


def load_verified_outcomes(path: Path) -> tuple[VerifiedOutcome, ...]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        parsed = _OutcomeFile.model_validate(payload)
    except (OSError, yaml.YAMLError, ValidationError, ValueError) as exc:
        raise ConfigurationError(f"Invalid verified outcomes file: {path}") from exc
    ids = [entry.id for entry in parsed.outcomes]
    if len(ids) != len(set(ids)):
        raise ConfigurationError("Verified outcome IDs must be unique")
    return tuple(
        VerifiedOutcome(
            id=entry.id,
            text=entry.text,
            source=entry.source,
            verified_by=entry.verified_by,
            verified_at=entry.verified_at,
            kind=entry.kind.upper(),
        )
        for entry in parsed.outcomes
    )
