from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Connection, and_, delete, insert, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from git_contribution_analyzer.adapters.storage.sqlite.database import create_database_engine
from git_contribution_analyzer.adapters.storage.sqlite.models import (
    analysis_runs,
    capability_assessments,
    commit_delivery,
    commits,
    contribution_items,
    evidence,
    file_changes,
    identity_aliases,
    persons,
    refs,
    repositories,
)
from git_contribution_analyzer.domain.errors import (
    IdentityResolutionError,
    ReportError,
    WorkspaceError,
)
from git_contribution_analyzer.domain.models.analysis import AnalysisFilters
from git_contribution_analyzer.domain.models.contribution import ContributionCommit
from git_contribution_analyzer.domain.models.run import RunType
from git_contribution_analyzer.domain.services.contribution_rules import (
    classify_commit,
    is_generated_path,
    module_from_path,
)


class SqliteAnalysisStore:
    def __init__(self, database_path: Path, repository_root: str) -> None:
        self.database_path = database_path
        self.repository_root = repository_root

    def _repository(self, connection: Connection) -> dict[str, Any]:
        row = connection.execute(
            select(repositories).where(repositories.c.root_path == self.repository_root)
        ).mappings().one_or_none()
        if row is None:
            raise WorkspaceError(f"Repository is not registered: {self.repository_root}")
        return dict(row)

    def resolve_confirmed_person(self, selector: str) -> dict[str, Any]:
        return self.resolve_people((selector,), require_confirmed=True)[0]

    def resolve_people(
        self,
        selectors: tuple[str, ...],
        *,
        require_confirmed: bool,
    ) -> list[dict[str, Any]]:
        if not selectors:
            return []
        engine = create_database_engine(self.database_path)
        try:
            with engine.connect() as connection:
                repository = self._repository(connection)
                person_rows = list(
                    connection.execute(
                    select(persons).where(persons.c.repository_id == repository["id"])
                    ).mappings()
                )
                people_by_id = {str(row["id"]): dict(row) for row in person_rows}
                aliases_by_person: dict[str, list[tuple[str, str]]] = {}
                for person_row in person_rows:
                    aliases = connection.execute(
                        select(identity_aliases.c.name, identity_aliases.c.email).where(
                            identity_aliases.c.person_id == person_row["id"]
                        )
                    ).all()
                    aliases_by_person[str(person_row["id"])] = [
                        (str(name), str(email)) for name, email in aliases
                    ]
        finally:
            engine.dispose()
        resolved: list[dict[str, Any]] = []
        for selector in selectors:
            needle = selector.strip().casefold()
            matches = []
            for person_row in person_rows:
                person_id = str(person_row["id"])
                values = {
                    person_id.casefold(),
                    str(person_row["canonical_name"]).casefold(),
                    str(person_row["canonical_email"]).casefold(),
                    *(
                        value.casefold()
                        for alias in aliases_by_person[person_id]
                        for value in alias
                    ),
                }
                if needle in values:
                    matches.append(dict(person_row))
            unique = {str(person["id"]): person for person in matches}
            if len(unique) != 1:
                raise IdentityResolutionError(
                    f"Person selector must match exactly one identity: {selector}"
                )
            selected = next(iter(unique.values()))
            visited: set[str] = set()
            while not bool(selected["active"]):
                selected_id = str(selected["id"])
                if selected_id in visited:
                    raise IdentityResolutionError(
                        f"Identity redirect cycle detected: {selector}"
                    )
                visited.add(selected_id)
                redirect_id = selected["merged_into_person_id"]
                if redirect_id is None or str(redirect_id) not in people_by_id:
                    raise IdentityResolutionError(
                        f"Inactive identity has no valid redirect: {selector}"
                    )
                selected = people_by_id[str(redirect_id)]
            if require_confirmed and not bool(selected["confirmed"]):
                raise IdentityResolutionError(
                    f"Identity is not confirmed: {selected['canonical_name']} "
                    f"<{selected['canonical_email']}>"
                )
            resolved.append(
                {
                    "id": str(selected["id"]),
                    "name": str(selected["canonical_name"]),
                    "email": str(selected["canonical_email"]),
                    "kind": str(selected["kind"]),
                    "confirmed": bool(selected["confirmed"]),
                }
            )
        return resolved

    def list_people_for_analysis(self) -> list[dict[str, Any]]:
        engine = create_database_engine(self.database_path)
        try:
            with engine.connect() as connection:
                repository = self._repository(connection)
                rows = connection.execute(
                    select(persons)
                    .where(
                        persons.c.repository_id == repository["id"],
                        persons.c.active.is_(True),
                    )
                    .order_by(persons.c.canonical_name, persons.c.canonical_email)
                ).mappings()
                result = []
                for row in rows:
                    aliases = connection.execute(
                        select(identity_aliases.c.name, identity_aliases.c.email)
                        .where(identity_aliases.c.person_id == row["id"])
                        .order_by(identity_aliases.c.name, identity_aliases.c.email)
                    ).all()
                    result.append(
                        {
                            "id": str(row["id"]),
                            "name": str(row["canonical_name"]),
                            "email": str(row["canonical_email"]),
                            "kind": str(row["kind"]),
                            "confirmed": bool(row["confirmed"]),
                            "active": bool(row["active"]),
                            "mergedIntoPersonId": row["merged_into_person_id"],
                            "aliases": [
                                {"name": str(name), "email": str(email)}
                                for name, email in aliases
                            ],
                        }
                    )
                return result
        finally:
            engine.dispose()

    def baseline_commit(self) -> str | None:
        engine = create_database_engine(self.database_path)
        try:
            with engine.connect() as connection:
                repository = self._repository(connection)
                target_ref = f"refs/heads/{repository['default_branch']}"
                return connection.execute(
                    select(refs.c.commit_hash).where(
                        refs.c.repository_id == repository["id"],
                        refs.c.ref_name == target_ref,
                    )
                ).scalar_one_or_none()
        finally:
            engine.dispose()

    def load_commits(
        self,
        person_id: str | None,
        filters: AnalysisFilters,
        *,
        allowed_hashes: set[str] | None = None,
    ) -> tuple[ContributionCommit, ...]:
        engine = create_database_engine(self.database_path)
        try:
            with engine.connect() as connection:
                repository = self._repository(connection)
                target_ref = f"refs/heads/{repository['default_branch']}"
                statement = (
                    select(
                        commits.c.hash,
                        commits.c.subject,
                        commits.c.authored_at,
                        commits.c.insertions,
                        commits.c.deletions,
                        commits.c.files_changed,
                        commits.c.is_merge,
                        commits.c.patch_id,
                        commits.c.reverts_hash,
                        commit_delivery.c.status,
                        commit_delivery.c.release_ref,
                    )
                    .join(
                        identity_aliases,
                        commits.c.author_alias_id == identity_aliases.c.id,
                    )
                    .outerjoin(
                        commit_delivery,
                        and_(
                            commit_delivery.c.repository_id == commits.c.repository_id,
                            commit_delivery.c.commit_hash == commits.c.hash,
                            commit_delivery.c.target_ref == target_ref,
                        ),
                    )
                    .where(
                        commits.c.repository_id == repository["id"],
                        identity_aliases.c.person_id == person_id,
                    )
                    .order_by(commits.c.authored_at, commits.c.hash)
                )
                if filters.since:
                    statement = statement.where(commits.c.authored_at >= filters.since)
                if filters.until:
                    statement = statement.where(commits.c.authored_at <= filters.until)
                if filters.release:
                    release_ref = (
                        filters.release
                        if filters.release.startswith("refs/tags/")
                        else f"refs/tags/{filters.release}"
                    )
                    statement = statement.where(commit_delivery.c.release_ref == release_ref)
                if filters.delivery:
                    delivery = filters.delivery.upper()
                    if delivery == "DELIVERED":
                        statement = statement.where(
                            commit_delivery.c.status.in_(("LANDED", "RELEASED", "REVERTED"))
                        )
                    else:
                        statement = statement.where(commit_delivery.c.status == delivery)
                rows = [
                    dict(row)
                    for row in connection.execute(statement).mappings()
                    if allowed_hashes is None or str(row["hash"]) in allowed_hashes
                ]
                changes_by_commit = self._load_changes(
                    connection,
                    str(repository["id"]),
                    tuple(str(row["hash"]) for row in rows),
                )
        finally:
            engine.dispose()

        facts: list[ContributionCommit] = []
        scope = filters.scope.replace("\\", "/").strip("/") if filters.scope else None
        for row in rows:
            changes = changes_by_commit.get(str(row["hash"]), ())
            paths = tuple(path for path, _binary, _excluded, _insertions, _deletions in changes)
            if scope and not any(path == scope or path.startswith(f"{scope}/") for path in paths):
                continue
            facts.append(
                ContributionCommit(
                    hash=str(row["hash"]),
                    subject=str(row["subject"]),
                    authored_at=row["authored_at"],
                    commit_type=classify_commit(str(row["subject"])),
                    delivery_status=str(row["status"] or "AUTHORED_ONLY"),
                    paths=paths,
                    modules=tuple(sorted({module_from_path(path) for path in paths})),
                    insertions=int(row["insertions"]),
                    deletions=int(row["deletions"]),
                    files_changed=int(row["files_changed"]),
                    merge=bool(row["is_merge"]),
                    binary_files=sum(
                        binary
                        for _path, binary, _excluded, _insertions, _deletions in changes
                    ),
                    generated_files=sum(is_generated_path(path) for path in paths),
                    patch_id=str(row["patch_id"]) if row["patch_id"] else None,
                    reverts_hash=(
                        str(row["reverts_hash"]) if row["reverts_hash"] else None
                    ),
                    effective_insertions=sum(
                        insertions
                        for path, binary, excluded, insertions, _deletions in changes
                        if not binary and not excluded and not is_generated_path(path)
                    ),
                    effective_deletions=sum(
                        deletions
                        for path, binary, excluded, _insertions, deletions in changes
                        if not binary and not excluded and not is_generated_path(path)
                    ),
                    effective_files_changed=sum(
                        1
                        for path, binary, excluded, _insertions, _deletions in changes
                        if not binary and not excluded and not is_generated_path(path)
                    ),
                )
            )
        return tuple(facts)

    def _load_changes(
        self,
        connection: Connection,
        repository_id: str,
        commit_hashes: tuple[str, ...],
    ) -> dict[str, tuple[tuple[str, bool, bool, int, int], ...]]:
        grouped: defaultdict[str, list[tuple[str, bool, bool, int, int]]] = defaultdict(list)
        for start in range(0, len(commit_hashes), 500):
            batch = commit_hashes[start : start + 500]
            if not batch:
                continue
            rows = connection.execute(
                select(
                    file_changes.c.commit_hash,
                    file_changes.c.old_path,
                    file_changes.c.new_path,
                    file_changes.c.is_binary,
                    file_changes.c.is_excluded,
                    file_changes.c.insertions,
                    file_changes.c.deletions,
                ).where(
                    file_changes.c.repository_id == repository_id,
                    file_changes.c.commit_hash.in_(batch),
                )
            )
            for commit_hash, old_path, new_path, binary, excluded, insertions, deletions in rows:
                path = str(new_path or old_path or "")
                if path:
                    grouped[str(commit_hash)].append(
                        (
                            path.replace("\\", "/"),
                            bool(binary),
                            bool(excluded),
                            int(insertions),
                            int(deletions),
                        )
                    )
        return {key: tuple(value) for key, value in grouped.items()}

    def start_run(
        self,
        *,
        run_id: str,
        person_id: str | None,
        parameters: dict[str, Any],
        baseline_commit: str | None,
        started_at: datetime,
        run_type: RunType = RunType.ANALYSIS,
        parent_run_id: str | None = None,
    ) -> None:
        engine = create_database_engine(self.database_path)
        try:
            with engine.begin() as connection:
                repository = self._repository(connection)
                if parent_run_id is not None:
                    parent = connection.execute(
                        select(
                            analysis_runs.c.repository_id,
                            analysis_runs.c.status,
                        ).where(analysis_runs.c.id == parent_run_id)
                    ).mappings().one_or_none()
                    if parent is None:
                        raise ReportError(f"Parent analysis run not found: {parent_run_id}")
                    if str(parent["repository_id"]) != str(repository["id"]):
                        raise ReportError("Parent analysis run belongs to another repository")
                    if str(parent["status"]) not in ("COMPLETED", "PARTIAL"):
                        raise ReportError("Parent analysis run is not completed")
                for table in (capability_assessments, evidence, contribution_items):
                    connection.execute(delete(table).where(table.c.run_id == run_id))
                statement = sqlite_insert(analysis_runs).values(
                    id=run_id,
                    repository_id=repository["id"],
                    status="RUNNING",
                    schema_version="1.0",
                    started_at=started_at,
                    completed_at=None,
                    person_id=person_id,
                    parameters_json=_json(parameters),
                    baseline_commit=baseline_commit,
                    rule_version="rules-v1",
                    provider_id="none",
                    run_type=run_type.value,
                    parent_run_id=parent_run_id,
                    result_json=None,
                    error_message=None,
                )
                connection.execute(
                    statement.on_conflict_do_update(
                        index_elements=[analysis_runs.c.id],
                        set_={
                            "repository_id": repository["id"],
                            "status": "RUNNING",
                            "schema_version": "1.0",
                            "started_at": started_at,
                            "completed_at": None,
                            "person_id": person_id,
                            "parameters_json": _json(parameters),
                            "baseline_commit": baseline_commit,
                            "rule_version": "rules-v1",
                            "provider_id": "none",
                            "run_type": run_type.value,
                            "parent_run_id": parent_run_id,
                            "result_json": None,
                            "error_message": None,
                        },
                    )
                )
        finally:
            engine.dispose()

    def complete_run(
        self,
        *,
        run_id: str,
        completed_at: datetime,
        report: dict[str, Any],
        status: str = "COMPLETED",
        provider_id: str = "none",
        persist_details: bool = True,
    ) -> None:
        engine = create_database_engine(self.database_path)
        try:
            with engine.begin() as connection:
                connection.execute(
                    update(analysis_runs)
                    .where(analysis_runs.c.id == run_id)
                    .values(
                        status=status,
                        completed_at=completed_at,
                        provider_id=provider_id,
                        result_json=_json(report),
                    )
                )
                if persist_details:
                    self._insert_report_rows(connection, run_id, report)
        finally:
            engine.dispose()

    def fail_run(self, run_id: str, completed_at: datetime, message: str) -> None:
        engine = create_database_engine(self.database_path)
        try:
            with engine.begin() as connection:
                connection.execute(
                    update(analysis_runs)
                    .where(analysis_runs.c.id == run_id)
                    .values(status="FAILED", completed_at=completed_at, error_message=message)
                )
        finally:
            engine.dispose()

    def _insert_report_rows(
        self, connection: Connection, run_id: str, report: dict[str, Any]
    ) -> None:
        item_rows = [
            {
                "run_id": run_id,
                "item_id": item["id"],
                "item_order": index,
                "group_key": item["groupKey"],
                "title": item["title"],
                "confidence": item["confidence"],
                "commits_json": _json(item["commitHashes"]),
                "evidence_ids_json": _json(item["evidenceIds"]),
            }
            for index, item in enumerate(report["contributionItems"], start=1)
        ]
        if item_rows:
            connection.execute(insert(contribution_items), item_rows)
        evidence_rows = [
            {
                "run_id": run_id,
                "evidence_id": entry["id"],
                "evidence_type": entry["type"],
                "summary": entry["summary"],
                "commit_hashes_json": _json(entry["commitHashes"]),
                "paths_json": _json(entry["paths"]),
                "metrics_json": _json(entry["metrics"]),
            }
            for entry in report["evidence"]
        ]
        if evidence_rows:
            connection.execute(insert(evidence), evidence_rows)
        capability_rows = [
            {
                "run_id": run_id,
                "capability": entry["capability"],
                "confidence": entry["confidence"],
                "rationale": entry["rationale"],
                "evidence_ids_json": _json(entry["evidenceIds"]),
                "gaps_json": _json(entry["gaps"]),
            }
            for entry in report["capabilities"]
        ]
        if capability_rows:
            connection.execute(insert(capability_assessments), capability_rows)

    def list_runs(self) -> list[dict[str, Any]]:
        engine = create_database_engine(self.database_path)
        try:
            with engine.connect() as connection:
                repository = self._repository(connection)
                rows = connection.execute(
                    select(analysis_runs)
                    .where(analysis_runs.c.repository_id == repository["id"])
                    .order_by(analysis_runs.c.started_at.desc(), analysis_runs.c.id.desc())
                ).mappings()
                return [
                    {
                        "id": str(row["id"]),
                        "status": str(row["status"]),
                        "startedAt": _iso_utc(row["started_at"]),
                        "completedAt": (
                            _iso_utc(row["completed_at"]) if row["completed_at"] else None
                        ),
                        "personId": row["person_id"],
                        "parameters": json.loads(str(row["parameters_json"])),
                        "baselineCommit": row["baseline_commit"],
                        "ruleVersion": str(row["rule_version"]),
                        "providerId": str(row["provider_id"]),
                        "runType": str(row["run_type"] or RunType.ANALYSIS.value),
                        "parentRunId": row["parent_run_id"],
                        "error": row["error_message"],
                    }
                    for row in rows
                ]
        finally:
            engine.dispose()

    def get_report(self, run_id: str) -> dict[str, Any]:
        engine = create_database_engine(self.database_path)
        try:
            with engine.connect() as connection:
                repository = self._repository(connection)
                actual_id = run_id
                if run_id == "latest":
                    actual_id = str(
                        connection.execute(
                            select(analysis_runs.c.id)
                            .where(
                                analysis_runs.c.repository_id == repository["id"],
                                analysis_runs.c.status.in_(("COMPLETED", "PARTIAL")),
                            )
                            .order_by(
                                analysis_runs.c.completed_at.desc(), analysis_runs.c.id.desc()
                            )
                            .limit(1)
                        ).scalar_one_or_none()
                    )
                result_json = connection.execute(
                    select(analysis_runs.c.result_json).where(
                        analysis_runs.c.repository_id == repository["id"],
                        analysis_runs.c.id == actual_id,
                    )
                ).scalar_one_or_none()
        finally:
            engine.dispose()
        if not result_json:
            raise ReportError(f"Completed analysis run not found: {run_id}")
        return dict(json.loads(str(result_json)))


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _iso_utc(value: datetime) -> str:
    aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return aware.isoformat()
