from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from git_contribution_analyzer.domain.errors import ConfigurationError


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


class ProjectConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: str = Field(default="1.0", alias="schemaVersion")
    default_branch: str = Field(alias="defaultBranch")
    refs: list[str] = Field(
        default_factory=lambda: ["refs/heads/*", "refs/remotes/origin/*", "refs/tags/*"]
    )
    llm: LlmConfig = Field(default_factory=LlmConfig)


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
