from __future__ import annotations

from pathlib import Path

import pytest

from git_contribution_analyzer.adapters.outcomes.yaml_loader import load_verified_outcomes
from git_contribution_analyzer.domain.errors import ConfigurationError


def test_should_load_strict_verified_outcome_yaml(tmp_path: Path) -> None:
    path = tmp_path / "outcomes.yml"
    path.write_text(
        """outcomes:
  - id: OUT-001
    text: API latency reduced by 35%
    source: benchmark.md
    verifiedBy: team-lead
    verifiedAt: 2026-01-01
""",
        encoding="utf-8",
    )

    outcomes = load_verified_outcomes(path)

    assert outcomes[0].id == "OUT-001"
    assert outcomes[0].verified_by == "team-lead"


def test_should_reject_unknown_outcome_fields(tmp_path: Path) -> None:
    path = tmp_path / "invalid.yml"
    path.write_text(
        """outcomes:
  - id: OUT-001
    text: result
    source: report.md
    verifiedBy: lead
    verifiedAt: 2026-01-01
    invented: true
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError):
        load_verified_outcomes(path)
