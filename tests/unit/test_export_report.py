from __future__ import annotations

from pathlib import Path

import pytest

from git_contribution_analyzer.application.use_cases import export_report as export_module


def test_export_should_write_generated_report_atomically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "report.md"
    monkeypatch.setattr(export_module, "generate_report", lambda *args, **kwargs: "report\n")

    result = export_module.export_report(
        Path("repository"),
        "run-1",
        "markdown",
        target,
        overwrite=False,
    )

    assert result == target.resolve()
    assert target.read_text(encoding="utf-8") == "report\n"
    assert list(tmp_path.glob("*.tmp")) == []


def test_export_should_reject_existing_target_without_overwrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "report.md"
    target.write_text("existing", encoding="utf-8")
    monkeypatch.setattr(export_module, "generate_report", lambda *args, **kwargs: "replacement")

    with pytest.raises(FileExistsError):
        export_module.export_report(
            Path("repository"),
            "run-1",
            "markdown",
            target,
            overwrite=False,
        )

    assert target.read_text(encoding="utf-8") == "existing"
