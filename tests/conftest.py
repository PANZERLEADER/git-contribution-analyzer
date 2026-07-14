from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repository = tmp_path / "sample-repository"
    repository.mkdir()
    subprocess.run(
        ["git", "init", "-b", "main", str(repository)],
        check=True,
        capture_output=True,
        text=True,
    )
    return repository
