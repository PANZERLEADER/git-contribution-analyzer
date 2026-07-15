from __future__ import annotations

from pathlib import Path
from typing import Any

from git_contribution_analyzer.adapters.git.repository_discovery import discover_repository
from git_contribution_analyzer.adapters.llm.registry import provider_descriptors
from git_contribution_analyzer.adapters.workspace.config import load_config
from git_contribution_analyzer.adapters.workspace.layout import WorkspaceLayout


def list_providers(path: Path) -> dict[str, Any]:
    repository = discover_repository(path)
    config = load_config(WorkspaceLayout.for_repository(repository.root).config)
    providers = [
        {
            "id": descriptor.provider_id,
            "localExecution": descriptor.local_execution,
            "requiresApiKey": descriptor.requires_api_key,
            "selected": descriptor.provider_id == config.llm.provider,
        }
        for descriptor in provider_descriptors()
    ]
    return {
        "selected": config.llm.provider,
        "enabled": config.llm.enabled,
        "apiKeyEnv": config.llm.api_key_env,
        "providers": providers,
    }
