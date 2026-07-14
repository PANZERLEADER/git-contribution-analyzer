from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from git_contribution_analyzer.cli.app import app
from tests.helpers.git_repo_builder import GitRepoBuilder

runner = CliRunner()


def _repository(tmp_path: Path) -> Path:
    repo = tmp_path / "team-selection"
    builder = GitRepoBuilder.create(repo)
    builder.commit_text(
        "src/alice.py",
        "ALICE = True\n",
        "feat: add alice feature",
        name="Alice",
        email="alice@example.com",
    )
    builder.commit_text(
        "src/bob.py",
        "BOB = True\n",
        "feat: add bob feature",
        name="Bob",
        email="bob@example.com",
    )
    assert runner.invoke(app, ["init", str(repo)]).exit_code == 0
    _map(repo, "Alice", "alice@example.com")
    _map(repo, "Bob", "bob@example.com")
    return repo


def _map(repo: Path, name: str, email: str) -> None:
    result = runner.invoke(
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
    assert result.exit_code == 0, result.stdout


def _assess(repo: Path, selectors: list[str]) -> dict[str, object]:
    args = ["assess", str(repo)]
    for selector in selectors:
        args.extend(["--person", selector])
    args.extend(["--no-llm", "--json"])
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.stdout
    return json.loads(result.stdout)["data"]


def test_should_select_multiple_people_independent_of_selector_order(
    tmp_path: Path,
) -> None:
    repo = _repository(tmp_path)

    first = _assess(repo, ["alice@example.com", "bob@example.com"])
    second = _assess(repo, ["bob@example.com", "alice@example.com"])

    assert first["scopeType"] == "PROJECT"
    assert len(first["subjects"]) == 2
    assert first["snapshot"]["id"] == second["snapshot"]["id"]
    assert first["selection"]["mode"] == "EXPLICIT"
    assert first["selection"]["requestedSelectors"] == [
        "alice@example.com",
        "bob@example.com",
    ]
    assert first["selection"]["includedPersonIds"] == sorted(
        subject["person"]["id"] for subject in first["subjects"]
    )


def test_should_reject_selectors_that_resolve_to_the_same_person(tmp_path: Path) -> None:
    repo = _repository(tmp_path)

    result = runner.invoke(
        app,
        [
            "assess",
            str(repo),
            "--person",
            "Alice",
            "--person",
            "alice@example.com",
            "--no-llm",
            "--json",
        ],
    )

    assert result.exit_code == 5
    assert "same person" in result.stdout.casefold()


def test_should_exclude_selected_people_from_all_scope(tmp_path: Path) -> None:
    repo = _repository(tmp_path)

    result = runner.invoke(
        app,
        [
            "assess",
            str(repo),
            "--all",
            "--exclude-person",
            "bob@example.com",
            "--no-llm",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.stdout
    report = json.loads(result.stdout)["data"]
    assert [subject["person"]["name"] for subject in report["subjects"]] == ["Alice"]
    assert report["selection"]["exclusions"][0]["selector"] == "bob@example.com"
    assert report["selection"]["exclusions"][0]["reason"] == "EXPLICITLY_EXCLUDED"


def test_should_reject_exclusion_without_all_scope(tmp_path: Path) -> None:
    repo = _repository(tmp_path)

    result = runner.invoke(
        app,
        [
            "assess",
            str(repo),
            "--person",
            "alice@example.com",
            "--exclude-person",
            "bob@example.com",
            "--no-llm",
        ],
    )

    assert result.exit_code == 2
    assert "--exclude-person" in result.stderr


def test_should_fail_before_creating_run_when_selection_is_empty(tmp_path: Path) -> None:
    repo = _repository(tmp_path)

    result = runner.invoke(
        app,
        [
            "assess",
            str(repo),
            "--all",
            "--exclude-person",
            "alice@example.com",
            "--exclude-person",
            "bob@example.com",
            "--no-llm",
            "--json",
        ],
    )
    runs = runner.invoke(app, ["runs", "list", str(repo), "--json"])

    assert result.exit_code == 5
    assert "no people" in result.stdout.casefold()
    assert json.loads(runs.stdout)["data"]["runs"] == []
