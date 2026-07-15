from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class AnalysisFilters:
    since: datetime | None = None
    until: datetime | None = None
    branch: str | None = None
    release: str | None = None
    scope: str | None = None
    delivery: str | None = None
    time_basis: str = "AUTHORED"

    def as_dict(self) -> dict[str, str | None]:
        result = {
            "since": self.since.isoformat() if self.since else None,
            "until": self.until.isoformat() if self.until else None,
            "branch": self.branch,
            "release": self.release,
            "scope": self.scope,
            "delivery": self.delivery,
        }
        if self.time_basis != "AUTHORED":
            result["timeBasis"] = self.time_basis
        return result
