from __future__ import annotations

import sys

import typer

from git_contribution_analyzer.application.dto.results import CommandEnvelope


def emit_json(envelope: CommandEnvelope) -> None:
    typer.echo(_console_safe(envelope.model_dump_json(by_alias=True, exclude_none=False)))


def emit_human(message: str) -> None:
    typer.echo(_console_safe(message))


def _console_safe(message: str) -> str:
    encoding = getattr(sys.stdout, "encoding", None)
    if not encoding:
        return message
    try:
        message.encode(encoding)
    except (LookupError, UnicodeEncodeError):
        return message.encode(encoding, errors="backslashreplace").decode(encoding)
    return message
