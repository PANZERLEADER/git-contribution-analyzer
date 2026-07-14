from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class WorkspaceLayout:
    repository_root: Path
    root: Path
    config: Path
    metadata: Path
    database: Path
    identities: Path
    cache: Path
    runs: Path
    reports: Path
    locks: Path

    @classmethod
    def for_repository(cls, repository_root: Path) -> WorkspaceLayout:
        resolved_root = repository_root.resolve()
        root = resolved_root / ".gca"
        return cls(
            repository_root=resolved_root,
            root=root,
            config=root / "config.yml",
            metadata=root / "meta.json",
            database=root / "index.sqlite",
            identities=root / "identities.yml",
            cache=root / "cache",
            runs=root / "runs",
            reports=root / "reports",
            locks=root / "locks",
        )

    def create_directories(self) -> None:
        self.root.mkdir(parents=False, exist_ok=True)
        for directory in (self.cache, self.runs, self.reports, self.locks):
            directory.mkdir(parents=True, exist_ok=True)
