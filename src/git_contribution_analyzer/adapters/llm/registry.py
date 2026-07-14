from __future__ import annotations

import os
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from git_contribution_analyzer.adapters.llm.anthropic import AnthropicProvider
from git_contribution_analyzer.adapters.llm.claude_cli import ClaudeCliProvider
from git_contribution_analyzer.adapters.llm.codex_cli import CodexCliProvider
from git_contribution_analyzer.adapters.llm.mock import MockLlmProvider
from git_contribution_analyzer.adapters.llm.ollama import OllamaProvider
from git_contribution_analyzer.adapters.llm.openai_compatible import (
    OpenAiCompatibleProvider,
)
from git_contribution_analyzer.adapters.workspace.config import LlmConfig
from git_contribution_analyzer.application.ports.llm import LlmProvider
from git_contribution_analyzer.domain.errors import ConfigurationError


@dataclass(frozen=True, slots=True)
class ProviderDescriptor:
    provider_id: str
    local_execution: bool
    requires_api_key: bool
    default_base_url: str


PROVIDERS = (
    ProviderDescriptor("mock", True, False, "local"),
    ProviderDescriptor("openai-compatible", False, True, "https://api.openai.com/v1"),
    ProviderDescriptor("anthropic", False, True, "https://api.anthropic.com"),
    ProviderDescriptor("ollama", True, False, "http://127.0.0.1:11434"),
    ProviderDescriptor("codex-cli", True, False, "local-command"),
    ProviderDescriptor("claude-cli", True, False, "local-command"),
)


def provider_descriptors() -> tuple[ProviderDescriptor, ...]:
    return PROVIDERS


def build_provider(
    config: LlmConfig,
    *,
    environ: Mapping[str, str] | None = None,
) -> LlmProvider:
    env = os.environ if environ is None else environ
    provider_id = env.get("GCA_LLM_PROVIDER", config.provider).strip().lower()
    model = env.get("GCA_LLM_MODEL", config.model).strip()
    base_url = env.get("GCA_LLM_BASE_URL", config.base_url or "").strip()
    descriptor = next(
        (candidate for candidate in PROVIDERS if candidate.provider_id == provider_id), None
    )
    if descriptor is None:
        supported = ", ".join(item.provider_id for item in PROVIDERS)
        raise ConfigurationError(
            f"Unsupported LLM provider '{provider_id}'. Supported providers: {supported}"
        )
    resolved_base_url = base_url or descriptor.default_base_url
    if provider_id == "mock":
        return MockLlmProvider()
    if provider_id == "ollama":
        return OllamaProvider(
            model=model,
            base_url=resolved_base_url,
            timeout_seconds=config.timeout_seconds,
            max_retries=config.max_retries,
        )
    if provider_id in ("codex-cli", "claude-cli"):
        executable_name = "codex" if provider_id == "codex-cli" else "claude"
        configured_executable = env.get("GCA_LLM_EXECUTABLE") or config.executable
        discovered_executable = shutil.which(executable_name) or executable_name
        executable = configured_executable or _prefer_native_command(
            provider_id, discovered_executable
        )
        command_model = "configured-default" if model == "deterministic" else model
        provider_type = CodexCliProvider if provider_id == "codex-cli" else ClaudeCliProvider
        return provider_type(
            executable=executable,
            model=command_model,
            timeout_seconds=config.command_timeout_seconds,
        )
    api_key = env.get(config.api_key_env, "")
    if not api_key:
        raise ConfigurationError(
            f"LLM provider '{provider_id}' requires environment variable "
            f"{config.api_key_env}"
        )
    if provider_id == "anthropic":
        return AnthropicProvider(
            model=model,
            base_url=resolved_base_url,
            api_key=api_key,
            timeout_seconds=config.timeout_seconds,
            max_retries=config.max_retries,
        )
    return OpenAiCompatibleProvider(
        model=model,
        base_url=resolved_base_url,
        api_key=api_key,
        timeout_seconds=config.timeout_seconds,
        max_retries=config.max_retries,
    )


def _prefer_native_command(provider_id: str, executable: str) -> str:
    path = Path(executable)
    if provider_id != "codex-cli" or path.name.casefold() != "codex.cmd":
        return executable
    pattern = (
        "node_modules/@openai/codex/node_modules/@openai/"
        "codex-win32-*/vendor/*/bin/codex.exe"
    )
    candidates = sorted(path.parent.glob(pattern))
    return str(candidates[0]) if candidates else executable
