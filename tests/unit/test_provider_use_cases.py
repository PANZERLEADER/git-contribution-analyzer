from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from git_contribution_analyzer.adapters.llm.registry import ProviderDescriptor
from git_contribution_analyzer.adapters.workspace.config import LlmConfig, ProjectConfig
from git_contribution_analyzer.application.use_cases import list_providers as list_module
from git_contribution_analyzer.application.use_cases import test_provider as test_module


def _patch_config(monkeypatch: pytest.MonkeyPatch) -> None:
    repository = SimpleNamespace(root=Path("repository"))
    config = ProjectConfig(defaultBranch="main", llm=LlmConfig(enabled=True, provider="mock"))
    monkeypatch.setattr(list_module, "discover_repository", lambda path: repository)
    monkeypatch.setattr(list_module, "load_config", lambda path: config)
    monkeypatch.setattr(test_module, "discover_repository", lambda path: repository)
    monkeypatch.setattr(test_module, "load_config", lambda path: config)


def test_list_providers_should_mark_selected_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_config(monkeypatch)
    monkeypatch.setattr(
        list_module,
        "provider_descriptors",
        lambda: (ProviderDescriptor("mock", True, False, "local"),),
    )

    result = list_module.list_providers(Path("repository"))

    assert result["selected"] == "mock"
    assert result["enabled"] is True
    assert result["providers"][0]["selected"] is True


def test_provider_health_should_not_expose_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_config(monkeypatch)
    provider = SimpleNamespace(
        provider_id="mock",
        model="deterministic",
        capabilities=SimpleNamespace(local_execution=True),
        health_check=lambda: True,
    )
    monkeypatch.setattr(test_module, "build_provider", lambda config: provider)

    result = test_module.test_provider(Path("repository"))

    assert result == {
        "provider": "mock",
        "model": "deterministic",
        "healthy": True,
        "localExecution": True,
    }
