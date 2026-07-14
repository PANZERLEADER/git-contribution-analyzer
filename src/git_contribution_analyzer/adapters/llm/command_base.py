from __future__ import annotations

import subprocess
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Protocol

from git_contribution_analyzer.adapters.llm.base import _parse_json
from git_contribution_analyzer.application.ports.llm import (
    LlmCompletion,
    LlmTask,
    ProviderCapabilities,
)
from git_contribution_analyzer.domain.errors import (
    LlmOutputError,
    LlmProviderError,
    LlmTimeoutError,
)

MAX_OUTPUT_CHARS = 2_000_000


class CommandExecutor(Protocol):
    def __call__(
        self,
        command: tuple[str, ...],
        *,
        input_text: str | None,
        cwd: Path,
        timeout_seconds: float,
    ) -> subprocess.CompletedProcess[str]: ...


def execute_command(
    command: tuple[str, ...],
    *,
    input_text: str | None,
    cwd: Path,
    timeout_seconds: float,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        input=input_text,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
        check=False,
        shell=False,
    )


class CommandLlmProvider(ABC):
    provider_id: str

    def __init__(
        self,
        *,
        executable: str,
        model: str,
        timeout_seconds: float = 120.0,
        executor: CommandExecutor = execute_command,
    ) -> None:
        self.executable = executable
        self.model = model or "configured-default"
        self.timeout_seconds = timeout_seconds
        self._executor = executor

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(structured_output=True, local_execution=True)

    def health_check(self) -> bool:
        try:
            with tempfile.TemporaryDirectory(prefix="gca-llm-health-") as directory:
                result = self._executor(
                    (self.executable, "--version"),
                    input_text=None,
                    cwd=Path(directory),
                    timeout_seconds=min(self.timeout_seconds, 10.0),
                )
            return result.returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    def complete(self, task: LlmTask) -> LlmCompletion:
        try:
            with tempfile.TemporaryDirectory(prefix="gca-llm-") as directory:
                working_directory = Path(directory)
                command = self._build_command(task, working_directory)
                result = self._executor(
                    command,
                    input_text=self._input_text(task),
                    cwd=working_directory,
                    timeout_seconds=self.timeout_seconds,
                )
                if result.returncode != 0:
                    error = LlmProviderError(
                        f"{self.provider_id} process exited with code {result.returncode}",
                        code="CLI_ERROR",
                    )
                    error.attempts = 1
                    raise error
                raw_text = self._extract_output(result, working_directory)
        except subprocess.TimeoutExpired as exc:
            error = LlmTimeoutError(f"{self.provider_id} process timed out")
            error.attempts = 1
            raise error from exc
        except (FileNotFoundError, PermissionError, OSError) as exc:
            error = LlmProviderError(
                f"{self.provider_id} executable is not available",
                code="CLI_NOT_AVAILABLE",
            )
            error.attempts = 1
            raise error from exc

        if len(raw_text) > MAX_OUTPUT_CHARS:
            error = LlmOutputError(f"{self.provider_id} output exceeds the size limit")
            error.attempts = 1
            raise error
        try:
            content = _parse_json(raw_text)
        except (TypeError, ValueError) as exc:
            error = LlmOutputError(f"{self.provider_id} returned invalid structured output")
            error.attempts = 1
            raise error from exc
        return LlmCompletion(
            provider_id=self.provider_id,
            model=self.model,
            content=content,
            attempts=1,
            input_chars=len(task.system_prompt) + len(task.user_prompt),
            output_chars=len(raw_text),
        )

    def _input_text(self, task: LlmTask) -> str:
        return task.user_prompt

    @abstractmethod
    def _build_command(self, task: LlmTask, working_directory: Path) -> tuple[str, ...]: ...

    @abstractmethod
    def _extract_output(
        self, result: subprocess.CompletedProcess[str], working_directory: Path
    ) -> str: ...

    def _model_arguments(self) -> tuple[str, ...]:
        if self.model in ("", "default", "configured-default"):
            return ()
        return ("--model", self.model)
