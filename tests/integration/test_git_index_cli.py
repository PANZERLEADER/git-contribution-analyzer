from __future__ import annotations

import json
from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import create_engine, text
from typer.testing import CliRunner

from git_contribution_analyzer.adapters.git.native_git import NativeGitHistory
from git_contribution_analyzer.adapters.storage.sqlite.database import _alembic_config
from git_contribution_analyzer.adapters.storage.sqlite.git_index import SqliteGitIndexStore
from git_contribution_analyzer.cli.app import app
from git_contribution_analyzer.domain.errors import WorkspaceError
from tests.helpers.git_repo_builder import GitRepoBuilder

runner = CliRunner()


def _database(repo: Path):  # type: ignore[no-untyped-def]
    return create_engine(f"sqlite:///{(repo / '.gca' / 'index.sqlite').as_posix()}")


def test_should_build_initial_index_during_init(tmp_path: Path) -> None:
    repo = tmp_path / "init-index"
    builder = GitRepoBuilder.create(repo)
    builder.commit_text("app.txt", "value\n", "feat: initial index")

    init_result = runner.invoke(app, ["init", str(repo)])
    status = runner.invoke(app, ["status", str(repo), "--json"])

    assert init_result.exit_code == 0
    assert json.loads(status.stdout)["data"]["indexedCommits"] == 1


def test_should_index_refs_commits_files_identities_and_delivery(tmp_path: Path) -> None:
    repo = tmp_path / "history"
    builder = GitRepoBuilder.create(repo)
    first = builder.commit_text(
        "src/app.py",
        "print('one')\n",
        "feat(core): add app",
        name="Alice",
        email="alice@example.com",
    )
    second = builder.commit_text(
        "src/app.py",
        "print('two')\n",
        "fix(core): update app",
        name="Alice Dev",
        email="alice@example.com",
    )
    builder.tag("v1.0.0")
    builder.checkout("feature/unmerged", create=True)
    unmerged = builder.commit_text(
        "src/feature.py",
        "FEATURE = True\n",
        "feat(feature): experimental work",
        name="Bob",
        email="bob@example.com",
    )

    assert runner.invoke(app, ["init", str(repo)]).exit_code == 0
    index_result = runner.invoke(app, ["index", str(repo), "--json"])

    assert index_result.exit_code == 0
    index_payload = json.loads(index_result.stdout)
    assert index_payload["data"]["indexedCommits"] == 3
    assert index_payload["data"]["newCommits"] == 3

    status = runner.invoke(app, ["status", str(repo), "--json"])
    status_payload = json.loads(status.stdout)
    assert status_payload["schemaVersion"] == "2.0"
    assert status_payload["data"]["indexedCommits"] == 3
    assert status_payload["data"]["identities"] == 2
    assert status_payload["data"]["unresolvedIdentities"] == 2
    assert status_payload["data"]["indexStatus"] == "up-to-date"

    identities = runner.invoke(app, ["identities", "list", str(repo), "--json"])
    identity_payload = json.loads(identities.stdout)
    assert identities.exit_code == 0
    assert len(identity_payload["data"]["persons"]) == 2
    alice = next(
        person
        for person in identity_payload["data"]["persons"]
        if person["email"] == "alice@example.com"
    )
    assert {alias["name"] for alias in alice["aliases"]} == {"Alice", "Alice Dev"}

    engine = _database(repo)
    with engine.connect() as connection:
        delivery = dict(
            connection.execute(
                text(
                    "SELECT commit_hash, status FROM commit_delivery "
                    "WHERE target_ref = 'refs/heads/main'"
                )
            ).all()
        )
        file_count = connection.execute(text("SELECT COUNT(*) FROM file_changes")).scalar_one()
    engine.dispose()

    assert delivery[first] == "RELEASED"
    assert delivery[second] == "RELEASED"
    assert delivery[unmerged] == "AUTHORED_ONLY"
    assert file_count == 3


