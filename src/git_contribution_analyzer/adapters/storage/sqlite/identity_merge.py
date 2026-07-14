from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import Connection, func, insert, select, update

from git_contribution_analyzer.adapters.storage.sqlite.database import create_database_engine
from git_contribution_analyzer.adapters.storage.sqlite.models import (
    analysis_runs,
    identity_aliases,
    identity_merge_events,
    persons,
    repositories,
)
from git_contribution_analyzer.domain.errors import IdentityResolutionError, WorkspaceError


class SqliteIdentityMergeStore:
    def __init__(self, database_path: Path, repository_root: str) -> None:
        self.database_path = database_path
        self.repository_root = repository_root

    def preview(self, sources: tuple[str, ...], target: str) -> dict[str, Any]:
        engine = create_database_engine(self.database_path)
        try:
            with engine.connect() as connection:
                repository_id = self._repository_id(connection)
                return self._preview(connection, repository_id, sources, target)
        finally:
            engine.dispose()

    def merge(self, sources: tuple[str, ...], target: str) -> dict[str, Any]:
        engine = create_database_engine(self.database_path)
        try:
            with engine.begin() as connection:
                repository_id = self._repository_id(connection)
                preview = self._preview(connection, repository_id, sources, target)
                event_id = str(uuid4())
                target_id = str(preview["target"]["id"])
                source_snapshots = [
                    {
                        "person": source,
                        "aliasIds": [alias["id"] for alias in source["aliases"]],
                    }
                    for source in preview["sources"]
                ]
                moved_alias_ids = sorted(
                    alias_id
                    for snapshot in source_snapshots
                    for alias_id in snapshot["aliasIds"]
                )
                if moved_alias_ids:
                    connection.execute(
                        update(identity_aliases)
                        .where(identity_aliases.c.id.in_(moved_alias_ids))
                        .values(person_id=target_id)
                    )
                source_ids = sorted(str(source["id"]) for source in preview["sources"])
                connection.execute(
                    update(persons)
                    .where(persons.c.id.in_(source_ids))
                    .values(active=False, merged_into_person_id=target_id)
                )
                connection.execute(
                    insert(identity_merge_events).values(
                        id=event_id,
                        repository_id=repository_id,
                        event_type="PERSON_MERGE",
                        target_person_id=target_id,
                        source_person_ids_json=_canonical_json(source_ids),
                        moved_alias_ids_json=_canonical_json(moved_alias_ids),
                        source_snapshots_json=_canonical_json(source_snapshots),
                        status="ACTIVE",
                    )
                )
                return {"mergeId": event_id, "status": "ACTIVE", **preview}
        finally:
            engine.dispose()

    def list_events(self, status: str = "ALL") -> list[dict[str, Any]]:
        engine = create_database_engine(self.database_path)
        try:
            with engine.connect() as connection:
                repository_id = self._repository_id(connection)
                statement = select(identity_merge_events).where(
                    identity_merge_events.c.repository_id == repository_id
                )
                normalized = status.upper()
                if normalized != "ALL":
                    statement = statement.where(
                        identity_merge_events.c.status == normalized
                    )
                rows = connection.execute(
                    statement.order_by(identity_merge_events.c.created_at.desc())
                ).mappings()
                return [self._serialize_event(dict(row)) for row in rows]
        finally:
            engine.dispose()

    def unmerge(self, merge_id: str) -> dict[str, Any]:
        engine = create_database_engine(self.database_path)
        try:
            with engine.begin() as connection:
                repository_id = self._repository_id(connection)
                row = connection.execute(
                    select(identity_merge_events).where(
                        identity_merge_events.c.id == merge_id,
                        identity_merge_events.c.repository_id == repository_id,
                    )
                ).mappings().one_or_none()
                if row is None:
                    raise WorkspaceError(f"Identity merge event not found: {merge_id}")
                if row["status"] != "ACTIVE":
                    raise WorkspaceError(f"Identity merge event is not ACTIVE: {merge_id}")
                target_id = str(row["target_person_id"])
                snapshots = json.loads(str(row["source_snapshots_json"]))
                for snapshot in snapshots:
                    source_id = str(snapshot["person"]["id"])
                    alias_ids = [str(value) for value in snapshot["aliasIds"]]
                    if alias_ids:
                        current = connection.execute(
                            select(identity_aliases.c.id, identity_aliases.c.person_id).where(
                                identity_aliases.c.id.in_(alias_ids)
                            )
                        ).all()
                        current_map = {
                            str(alias_id): str(person_id)
                            for alias_id, person_id in current
                        }
                        conflicts = [
                            alias_id
                            for alias_id in alias_ids
                            if current_map.get(alias_id) != target_id
                        ]
                        if conflicts:
                            raise WorkspaceError(
                                "Cannot unmerge aliases changed after merge: "
                                + ", ".join(sorted(conflicts))
                            )
                        connection.execute(
                            update(identity_aliases)
                            .where(identity_aliases.c.id.in_(alias_ids))
                            .values(person_id=source_id)
                        )
                    connection.execute(
                        update(persons)
                        .where(persons.c.id == source_id)
                        .values(active=True, merged_into_person_id=None)
                    )
                reverted_at = datetime.now(UTC)
                connection.execute(
                    update(identity_merge_events)
                    .where(identity_merge_events.c.id == merge_id)
                    .values(status="REVERTED", reverted_at=reverted_at)
                )
                return {
                    "mergeId": merge_id,
                    "status": "REVERTED",
                    "revertedAt": reverted_at.isoformat(),
                }
        finally:
            engine.dispose()

    def _preview(
        self,
        connection: Connection,
        repository_id: str,
        source_selectors: tuple[str, ...],
        target_selector: str,
    ) -> dict[str, Any]:
        if not source_selectors:
            raise IdentityResolutionError("At least one --source selector is required")
        target = self._resolve_raw(connection, repository_id, target_selector)
        sources = [
            self._resolve_raw(connection, repository_id, selector)
            for selector in source_selectors
        ]
        source_ids = [str(source["id"]) for source in sources]
        if len(source_ids) != len(set(source_ids)):
            raise IdentityResolutionError("Multiple source selectors resolve to the same person")
        if str(target["id"]) in source_ids:
            raise IdentityResolutionError("Merge target cannot also be a source")
        if not target["active"] or not target["confirmed"] or target["kind"] != "HUMAN":
            raise IdentityResolutionError("Merge target must be active, confirmed, and HUMAN")
        for source in sources:
            if not source["active"]:
                raise IdentityResolutionError(
                    f"Merge source is inactive and redirects to {source['mergedIntoPersonId']}"
                )
            if source["kind"] != "HUMAN":
                raise IdentityResolutionError("Merge sources must be HUMAN")
            source["historicalRunCount"] = int(
                connection.execute(
                    select(func.count()).select_from(analysis_runs).where(
                        analysis_runs.c.repository_id == repository_id,
                        analysis_runs.c.person_id == source["id"],
                    )
                ).scalar_one()
            )
        return {
            "target": target,
            "sources": sources,
            "movedAliases": [
                alias for source in sources for alias in source["aliases"]
            ],
            "selectorRedirects": [
                {"selector": selector, "targetPersonId": target["id"]}
                for selector in source_selectors
            ],
            "safeToExecute": True,
        }

    def _resolve_raw(
        self, connection: Connection, repository_id: str, selector: str
    ) -> dict[str, Any]:
        rows = connection.execute(
            select(persons).where(persons.c.repository_id == repository_id)
        ).mappings().all()
        needle = selector.strip().casefold()
        matches: list[dict[str, Any]] = []
        for row in rows:
            aliases = connection.execute(
                select(identity_aliases).where(identity_aliases.c.person_id == row["id"])
            ).mappings().all()
            values = {
                str(row["id"]).casefold(),
                str(row["canonical_name"]).casefold(),
                str(row["canonical_email"]).casefold(),
                *(
                    str(value).casefold()
                    for alias in aliases
                    for value in (alias["name"], alias["email"])
                ),
            }
            if needle in values:
                matches.append(
                    {
                        "id": str(row["id"]),
                        "name": str(row["canonical_name"]),
                        "email": str(row["canonical_email"]),
                        "kind": str(row["kind"]),
                        "confirmed": bool(row["confirmed"]),
                        "active": bool(row["active"]),
                        "mergedIntoPersonId": row["merged_into_person_id"],
                        "aliases": [
                            {
                                "id": str(alias["id"]),
                                "name": str(alias["name"]),
                                "email": str(alias["email"]),
                            }
                            for alias in aliases
                        ],
                    }
                )
        unique = {str(match["id"]): match for match in matches}
        if len(unique) != 1:
            raise IdentityResolutionError(
                f"Person selector must match exactly one identity: {selector}"
            )
        return next(iter(unique.values()))

    def _repository_id(self, connection: Connection) -> str:
        value = connection.execute(
            select(repositories.c.id).where(repositories.c.root_path == self.repository_root)
        ).scalar_one_or_none()
        if value is None:
            raise WorkspaceError(f"Repository is not registered: {self.repository_root}")
        return str(value)

    @staticmethod
    def _serialize_event(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "mergeId": str(row["id"]),
            "eventType": str(row["event_type"]),
            "targetPersonId": str(row["target_person_id"]),
            "sourcePersonIds": json.loads(str(row["source_person_ids_json"])),
            "movedAliasIds": json.loads(str(row["moved_alias_ids_json"])),
            "status": str(row["status"]),
            "createdAt": row["created_at"].isoformat(),
            "revertedAt": (
                row["reverted_at"].isoformat() if row["reverted_at"] else None
            ),
        }


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
