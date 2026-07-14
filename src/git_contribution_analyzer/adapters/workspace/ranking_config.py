from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from git_contribution_analyzer.domain.errors import ConfigurationError
from git_contribution_analyzer.domain.models.ranking import RankingConfig


def load_ranking_config(path: Path) -> RankingConfig:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        return RankingConfig.model_validate(raw)
    except (OSError, yaml.YAMLError, ValidationError, TypeError) as exc:
        raise ConfigurationError(f"Invalid ranking configuration: {path}: {exc}") from exc