def test_should_sync_only_new_commits_and_preserve_existing_history(tmp_path: Path) -> None:
    repo = tmp_path / "sync"
    builder = GitRepoBuilder.create(repo)
    builder.commit_text("README.md", "one\n", "docs: first")

    assert runner.invoke(app, ["init", str(repo)]).exit_code == 0
    assert runner.invoke(app, ["index", str(repo)]).exit_code == 0

    builder.commit_text("README.md", "two\n", "docs: second")
    sync_result = runner.invoke(app, ["sync", str(repo), "--json"])

    assert sync_result.exit_code == 0
    payload = json.loads(sync_result.stdout)
    assert payload["data"]["newCommits"] == 1
    assert payload["data"]["indexedCommits"] == 2

    second_sync = runner.invoke(app, ["sync", str(repo), "--json"])
    assert json.loads(second_sync.stdout)["data"]["newCommits"] == 0


def test_index_should_migrate_an_existing_workspace(tmp_path: Path) -> None:
    repo = tmp_path / "migrated-index"
    builder = GitRepoBuilder.create(repo)
    builder.commit_text("README.md", "one\n", "docs: first")
    assert runner.invoke(app, ["init", str(repo)]).exit_code == 0
    database = repo / ".gca" / "index.sqlite"
    command.downgrade(_alembic_config(database), "0006_identity_merges")

    result = runner.invoke(app, ["index", str(repo), "--json"])
    status = runner.invoke(app, ["status", str(repo), "--json"])

    assert result.exit_code == 0
    assert json.loads(status.stdout)["data"]["toolVersion"] == "0.5.1"
    engine = _database(repo)
    with engine.connect() as connection:
        revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
        structural_facts = connection.execute(
            text("SELECT COUNT(*) FROM structural_commit_facts")
        ).scalar_one()
    engine.dispose()
    assert revision == "0007_structural_baselines"
    assert structural_facts == 1


def test_should_update_registered_default_branch_during_sync(tmp_path: Path) -> None:
    repo = tmp_path / "default-branch-sync"
    builder = GitRepoBuilder.create(repo)
    builder.commit_text("README.md", "main\n", "docs: main")
    assert runner.invoke(app, ["init", str(repo)]).exit_code == 0

    builder.checkout("dev", create=True)
    dev_commit = builder.commit_text("dev.txt", "dev\n", "feat: dev")
    config = repo / ".gca" / "config.yml"
    config.write_text(
        config.read_text(encoding="utf-8").replace("defaultBranch: main", "defaultBranch: dev"),
        encoding="utf-8",
    )

    sync_result = runner.invoke(app, ["sync", str(repo), "--json"])

    assert sync_result.exit_code == 0
    engine = _database(repo)
    with engine.connect() as connection:
        default_branch = connection.execute(
            text("SELECT default_branch FROM repositories")
        ).scalar_one()
        delivery = connection.execute(
            text(
                "SELECT status FROM commit_delivery "
                "WHERE commit_hash = :hash AND target_ref = 'refs/heads/dev'"
            ),
            {"hash": dev_commit},
        ).scalar_one()
    engine.dispose()

    assert default_branch == "dev"
    assert delivery == "LANDED"


