from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class SelectionMode(StrEnum):
    EXPLICIT = "EXPLICIT"
    ALL = "ALL"


@dataclass(frozen=True, slots=True)
class PersonExclusion:
    selector: str | None
    person_id: str | None
    reason: str

    def as_dict(self) -> dict[str, str | None]:
        return {
            "selector": self.selector,
            "personId": self.person_id,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class PersonSelection:
    mode: SelectionMode
    requested_selectors: tuple[str, ...]
    included_person_ids: tuple[str, ...]
    exclusions: tuple[PersonExclusion, ...]
    confirmed_only: bool = True
    allowed_kinds: tuple[str, ...] = ("HUMAN",)
    warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "requestedSelectors": list(self.requested_selectors),
            "includedPersonIds": list(self.included_person_ids),
            "exclusions": [exclusion.as_dict() for exclusion in self.exclusions],
            "confirmedOnly": self.confirmed_only,
            "allowedKinds": list(self.allowed_kinds),
            "warnings": list(self.warnings),
        }
