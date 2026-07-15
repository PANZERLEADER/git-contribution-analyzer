from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QSettings

_MAX_RECENT_REPOSITORIES = 10


class GuiSettings:
    def __init__(self, path: Path | None = None) -> None:
        self._settings = (
            QSettings(str(path), QSettings.Format.IniFormat)
            if path is not None
            else QSettings("GCA", "Git Contribution Analyzer")
        )

    def remember_repository(self, repository: Path) -> None:
        resolved = str(repository.expanduser().resolve())
        recent = [item for item in self.recent_repositories() if item != resolved]
        recent.insert(0, resolved)
        self._settings.setValue(
            "repositories/recent",
            json.dumps(recent[:_MAX_RECENT_REPOSITORIES], ensure_ascii=False),
        )
        self._settings.sync()

    def recent_repositories(self) -> list[str]:
        raw_value = self._settings.value("repositories/recent", "[]", type=str)
        raw = str(raw_value) if raw_value is not None else "[]"
        try:
            values = json.loads(raw)
        except (TypeError, ValueError):
            return []
        if not isinstance(values, list):
            return []
        return [str(value) for value in values if isinstance(value, str)][:_MAX_RECENT_REPOSITORIES]

    def clear_recent_repositories(self) -> None:
        self._settings.remove("repositories/recent")
        self._settings.sync()

    def set_theme(self, theme: str) -> None:
        normalized = theme.casefold()
        if normalized not in {"system", "light", "dark"}:
            raise ValueError(f"Unsupported theme: {theme}")
        self._settings.setValue("ui/theme", normalized)
        self._settings.sync()

    def theme(self) -> str:
        value = self._settings.value("ui/theme", "system", type=str)
        return str(value) if value is not None else "system"
