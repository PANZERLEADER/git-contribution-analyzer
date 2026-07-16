from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import Connection, delete, func, insert, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from git_contribution_analyzer.adapters.storage.sqlite.database import create_database_engine
from git_contribution_analyzer.adapters.storage.sqlite.identity_merge import reassign_alias
from git_contribution_analyzer.adapters.storage.sqlite.models import (
    commit_delivery,
    commit_parents,
    commits,
    file_changes,
    identity_aliases,
    persons,
    refs,
    repositories,
)
from git_contribution_analyzer.domain.errors import WorkspaceError
from git_contribution_analyzer.domain.models.git_history import (
    CommitDelivery,
    GitCommit,
    GitIdentity,
    GitRef,
)


class SqliteGitIndexStore:
    def __init__(self, database_path: Any, repository_root: str) -> None:
        self.database_path = database_path
        self.repository_root = repository_root

    def _repository_id(self, connection: Connection) -> str:
        repository_id = connection.execute(
            select(repositories.c.id).where(repositories.c.root_path == self.repository_root)
        ).scalar_one_or_none()
        if repository_id is None:
            raise WorkspaceError(f"Repository is not registered: {self.repository_root}")
        return str(repository_id)

    def existing_commit_hashes(self) -> set[str]:
        engine = create_database_engine(self.database_path)
        try:
            with engine.connect() as connection:
                repository_id = self._repository_id(connection)
                return set(
                    connection.execute(
                        select(commits.c.hash).where(commits.c.repository_id == repository_id)
                    ).scalars()
                )
        finally:
            engine.dispose()

    def write_index(
        self,
        git_refs: Iterable[GitRef],
        git_commits: Iterable[GitCommit],
        deliveries: Iterable[CommitDelivery],
        *,
        clear_existing: bool,
        default_branch: str | None = None,
    ) -> None:
        engine = create_database_engine(self.database_path)
        try:
            with engine.begin() as connection:
                repository_id = self._repository_id(connection)
                if default_branch is not None:
                    connection.execute(
                        update(repositories)
                        .where(repositories.c.id == repository_id)
                        .values(default_branch=default_branch, updated_at=datetime.now(UTC))
                    )
                if clear_existing:
                    self._clear(connection, repository_id)
                self._replace_refs(connection, repository_id, git_refs)
                for commit in git_commits:
                    self._insert_commit(connection, repository_id, commit)
                self._replace_delivery(connection, repository_id, deliveries)
        except Exception as exc:
            if isinstance(exc, WorkspaceError):
                raise
            raise WorkspaceError("Unable to persist Git index") from exc
        finally:
            engine.dispose()

    def _clear(self, connection: Connection, repository_id: str) -> None:
        person_ids = list(
            connection.execute(
                select(persons.c.id).where(persons.c.repository_id == repository_id)
            ).scalars()
        )
        indexed_tables = (
            commit_delivery,
            file_changes,
            commit_parents,
            commits,
            identity_aliases,
            refs,
        )
        for table in indexed_tables:
            connection.execute(delete(table).where(table.c.repository_id == repository_id))
        if person_ids:
            connection.execute(delete(persons).where(persons.c.id.in_(person_ids)))

    def _replace_refs(
        self,
        connection: Connection,
        repository_id: str,
        git_refs: Iterable[GitRef],
    ) -> None:
        connection.execute(
            update(refs).where(refs.c.repository_id == repository_id).values(active=False)
        )
        for git_ref in git_refs:
            statement = sqlite_insert(refs).values(
                repository_id=repository_id,
                ref_name=git_ref.name,
                commit_hash=git_ref.commit_hash,
                ref_type=git_ref.ref_type,
                active=True,
                observed_at=datetime.now(UTC),
            )
            connection.execute(
                statement.on_conflict_do_update(
                    index_elements=[refs.c.repository_id, refs.c.ref_name],
                    set_={
                        "commit_hash": git_ref.commit_hash,
                        "ref_type": git_ref.ref_type,
                        "active": True,
                        "observed_at": datetime.now(UTC),
                    },
                )
            )

    def _insert_commit(
        self,
        connection: Connection,
        repository_id: str,
        commit: GitCommit,
    ) -> None:
        alias_id = self._resolve_alias(connection, repository_id, commit.author)
        commit_statement = sqlite_insert(commits).values(
            repository_id=repository_id,
            hash=commit.hash,
            author_alias_id=alias_id,
            committer_name=commit.committer_name,
            committer_email=commit.committer_email,
            authored_at=commit.authored_at.astimezone(UTC),
            committed_at=commit.committed_at.astimezone(UTC),
            subject=commit.subject,
            body=commit.body,
            is_merge=commit.is_merge,
            tree_hash=commit.tree_hash,
            patch_id=commit.patch_id,
            reverts_hash=commit.reverts_hash,
            insertions=commit.insertions,
            deletions=commit.deletions,
            files_changed=len(commit.changes),
        )
        result = connection.execute(
            commit_statement.on_conflict_do_nothing(
                index_elements=[commits.c.repository_id, commits.c.hash]
            )
        )
        if result.rowcount == 0:
            return
        for parent_index, parent_hash in enumerate(commit.parents):
            connection.execute(
                insert(commit_parents).values(
                    repository_id=repository_id,
                    commit_hash=commit.hash,
                    parent_index=parent_index,
                    parent_hash=parent_hash,
                )
            )
        if commit.changes:
            connection.execute(
                insert(file_changes),
                [
                    {
                        "repository_id": repository_id,
                        "commit_hash": commit.hash,
                        "old_path": change.old_path,
                        "new_path": change.new_path,
                        "change_type": change.change_type,
                        "is_binary": change.is_binary,
                        "is_excluded": False,
                        "insertions": change.insertions,
                        "deletions": change.deletions,
                    }
                    for change in commit.changes
                ],
            )

    def _resolve_alias(
        self,
        connection: Connection,
        repository_id: str,
        identity: GitIdentity,
    ) -> str:
        alias_id = str(
            uuid5(
                NAMESPACE_URL,
                f"{repository_id}:alias:{identity.name}:{identity.email.lower()}",
            )
        )
        person_id = str(
            uuid5(
                NAMESPACE_URL,
                f"{repository_id}:person:{identity.canonical_email.lower()}",
            )
        )
        person_statement = sqlite_insert(persons).values(
            id=person_id,
            repository_id=repository_id,
            canonical_name=identity.canonical_name,
            canonical_email=identity.canonical_email.lower(),
            kind="HUMAN",
            confirmed=identity.confirmed,
        )
        connection.execute(
            person_statement.on_conflict_do_update(
                index_elements=[persons.c.repository_id, persons.c.canonical_email],
                set_={"confirmed": persons.c.confirmed | identity.confirmed},
            )
        )
        person_id = str(
            connection.execute(
                select(persons.c.id).where(
                    persons.c.repository_id == repository_id,
                    persons.c.canonical_email == identity.canonical_email.lower(),
                )
            ).scalar_one()
        )
        alias_statement = sqlite_insert(identity_aliases).values(
            id=alias_id,
            repository_id=repository_id,
            person_id=person_id,
            name=identity.name,
            email=identity.email,
            normalized_email=identity.email.lower(),
            source=identity.source,
            confidence=1.0 if identity.confirmed else 0.95,
            confirmed=identity.confirmed,
            rationale="Resolved by .mailmap" if identity.confirmed else "Exact normalized email",
        )
        connection.execute(
            alias_statement.on_conflict_do_update(
                # Alias IDs normalize email case, so case-only Git author variants
                # must resolve through the same primary key as well.
                index_elements=[identity_aliases.c.id],
                set_={
                    "person_id": person_id,
                    "source": identity.source,
                    "confirmed": identity.confirmed,
                },
            )
        )
        return alias_id

    def _replace_delivery(
        self,
        connection: Connection,
        repository_id: str,
        deliveries: Iterable[CommitDelivery],
    ) -> None:
        connection.execute(
            delete(commit_delivery).where(commit_delivery.c.repository_id == repository_id)
        )
        values = [
            {
                "repository_id": repository_id,
                "commit_hash": delivery.commit_hash,
                "target_ref": delivery.target_ref,
                "status": delivery.status,
                "release_ref": delivery.release_ref,
                "related_commit_hash": delivery.related_commit_hash,
            }
            for delivery in deliveries
        ]
        if values:
            connection.execute(insert(commit_delivery), values)

    def relation_summaries(self) -> list[dict[str, Any]]:
        engine = create_database_engine(self.database_path)
        try:
            with engine.connect() as connection:
                repository_id = self._repository_id(connection)
                rows = connection.execute(
                    select(
                        commits.c.hash,
                        commits.c.patch_id,
                        commits.c.reverts_hash,
                    ).where(commits.c.repository_id == repository_id)
                ).mappings()
                return [dict(row) for row in rows]
        finally:
            engine.dispose()

    def stats(self) -> dict[str, int]:
        engine = create_database_engine(self.database_path)
        try:
            with engine.connect() as connection:
                repository_id = self._repository_id(connection)
                commit_count = connection.execute(
                    select(func.count()).select_from(commits).where(
                        commits.c.repository_id == repository_id
                    )
                ).scalar_one()
                identity_count = connection.execute(
                    select(func.count()).select_from(persons).where(
                        persons.c.repository_id == repository_id
                    )
                ).scalar_one()
                unresolved_count = connection.execute(
                    select(func.count()).select_from(persons).where(
                        persons.c.repository_id == repository_id,
                        persons.c.confirmed.is_(False),
                    )
                ).scalar_one()
                active_ref_count = connection.execute(
                    select(func.count()).select_from(refs).where(
                        refs.c.repository_id == repository_id,
                        refs.c.active.is_(True),
                    )
                ).scalar_one()
            return {
                "indexedCommits": int(commit_count),
                "identities": int(identity_count),
                "unresolvedIdentities": int(unresolved_count),
                "refs": int(active_ref_count),
            }
        finally:
            engine.dispose()

    def list_identities(self, *, unresolved_only: bool = False) -> list[dict[str, Any]]:
        engine = create_database_engine(self.database_path)
        try:
            with engine.connect() as connection:
                repository_id = self._repository_id(connection)
                statement = select(persons).where(persons.c.repository_id == repository_id)
                if unresolved_only:
                    statement = statement.where(persons.c.confirmed.is_(False))
                person_rows = connection.execute(statement).mappings().all()
                result: list[dict[str, Any]] = []
                for person in person_rows:
                    aliases = connection.execute(
                        select(identity_aliases).where(
                            identity_aliases.c.person_id == person["id"]
                        )
                    ).mappings()
                    result.append(
                        {
                            "id": person["id"],
                            "name": person["canonical_name"],
                            "email": person["canonical_email"],
                            "kind": person["kind"],
                            "confirmed": bool(person["confirmed"]),
                            "active": bool(person["active"]),
                            "mergedIntoPersonId": person["merged_into_person_id"],
                            "aliases": [
                                {
                                    "id": alias["id"],
                                    "name": alias["name"],
                                    "email": alias["email"],
                                    "source": alias["source"],
                                    "confirmed": bool(alias["confirmed"]),
                                }
                                for alias in aliases
                            ],
                        }
                    )
                return result
        finally:
            engine.dispose()

    def map_identity(
        self,
        *,
        name: str,
        email: str,
        person_name: str,
        person_email: str,
    ) -> dict[str, Any]:
        engine = create_database_engine(self.database_path)
        try:
            with engine.begin() as connection:
                repository_id = self._repository_id(connection)
                alias = connection.execute(
                    select(identity_aliases).where(
                        identity_aliases.c.repository_id == repository_id,
                        identity_aliases.c.name == name,
                        identity_aliases.c.email == email,
                    )
                ).mappings().one_or_none()
                if alias is None:
                    raise WorkspaceError(f"Identity alias not found: {name} <{email}>")
                person_id = str(
                    uuid5(
                        NAMESPACE_URL,
                        f"{repository_id}:person:{person_email.lower()}",
                    )
                )
                statement = sqlite_insert(persons).values(
                    id=person_id,
                    repository_id=repository_id,
                    canonical_name=person_name,
                    canonical_email=person_email.lower(),
                    kind="HUMAN",
                    confirmed=True,
                )
                connection.execute(
                    statement.on_conflict_do_update(
                        index_elements=[persons.c.repository_id, persons.c.canonical_email],
                        set_={"canonical_name": person_name, "confirmed": True},
                    )
                )
                person_id = str(
                    connection.execute(
                        select(persons.c.id).where(
                            persons.c.repository_id == repository_id,
                            persons.c.canonical_email == person_email.lower(),
                        )
                    ).scalar_one()
                )
                reassign_alias(
                    connection,
                    repository_id,
                    str(alias["id"]),
                    person_id,
                )
                connection.execute(
                    update(identity_aliases)
                    .where(identity_aliases.c.id == alias["id"])
                    .values(
                        source="MANUAL",
                        confidence=1.0,
                        confirmed=True,
                        rationale="Confirmed by user",
                    )
                )
                return {
                    "id": person_id,
                    "name": person_name,
                    "email": person_email.lower(),
                    "confirmed": True,
                }
        finally:
            engine.dispose()
