from __future__ import annotations

import json
from pathlib import Path

import pytest
from alembic import command
from typer.testing import CliRunner

from git_contribution_analyzer.adapters.storage.sqlite.database import _alembic_config
from git_contribution_analyzer.cli.app import app
from tests.helpers.git_repo_builder import GitRepoBuilder

runner = CliRunner()


def _repository(tmp_path: Path) -> Path:
    repo = tmp_path / "identity-merge"
    builder = GitRepoBuilder.create(repo)
    builder.commit_text(
        "src/alice.py",
        "ALICE = True\n",
        "feat: alice",
        name="Alice",
        email="alice@example.com",
    )
    builder.commit_text(
        "src/bob.py",
        "BOB = True\n",
        "feat: bob",
        name="Bob",
        email="bob@example.com",
    )
    assert runner.invoke(app, ["init", str(repo)]).exit_code == 0
    for name, email in (
        ("Alice", "alice@example.com"),
        ("Bob", "bob@example.com"),
    ):
        mapped = runner.invoke(
            app,
            [
                "identities",
                "map",
                str(repo),
                "--name",
                name,
                "--email",
                email,
                "--person-name",
                name,
                "--person-email",
                email,
            ],
        )
        assert mapped.exit_code == 0, mapped.stdout
    return repo


def _json(*args: str) -> dict[str, object]:
    result = runner.invoke(app, [*args, "--json"])
    assert result.exit_code == 0, result.stdout
    return json.loads(result.stdout)["data"]


def test_should_merge_and_unmerge_identities_without_rewriting_history(
    tmp_path: Path,
) -> None:
    repo = _repository(tmp_path)
    historical = _json(
        "assess",
        str(repo),
        "--person",
        "alice@example.com",
        "--no-llm",
    )
    historical_run = historical["run"]["id"]

    preview = _json(
        "identities",
        "merge",
        str(repo),
        "--source",
        "alice@example.com",
        "--target",
        "bob@example.com",
        "--dry-run",
    )
    identities_before = _json("identities", "list", str(repo))

    assert preview["safeToExecute"] is True
    assert all(person["active"] for person in identities_before["persons"])

    merged = _json(
        "identities",
        "merge",
        str(repo),
        "--source",
        "alice@example.com",
        "--target",
        "bob@example.com",
        "--yes",
    )
    identities_after = _json("identities", "list", str(repo))
    source = next(
        person for person in identities_after["persons"] if person["name"] == "Alice"
    )
    target = next(
        person for person in identities_after["persons"] if person["name"] == "Bob"
    )
    combined = _json(
        "assess",
        str(repo),
        "--person",
        "bob@example.com",
        "--no-llm",
    )
    replay = runner.invoke(
        app,
        [
            "report",
            str(repo),
            "--run",
            str(historical_run),
            "--format",
            "json",
        ],
    )
    assert replay.exit_code == 0, replay.stdout
    replayed = json.loads(replay.stdout)

    assert source["active"] is False
    assert source["mergedIntoPersonId"] == target["id"]
    assert len(target["aliases"]) == 2
    assert len(
        {
            commit_hash
            for evidence in combined["evidence"]
            for commit_hash in evidence["commitHashes"]
        }
    ) == 2
    assert replayed == historical

    reverted = _json(
        "identities",
        "unmerge",
        str(repo),
        "--merge-id",
        str(merged["mergeId"]),
        "--yes",
    )
    restored = _json("identities", "list", str(repo))
    events = _json("identities", "merges", str(repo))

    assert reverted["status"] == "REVERTED"
    assert all(person["active"] for person in restored["persons"])
    assert events["merges"][0]["status"] == "REVERTED"


def test_should_block_downgrade_while_merge_is_active(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    _json(
        "identities",
        "merge",
        str(repo),
        "--source",
        "alice@example.com",
        "--target",
        "bob@example.com",
        "--yes",
    )

    with pytest.raises(RuntimeError, match="ACTIVE"):
        command.downgrade(
            _alembic_config(repo / ".gca" / "index.sqlite"), "0005_run_types"
        )
