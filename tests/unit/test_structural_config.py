from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from git_contribution_analyzer.adapters.workspace.config import (
    StructuralConfig,
    write_default_config,
)
from git_contribution_analyzer.application.use_cases.manage_structural_baselines import (
    _filter_fingerprint,
)
from git_contribution_analyzer.domain.models.structural_baseline import (
    StructuralRuleConfig,
    StructuralTimeStrategy,
)

ROOT = Path(__file__).parents[2]


def test_default_workspace_config_should_include_community_structural_profile(
    tmp_path: Path,
) -> None:
    path = tmp_path / "config.yml"

    write_default_config(path, "main")

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert raw["structural"] == {
        "profile": "community-baseline-v1",
        "timeStrategy": "DUAL_WINDOW",
        "minimumBaselineCommits": 50,
        "hotspotPercentile": 0.95,
        "minimumCoChangeCount": 3,
        "minimumSubsetRatio": 0.8,
        "minimumJaccard": 0.3,
        "minimumHubPenalty": 0.5,
        "maximumContextPaths": 100,
        "rollingWindowDays": 365,
        "automaticDifficultyPromotion": False,
    }


def test_structural_profile_should_convert_to_rule_config_with_optional_cli_override() -> None:
    config = StructuralConfig()

    defaults = config.to_rule_config()
    overridden = config.to_rule_config(time_strategy=StructuralTimeStrategy.ROLLING_WINDOW)

    assert defaults == StructuralRuleConfig(
        time_strategy=StructuralTimeStrategy.DUAL_WINDOW,
        minimum_baseline_commits=50,
        hotspot_percentile=0.95,
        minimum_co_change_count=3,
        minimum_subset_ratio=0.8,
        minimum_jaccard=0.3,
        minimum_hub_penalty=0.5,
        maximum_context_paths=100,
        rolling_window_days=365,
    )
    assert overridden == replace(
        defaults,
        time_strategy=StructuralTimeStrategy.ROLLING_WINDOW,
    )


def test_automatic_difficulty_promotion_should_remain_disabled() -> None:
    with pytest.raises(ValueError, match="automaticDifficultyPromotion"):
        StructuralConfig(automaticDifficultyPromotion=True)


def test_community_profile_json_should_match_runtime_defaults() -> None:
    canonical = json.loads(
        (ROOT / "config" / "structural-community-baseline-v1.json").read_text(
            encoding="utf-8"
        )
    )

    assert canonical["status"] == "COMMUNITY_BASELINE_READY_OBSERVATION_ONLY"
    assert canonical["policy"] == {
        "mode": "OBSERVATION_ONLY",
        "automaticDifficultyPromotion": False,
        "empiricalCalibrationRequiredForPromotion": True,
    }
    assert canonical["structural"] == StructuralConfig().model_dump(
        by_alias=True,
        mode="json",
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("time_strategy", StructuralTimeStrategy.ROLLING_WINDOW),
        ("minimum_baseline_commits", 51),
        ("hotspot_percentile", 0.96),
        ("minimum_co_change_count", 4),
        ("minimum_subset_ratio", 0.81),
        ("minimum_jaccard", 0.31),
        ("minimum_hub_penalty", 0.51),
        ("maximum_context_paths", 101),
        ("rolling_window_days", 366),
    ],
)
def test_filter_fingerprint_should_change_for_every_structural_rule(
    field: str,
    value: object,
) -> None:
    baseline = StructuralRuleConfig(
        time_strategy=StructuralTimeStrategy.DUAL_WINDOW,
        minimum_baseline_commits=50,
        hotspot_percentile=0.95,
        minimum_co_change_count=3,
        minimum_subset_ratio=0.8,
        minimum_jaccard=0.3,
        minimum_hub_penalty=0.5,
        maximum_context_paths=100,
        rolling_window_days=365,
    )

    assert _filter_fingerprint("refs/heads/main", None, baseline) != _filter_fingerprint(
        "refs/heads/main",
        None,
        replace(baseline, **{field: value}),
    )
