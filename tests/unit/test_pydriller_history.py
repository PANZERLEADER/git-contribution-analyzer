from __future__ import annotations

import os
import subprocess
from pathlib import Path

from git_contribution_analyzer.adapters.git.pydriller_history import PyDrillerChangeReader


def _git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def test_should_treat_missing_gitlink_object_as_binary_change(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    _git(repository, "init")
    _git(repository, "config", "user.name", "Calibration Test")
    _git(repository, "config", "user.email", "calibration@example.com")
    (repository / "README.md").write_text("fixture\n", encoding="utf-8")
    _git(repository, "add", "README.md")
    _git(repository, "commit", "-m", "initial")

    missing_gitlink = "0563417be973397d05b45cd2c5b415d7215161e3"
    environment = os.environ.copy()
    environment["GIT_INDEX_FILE"] = str(repository / ".git" / "index")
    subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "update-index",
            "--add",
            "--cacheinfo",
            f"160000,{missing_gitlink},vendor/public-submodule",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
    )
    _git(repository, "commit", "-m", "add public submodule")
    commit_hash = _git(repository, "rev-parse", "HEAD")

    changes = PyDrillerChangeReader(repository).read_changes((commit_hash,))

    assert len(changes[commit_hash]) == 1
    assert changes[commit_hash][0].new_path == "vendor/public-submodule"
    assert changes[commit_hash][0].is_binary is True
