from __future__ import annotations

from pathlib import Path

import pytest

from git_contribution_analyzer.adapters.llm.registry import (
    build_provider,
    provider_descriptors,
)
from git_contribution_analyzer.adapters.workspace.config import LlmConfig
from git_contribution_analyzer.domain.errors import ConfigurationError


def test_should_list_all_builtin_providers() -> None:
    assert {item.provider_id for item in provider_descriptors()} == {
        "mock",
        "openai-compatible",
        "anthropic",
        "ollama",
        "codex-cli",
        "claude-cli",
    }


def test_should_build_provider_using_environment_precedence() -> None:
    config = LlmConfig(
        provider="mock",
        model="configured-model",
        baseUrl="https://configured.invalid",
        apiKeyEnv="CUSTOM_LLM_KEY",
    )

    provider = build_provider(
        config,
        environ={
            "GCA_LLM_PROVIDER": "openai-compatible",
            "GCA_LLM_MODEL": "environment-model",
            "GCA_LLM_BASE_URL": "https://environment.test/v1",
            "CUSTOM_LLM_KEY": "secret-value",
        },
    )

    assert provider.provider_id == "openai-compatible"
    assert provider.model == "environment-model"
    assert provider.base_url == "https://environment.test/v1"


def test_should_report_missing_key_by_environment_variable_name_only() -> None:
    config = LlmConfig(provider="anthropic", model="test", apiKeyEnv="ANTHROPIC_API_KEY")

    with pytest.raises(ConfigurationError, match="ANTHROPIC_API_KEY") as raised:
        build_provider(config, environ={})

    assert "secret-value" not in str(raised.value)


@pytest.mark.parametrize(
    ("provider_id", "executable"),
    [("codex-cli", "custom-codex.cmd"), ("claude-cli", "custom-claude.exe")],
)
def test_should_build_command_provider_with_environment_executable(
    provider_id: str, executable: str
) -> None:
    provider = build_provider(
        LlmConfig(provider=provider_id, model="configured-model"),
        environ={"GCA_LLM_EXECUTABLE": executable},
    )

    assert provider.provider_id == provider_id
    assert provider.model == "configured-model"
    assert provider.executable == executable  # type: ignore[attr-defined]
    assert provider.timeout_seconds == 300.0  # type: ignore[attr-defined]


def test_should_prefer_native_codex_binary_over_discovered_npm_wrapper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wrapper = tmp_path / "npm" / "codex.CMD"
    native = (
        wrapper.parent
        / "node_modules"
        / "@openai"
        / "codex"
        / "node_modules"
        / "@openai"
        / "codex-win32-x64"
        / "vendor"
        / "x86_64-pc-windows-msvc"
        / "bin"
        / "codex.exe"
    )
    native.parent.mkdir(parents=True)
    wrapper.write_text("@ECHO off", encoding="utf-8")
    native.write_bytes(b"binary")
    monkeypatch.setattr(
        "git_contribution_analyzer.adapters.llm.registry.shutil.which",
        lambda _name: str(wrapper),
    )

    provider = build_provider(
        LlmConfig(provider="codex-cli", model="configured-default"), environ={}
    )

    assert provider.executable == str(native)  # type: ignore[attr-defined]
