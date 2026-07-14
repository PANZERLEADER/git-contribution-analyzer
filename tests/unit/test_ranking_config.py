from __future__ import annotations

from pathlib import Path

import pytest

from git_contribution_analyzer.adapters.workspace.ranking_config import load_ranking_config
from git_contribution_analyzer.domain.errors import ConfigurationError


def test_should_load_explicit_decimal_ranking_weights(tmp_path: Path) -> None:
    path = tmp_path / "ranking.yml"
    path.write_text(
        """schemaVersion: "1.0"
rankingRuleVersion: performance-ranking-v1
weights:
  workload: 0.45
  difficulty: 0.35
  delivery: 0.20
normalization: cohort-max
ties: dense
""",
        encoding="utf-8",
    )

    config = load_ranking_config(path)

    assert str(config.weights.workload) == "0.45"
    assert config.as_dict()["normalization"] == "cohort-max"


@pytest.mark.parametrize(
    "weights",
    [
        "workload: 0.5\n  difficulty: 0.5\n  delivery: 0.5",
        "workload: -0.1\n  difficulty: 0.6\n  delivery: 0.5",
        "workload: .nan\n  difficulty: 0.5\n  delivery: 0.5",
    ],
)
def test_should_reject_invalid_ranking_weights(tmp_path: Path, weights: str) -> None:
    path = tmp_path / "ranking.yml"
    path.write_text(
        "schemaVersion: '1.0'\n"
        "rankingRuleVersion: performance-ranking-v1\n"
        f"weights:\n  {weights}\n"
        "normalization: cohort-max\n"
        "ties: dense\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError):
        load_ranking_config(path)
