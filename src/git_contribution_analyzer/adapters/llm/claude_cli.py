from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from git_contribution_analyzer.adapters.llm.command_base import CommandLlmProvider
from git_contribution_analyzer.application.ports.llm import LlmTask


class ClaudeCliProvider(CommandLlmProvider):
    provider_id = "claude-cli"

    def _build_command(self, task: LlmTask, _working_directory: Path) -> tuple[str, ...]:
        return (
            self.executable,
            "--print",
            "--output-format",
            "json",
            "--json-schema",
            json.dumps(task.output_schema, ensure_ascii=False, sort_keys=True),
            "--no-session-persistence",
            "--permission-mode",
            "dontAsk",
            "--tools",
            "",
            "--disable-slash-commands",
            "--strict-mcp-config",
            "--no-chrome",
            "--system-prompt",
            task.system_prompt,
            *self._model_arguments(),
        )

    def _extract_output(
        self, result: subprocess.CompletedProcess[str], _working_directory: Path
    ) -> str:
        try:
            payload: Any = json.loads(result.stdout)
        except (TypeError, ValueError):
            return result.stdout
        if isinstance(payload, dict):
            structured = payload.get("structured_output") or payload.get("structuredOutput")
            if isinstance(structured, dict):
                return json.dumps(structured, ensure_ascii=False)
            value = payload.get("result")
            if isinstance(value, dict):
                return json.dumps(value, ensure_ascii=False)
            if isinstance(value, str):
                return value
        return result.stdout
