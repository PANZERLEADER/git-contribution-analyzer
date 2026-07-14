from __future__ import annotations

import io
import json
import sys

import pytest

from git_contribution_analyzer.application.dto.results import CommandEnvelope
from git_contribution_analyzer.cli.output import emit_human, emit_json


def _cp1252_stdout(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[io.BytesIO, io.TextIOWrapper]:
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="cp1252", errors="strict")
    monkeypatch.setattr(sys, "stdout", stream)
    return buffer, stream


def test_should_escape_unicode_human_output_when_stdout_cannot_encode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    buffer, stream = _cp1252_stdout(monkeypatch)

    emit_human("Initialized: C:\\验证 repository")
    stream.flush()

    output = buffer.getvalue().decode("cp1252")
    assert "Initialized:" in output
    assert r"\u9a8c\u8bc1" in output


def test_should_keep_json_valid_when_stdout_cannot_encode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    buffer, stream = _cp1252_stdout(monkeypatch)

    emit_json(CommandEnvelope(command="status", data={"repository": "C:\\验证"}))
    stream.flush()

    payload = json.loads(buffer.getvalue().decode("cp1252"))
    assert payload["data"]["repository"] == "C:\\验证"