def test_should_detect_rename_binary_duplicate_patch_and_revert(tmp_path: Path) -> None:
    repo = tmp_path / "relationships"
    builder = GitRepoBuilder.create(repo)
    builder.commit_text("src/name.txt", "base\n", "feat: add base")
    rename_commit = builder.rename("src/name.txt", "src/renamed.txt", "refactor: rename file")
    binary_commit = builder.commit_binary("assets/blob.bin", b"\x00\x01\x02", "feat: add binary")

    builder.checkout("feature/change", create=True)
    feature_commit = builder.commit_text("src/change.txt", "change\n", "feat: shared patch")
    builder.checkout("main")
    cherry_pick = builder.cherry_pick(feature_commit)
    revert_commit = builder.revert(cherry_pick)

    assert runner.invoke(app, ["init", str(repo)]).exit_code == 0
    assert runner.invoke(app, ["index", str(repo)]).exit_code == 0

    engine = _database(repo)
    with engine.connect() as connection:
        rename = connection.execute(
            text(
                "SELECT change_type, old_path, new_path FROM file_changes "
                "WHERE commit_hash = :hash"
            ),
            {"hash": rename_commit},
        ).one()
        binary = connection.execute(
            text("SELECT is_binary FROM file_changes WHERE commit_hash = :hash"),
            {"hash": binary_commit},
        ).scalar_one()
        relations = connection.execute(
            text(
                "SELECT commit_hash, status, related_commit_hash FROM commit_delivery "
                "WHERE commit_hash IN (:feature, :cherry, :revert) "
                "AND target_ref = 'refs/heads/main'"
            ),
            {"feature": feature_commit, "cherry": cherry_pick, "revert": revert_commit},
        ).all()
    engine.dispose()

    assert tuple(rename) == ("RENAME", "src/name.txt", "src/renamed.txt")
    assert binary == 1
    relation_map = {row.commit_hash: (row.status, row.related_commit_hash) for row in relations}
    assert relation_map[feature_commit][0] == "AUTHORED_ONLY"
    assert relation_map[cherry_pick] == ("REVERTED", revert_commit)
    assert relation_map[revert_commit][0] == "LANDED"


def test_should_map_identity_manually(tmp_path: Path) -> None:
    repo = tmp_path / "identity-map"
    builder = GitRepoBuilder.create(repo)
    builder.commit_text(
        "app.txt",
        "value\n",
        "feat: identity",
        name="Alias Name",
        email="alias@example.com",
    )
    runner.invoke(app, ["init", str(repo)])
    runner.invoke(app, ["index", str(repo)])

    mapped = runner.invoke(
        app,
        [
            "identities",
            "map",
            str(repo),
            "--name",
            "Alias Name",
            "--email",
            "alias@example.com",
            "--person-name",
            "Canonical Name",
            "--person-email",
            "canonical@example.com",
            "--json",
        ],
    )

    assert mapped.exit_code == 0
    payload = json.loads(mapped.stdout)
    assert payload["data"]["person"]["name"] == "Canonical Name"
    assert payload["data"]["person"]["confirmed"] is True


def test_should_coalesce_author_email_case_variants(tmp_path: Path) -> None:
    repo = tmp_path / "email-case"
    builder = GitRepoBuilder.create(repo)
    builder.commit_text(
        "one.txt",
        "one\n",
        "feat: uppercase email",
        name="Case Author",
        email="Author@Example.com",
    )
    builder.commit_text(
        "two.txt",
        "two\n",
        "feat: lowercase email",
        name="Case Author",
        email="author@example.com",
    )

    init_result = runner.invoke(app, ["init", str(repo)])
    identities = runner.invoke(app, ["identities", "list", str(repo), "--json"])

    assert init_result.exit_code == 0
    assert identities.exit_code == 0
    payload = json.loads(identities.stdout)
    assert len(payload["data"]["persons"]) == 1
    assert len(payload["data"]["persons"][0]["aliases"]) == 1

    status = runner.invoke(app, ["status", str(repo), "--json"])
    assert json.loads(status.stdout)["data"]["indexedCommits"] == 2


