from __future__ import annotations

from pathlib import Path
from typing import Any

from git_contribution_analyzer.adapters.git.repository_discovery import discover_repository
from git_contribution_analyzer.adapters.llm.registry import build_provider
from git_contribution_analyzer.adapters.workspace.config import load_config
from git_contribution_analyzer.adapters.workspace.layout import WorkspaceLayout


def test_provider(path: Path) -> dict[str, Any]:
    repository = discover_repository(path)
    config = load_config(WorkspaceLayout.for_repository(repository.root).config)
    provider = build_provider(config.llm)
    healthy = provider.health_check()
    return {
        "provider": provider.provider_id,
        "model": provider.model,
        "healthy": healthy,
        "localExecution": provider.capabilities.local_execution,
    }
