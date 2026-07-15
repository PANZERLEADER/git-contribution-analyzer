from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

_STAGE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True, slots=True, kw_only=True)
class ProgressEvent:
    task_id: str
    operation: str
    stage: str
    repository: Path
    current: int | None = None
    total: int | None = None
    message: str = ""
    occurred_at: datetime
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        if not _STAGE_PATTERN.fullmatch(self.stage):
            raise ValueError("Progress stage must be a stable lower_snake_case identifier")
        if (self.current is None) != (self.total is None):
            raise ValueError("Progress current and total must be provided together")
        if (
            self.current is not None
            and self.total is not None
            and (self.current < 0 or self.total < 0 or self.current > self.total)
        ):
            raise ValueError("Progress counts must satisfy 0 <= current <= total")


class ProgressReporter(Protocol):
    def report(self, event: ProgressEvent) -> None: ...


class NullProgressReporter:
    def report(self, event: ProgressEvent) -> None:
        del event
