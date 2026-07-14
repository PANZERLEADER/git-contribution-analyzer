from __future__ import annotations

import json
import subprocess
from pathlib import Path

from git_contribution_analyzer.adapters.llm.command_base import CommandLlmProvider
from git_contribution_analyzer.application.ports.llm import LlmTask


class CodexCliProvider(CommandLlmProvider):
    provider_id = "codex-cli"

    def _input_text(self, task: LlmTask) -> str:
        return f"{task.system_prompt}\n\nInput context:\n{task.user_prompt}"

    def _build_command(self, task: LlmTask, working_directory: Path) -> tuple[str, ...]:
        schema_path = working_directory / "output-schema.json"
        schema_path.write_text(
            json.dumps(task.output_schema, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        output_path = working_directory / "last-message.json"
        return (
            self.executable,
            "exec",
            "--ephemeral",
            "--skip-git-repo-check",
            "--ignore-rules",
            "--config",
            "mcp_servers={}",
            "--sandbox",
            "read-only",
            "--color",
            "never",
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(output_path),
            "-C",
            str(working_directory),
            *self._model_arguments(),
            "-",
        )

    def _extract_output(
        self, _result: subprocess.CompletedProcess[str], working_directory: Path
    ) -> str:
        try:
            return (working_directory / "last-message.json").read_text(encoding="utf-8")
        except OSError:
            return ""
