from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_project_should_define_optional_gui_dependency_and_entrypoint() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "gui = [" in pyproject
    assert '"PySide6>=' in pyproject
    assert 'gca-gui = "git_contribution_analyzer.adapters.gui.app:main"' in pyproject
