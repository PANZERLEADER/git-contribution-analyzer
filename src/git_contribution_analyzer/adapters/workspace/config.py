from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from git_contribution_analyzer.domain.errors import ConfigurationError
from git_contribution_analyzer.domain.models.structural_baseline import (
    StructuralRuleConfig,
    StructuralTimeStrategy,
)


class LlmConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    enabled: bool = False
    provider: str = "mock"
    model: str = "deterministic"
    base_url: str | None = Field(default=None, alias="baseUrl")
    api_key_env: str = Field(default="GCA_LLM_API_KEY", alias="apiKeyEnv")
    executable: str | None = None
    timeout_seconds: float = Field(default=30.0, gt=0, alias="timeoutSeconds")
    command_timeout_seconds: float = Field(
        default=300.0, gt=0, alias="commandTimeoutSeconds"
    )
    max_retries: int = Field(default=2, ge=0, le=10, alias="maxRetries")
    allow_fallback_to_rules: bool = Field(default=True, alias="allowFallbackToRules")


class StructuralConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    profile: str = "community-baseline-v1"
    time_strategy: StructuralTimeStrategy = Field(
        default=StructuralTimeStrategy.DUAL_WINDOW,
        alias="timeStrategy",
    )
    minimum_baseline_commits: int = Field(
        default=50,
        ge=1,
        alias="minimumBaselineCommits",
    )
    hotspot_percentile: float = Field(
        default=0.95,
        ge=0,
        le=1,
        alias="hotspotPercentile",
    )
    minimum_co_change_count: int = Field(
        default=3,
        ge=1,
        alias="minimumCoChangeCount",
    )
    minimum_subset_ratio: float = Field(
        default=0.80,
        ge=0,
        le=1,
        alias="minimumSubsetRatio",
    )
    minimum_jaccard: float = Field(
        default=0.30,
        ge=0,
        le=1,
        alias="minimumJaccard",
    )
    minimum_hub_penalty: float = Field(
        default=0.50,
        ge=0,
        le=1,
        alias="minimumHubPenalty",
    )
    maximum_context_paths: int = Field(
        default=100,
        ge=1,
        alias="maximumContextPaths",
    )
    rolling_window_days: int = Field(
        default=365,
        ge=1,
        alias="rollingWindowDays",
    )
    automatic_difficulty_promotion: Literal[False] = Field(
        default=False,
        alias="automaticDifficultyPromotion",
    )

    def to_rule_config(
        self,
        *,
        time_strategy: StructuralTimeStrategy | None = None,
    ) -> StructuralRuleConfig:
        return StructuralRuleConfig(
            time_strategy=time_strategy or self.time_strategy,
            minimum_baseline_commits=self.minimum_baseline_commits,
            hotspot_percentile=self.hotspot_percentile,
            minimum_co_change_count=self.minimum_co_change_count,
            minimum_subset_ratio=self.minimum_subset_ratio,
            minimum_jaccard=self.minimum_jaccard,
            minimum_hub_penalty=self.minimum_hub_penalty,
            maximum_context_paths=self.maximum_context_paths,
            rolling_window_days=self.rolling_window_days,
        )


class ProjectConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: str = Field(default="1.0", alias="schemaVersion")
    default_branch: str = Field(alias="defaultBranch")
    refs: list[str] = Field(
        default_factory=lambda: ["refs/heads/*", "refs/remotes/origin/*", "refs/tags/*"]
    )
    llm: LlmConfig = Field(default_factory=LlmConfig)
    structural: StructuralConfig = Field(default_factory=StructuralConfig)


def write_default_config(path: Path, default_branch: str) -> None:
    if path.exists():
        return
    config = ProjectConfig(defaultBranch=default_branch)
    data = config.model_dump(by_alias=True, mode="json")
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8", newline="\n")


def load_config(path: Path) -> ProjectConfig:
    if not path.exists():
        raise ConfigurationError(f"Missing workspace configuration: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return ProjectConfig.model_validate(raw)
    except (OSError, yaml.YAMLError, ValueError) as exc:
        raise ConfigurationError(f"Invalid workspace configuration: {path}") from exc
