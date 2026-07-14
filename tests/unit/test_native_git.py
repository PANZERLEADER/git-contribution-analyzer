from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from git_contribution_analyzer.adapters.git.native_git import NativeGitHistory
from tests.helpers.git_repo_builder import GitRepoBuilder


def test_should_list_all_refs_with_one_git_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "bulk-refs"
    builder = GitRepoBuilder.create(repo)
    commit_hash = builder.commit_text("app.txt", "app\n", "feat: app")
    builder.tag("v1.0.0")
    builder.run("tag", "-a", "v2.0.0", "-m", "release v2")

    history = NativeGitHistory(repo)
    commands: list[tuple[str, ...]] = []
    original_run = history._run

    def recording_run(
        *arguments: str,
        input_bytes: bytes | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[bytes]:
        commands.append(arguments)
        return original_run(*arguments, input_bytes=input_bytes, check=check)

    monkeypatch.setattr(history, "_run", recording_run)

    refs = history.list_refs()
    refs_by_name = {git_ref.name: git_ref for git_ref in refs}

    assert refs_by_name["refs/heads/main"].commit_hash == commit_hash
    assert refs_by_name["refs/tags/v1.0.0"].commit_hash == commit_hash
    assert refs_by_name["refs/tags/v2.0.0"].commit_hash == commit_hash
    assert refs_by_name["refs/tags/v2.0.0"].ref_type == "TAG"
    assert sum(command[0] == "for-each-ref" for command in commands) == 1
    assert not any(command[0] == "rev-parse" for command in commands)


def test_should_resolve_reachability_and_release_tags_in_bulk(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "bulk-delivery"
    builder = GitRepoBuilder.create(repo)
    first = builder.commit_text("first.txt", "first\n", "feat: first")
    builder.tag("v2.0.0")
    second = builder.commit_text("second.txt", "second\n", "feat: second")
    builder.tag("v1.0.0")
    builder.checkout("feature/unmerged", create=True)
    unmerged = builder.commit_text("feature.txt", "feature\n", "feat: feature")

    history = NativeGitHistory(repo)
    commands: list[tuple[str, ...]] = []
    original_run = history._run

    def recording_run(
        *arguments: str,
        input_bytes: bytes | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[bytes]:
        commands.append(arguments)
        return original_run(*arguments, input_bytes=input_bytes, check=check)

    monkeypatch.setattr(history, "_run", recording_run)

    reachable = history.reachable_commits("refs/heads/main")
    release_tags = history.first_release_tags((first, second, unmerged))

    assert reachable == frozenset((first, second))
    assert release_tags == {
        first: "refs/tags/v1.0.0",
        second: "refs/tags/v1.0.0",
    }
    assert not any(command[:2] == ("merge-base", "--is-ancestor") for command in commands)
    assert not any(command[:2] == ("tag", "--contains") for command in commands)
    assert sum(command[0] == "rev-list" for command in commands) == 3
