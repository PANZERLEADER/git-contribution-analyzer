from __future__ import annotations

from pathlib import Path

from git_contribution_analyzer.adapters.gui.settings import GuiSettings


def test_settings_should_keep_ten_most_recent_unique_repositories(tmp_path: Path) -> None:
    settings = GuiSettings(tmp_path / "settings.ini")
    repositories = [tmp_path / f"repo-{index}" for index in range(12)]

    for repository in repositories:
        settings.remember_repository(repository)
    settings.remember_repository(repositories[5])

    recent = settings.recent_repositories()
    assert len(recent) == 10
    assert recent[0] == str(repositories[5].resolve())
    assert len(recent) == len(set(recent))


def test_settings_should_not_contain_credential_keys(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.ini"
    settings = GuiSettings(settings_path)

    settings.set_theme("dark")
    settings.remember_repository(tmp_path / "repo")

    content = settings_path.read_text(encoding="utf-8")
    assert "apiKey" not in content
    assert "token" not in content.casefold()