def test_should_index_merge_parents_and_update_ref_after_force_push(tmp_path: Path) -> None:
    repo = tmp_path / "merge-force"
    builder = GitRepoBuilder.create(repo)
    base = builder.commit_text("base.txt", "base\n", "feat: base")
    builder.checkout("feature", create=True)
    builder.commit_text("feature.txt", "feature\n", "feat: feature")
    builder.checkout("main")
    builder.commit_text("main.txt", "main\n", "feat: main")
    merge_commit = builder.merge("feature", "merge feature")

    runner.invoke(app, ["init", str(repo)])
    runner.invoke(app, ["index", str(repo)])

    engine = _database(repo)
    with engine.connect() as connection:
        is_merge = connection.execute(
            text("SELECT is_merge FROM commits WHERE hash = :hash"),
            {"hash": merge_commit},
        ).scalar_one()
        parent_count = connection.execute(
            text("SELECT COUNT(*) FROM commit_parents WHERE commit_hash = :hash"),
            {"hash": merge_commit},
        ).scalar_one()
    assert is_merge == 1
    assert parent_count == 2

    builder.reset_hard(base)
    replacement = builder.commit_text("replacement.txt", "replacement\n", "fix: replacement")
    sync = runner.invoke(app, ["sync", str(repo), "--json"])
    assert sync.exit_code == 0

    with engine.connect() as connection:
        main_ref = connection.execute(
            text("SELECT commit_hash FROM refs WHERE ref_name = 'refs/heads/main'")
        ).scalar_one()
        old_delivery = connection.execute(
            text(
                "SELECT status FROM commit_delivery "
                "WHERE commit_hash = :hash AND target_ref = 'refs/heads/main'"
            ),
            {"hash": merge_commit},
        ).scalar_one()
        preserved = connection.execute(
            text("SELECT COUNT(*) FROM commits WHERE hash = :hash"),
            {"hash": merge_commit},
        ).scalar_one()
    engine.dispose()

    assert main_ref == replacement
    assert old_delivery == "AUTHORED_ONLY"
    assert preserved == 1


def test_should_apply_mailmap_as_confirmed_identity(tmp_path: Path) -> None:
    repo = tmp_path / "mailmap"
    builder = GitRepoBuilder.create(repo)
    builder.commit_text(
        "app.txt",
        "value\n",
        "feat: old identity",
        name="Old Name",
        email="old@example.com",
    )
    builder.commit_text(
        ".mailmap",
        "Canonical Name <canonical@example.com> Old Name <old@example.com>\n",
        "chore: add mailmap",
    )

    runner.invoke(app, ["init", str(repo)])
    runner.invoke(app, ["index", str(repo)])
    identities = runner.invoke(app, ["identities", "list", str(repo), "--json"])
    persons = json.loads(identities.stdout)["data"]["persons"]

    canonical = next(person for person in persons if person["email"] == "canonical@example.com")
    assert canonical["name"] == "Canonical Name"
    assert canonical["confirmed"] is True
    assert canonical["aliases"][0]["source"] == "MAILMAP"


def test_should_rollback_entire_index_batch_when_commit_write_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "rollback"
    builder = GitRepoBuilder.create(repo)
    builder.commit_text("one.txt", "one\n", "feat: one")
    builder.commit_text("two.txt", "two\n", "feat: two")
    runner.invoke(app, ["init", str(repo)])

    history = NativeGitHistory(repo)
    commits = history.read_commits(history.list_commit_hashes())
    store = SqliteGitIndexStore(repo / ".gca" / "index.sqlite", str(repo.resolve()))
    engine = _database(repo)
    with engine.connect() as connection:
        baseline = (
            connection.execute(text("SELECT COUNT(*) FROM commits")).scalar_one(),
            connection.execute(text("SELECT COUNT(*) FROM refs")).scalar_one(),
            connection.execute(text("SELECT COUNT(*) FROM persons")).scalar_one(),
        )
    original = store._insert_commit
    calls = 0

    def fail_on_second(*args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated write failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(store, "_insert_commit", fail_on_second)

    with pytest.raises(WorkspaceError):
        store.write_index(history.list_refs(), commits, (), clear_existing=True)

    with engine.connect() as connection:
        commit_count = connection.execute(text("SELECT COUNT(*) FROM commits")).scalar_one()
        ref_count = connection.execute(text("SELECT COUNT(*) FROM refs")).scalar_one()
        person_count = connection.execute(text("SELECT COUNT(*) FROM persons")).scalar_one()
    engine.dispose()

    assert (commit_count, ref_count, person_count) == baseline
