from __future__ import annotations

import importlib
from datetime import timedelta, timezone

import pytest


def test_should_interpret_naive_boundary_in_system_timezone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cli_app = importlib.import_module("git_contribution_analyzer.cli.app")
    china = timezone(timedelta(hours=8))
    monkeypatch.setattr(
        cli_app,
        "_localize_system_time",
        lambda value: value.replace(tzinfo=china),
    )

    parsed = cli_app._parse_boundary("2026-07-01T09:30:00", end_of_day=False)

    assert parsed.isoformat() == "2026-07-01T09:30:00+08:00"


def test_should_preserve_explicit_timezone_boundary() -> None:
    cli_app = importlib.import_module("git_contribution_analyzer.cli.app")

    parsed = cli_app._parse_boundary("2026-07-01T09:30:00+02:00", end_of_day=False)

    assert parsed.isoformat() == "2026-07-01T09:30:00+02:00"
