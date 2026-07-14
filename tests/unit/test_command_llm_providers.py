from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from git_contribution_analyzer.adapters.llm.claude_cli import ClaudeCliProvider
from git_contribution_analyzer.adapters.llm.codex_cli import CodexCliProvider
from git_contribution_analyzer.application.ports.llm import LlmTask
from git_contribution_analyzer.domain.errors import (
    LlmOutputError,
    LlmProviderError,
    LlmTimeoutError,
)

VALID_OUTPUT = {
    "overallSummary": [
        {
            "text": "Delivered an evidence-backed change.",
            "evidenceIds": ["EV-001"],
            "confidence": "HIGH",
        }
    ],
    "contributionSummaries": [],
    "capabilityExplanations": [],
    "resumeBullets": [],
}


def _task() -> LlmTask:
    return LlmTask(
        task_id="semantic-report",
        prompt_version="semantic-v1",
        schema_version="semantic-v1",
        system_prompt="Return JSON only.",
        user_prompt="private prompt context for EV-001",
        output_schema={"type": "object"},
        allowed_evidence_ids=("EV-001",),
    )


class FakeExecutor:
    def __init__(
        self,
        *,
        stdout: str = "",
        returncode: int = 0,
        codex_output: dict[str, Any] | None = None,
        timeout: bool = False,
    ) -> None:
        self.stdout = stdout
        self.returncode = returncode
        self.codex_output = codex_output
        self.timeout = timeout
        self.calls: list[dict[str, Any]] = []

    def __call__(
        self,
        command: tuple[str, ...],
        *,
        input_text: str | None,
        cwd: Path,
        timeout_seconds: float,
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(
            {
                "command": command,
                "input_text": input_text,
                "cwd": cwd,
                "timeout_seconds": timeout_seconds,
            }
        )
        if self.timeout:
            raise subprocess.TimeoutExpired(command, timeout_seconds)
        if self.codex_output is not None and "--output-last-message" in command:
            output_index = command.index("--output-last-message") + 1
            Path(command[output_index]).write_text(
                json.dumps(self.codex_output), encoding="utf-8"
            )
        return subprocess.CompletedProcess(
            command,
            self.returncode,
            stdout=self.stdout,
            stderr="provider stderr must not enter the audit log",
        )


def test_should_run_codex_ephemerally_in_isolated_read_only_directory() -> None:
    executor = FakeExecutor(codex_output=VALID_OUTPUT)
    provider = CodexCliProvider(
        executable="codex.cmd",
        model="gpt-test",
        executor=executor,
    )

    completion = provider.complete(_task())

    call = executor.calls[0]
    command = call["command"]
    assert completion.content == VALID_OUTPUT
    assert command[:2] == ("codex.cmd", "exec")
    assert "--ephemeral" in command
    assert "mcp_servers={}" in command
    assert (
        command[command.index("--sandbox")],
        command[command.index("--sandbox") + 1],
    ) == ("--sandbox", "read-only")
    assert "--output-schema" in command
    assert "--output-last-message" in command
    assert "private prompt context" not in " ".join(command)
    assert "private prompt context" in call["input_text"]
    assert call["cwd"] != Path.cwd()


def test_should_run_claude_without_tools_or_session_persistence() -> None:
    executor = FakeExecutor(
        stdout=json.dumps({"type": "result", "structured_output": VALID_OUTPUT})
    )
    provider = ClaudeCliProvider(
        executable="claude.exe",
        model="sonnet",
        executor=executor,
    )

    completion = provider.complete(_task())

    call = executor.calls[0]
    command = call["command"]
    assert completion.content == VALID_OUTPUT
    assert command[0] == "claude.exe"
    assert "--print" in command
    assert (
        command[command.index("--output-format")],
        command[command.index("--output-format") + 1],
    ) == ("--output-format", "json")
    assert "--json-schema" in command
    assert "--no-session-persistence" in command
    assert (
        command[command.index("--tools")],
        command[command.index("--tools") + 1],
    ) == ("--tools", "")
    assert "private prompt context" not in " ".join(command)
    assert call["input_text"] == _task().user_prompt
    assert call["cwd"] != Path.cwd()


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "result", "result": VALID_OUTPUT},
        {"type": "result", "result": json.dumps(VALID_OUTPUT)},
        VALID_OUTPUT,
    ],
    ids=("result-object", "result-string", "direct-object"),
)
def test_should_parse_supported_claude_json_wrappers(payload: dict[str, Any]) -> None:
    provider = ClaudeCliProvider(
        executable="claude.exe",
        model="sonnet",
        executor=FakeExecutor(stdout=json.dumps(payload)),
    )

    assert provider.complete(_task()).content == VALID_OUTPUT


@pytest.mark.parametrize(
    "provider",
    [
        CodexCliProvider(executable="codex.cmd", model="gpt-test"),
        ClaudeCliProvider(executable="claude.exe", model="sonnet"),
    ],
    ids=("codex", "claude"),
)
def test_should_report_cli_health_from_version_command(provider: object) -> None:
    executor = FakeExecutor(stdout="provider version")
    provider._executor = executor  # type: ignore[attr-defined]

    assert provider.health_check() is True  # type: ignore[attr-defined]
    assert executor.calls[0]["command"][-1] == "--version"


@pytest.mark.parametrize("error_kind", ["timeout", "exit", "invalid-output"])
def test_should_map_command_failures_without_exposing_stderr(error_kind: str) -> None:
    executor = FakeExecutor(
        stdout="not-json",
        returncode=7 if error_kind == "exit" else 0,
        timeout=error_kind == "timeout",
    )
    provider = ClaudeCliProvider(
        executable="claude.exe",
        model="sonnet",
        executor=executor,
    )
    expected = {
        "timeout": LlmTimeoutError,
        "exit": LlmProviderError,
        "invalid-output": LlmOutputError,
    }[error_kind]

    with pytest.raises(expected) as raised:
        provider.complete(_task())

    assert "provider stderr" not in str(raised.value)


def test_should_map_missing_codex_last_message_to_output_error() -> None:
    provider = CodexCliProvider(
        executable="codex.exe",
        model="configured-default",
        executor=FakeExecutor(),
    )

    with pytest.raises(LlmOutputError):
        provider.complete(_task())
