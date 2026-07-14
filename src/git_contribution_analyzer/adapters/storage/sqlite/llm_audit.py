from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import func, insert, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from git_contribution_analyzer.adapters.storage.sqlite.database import create_database_engine
from git_contribution_analyzer.adapters.storage.sqlite.models import llm_cache, llm_invocations


class SqliteLlmAuditStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def get_cached(self, request_hash: str) -> dict[str, Any] | None:
        engine = create_database_engine(self.database_path)
        try:
            with engine.begin() as connection:
                value = connection.execute(
                    select(llm_cache.c.response_json).where(
                        llm_cache.c.request_hash == request_hash
                    )
                ).scalar_one_or_none()
                if value is not None:
                    connection.execute(
                        update(llm_cache)
                        .where(llm_cache.c.request_hash == request_hash)
                        .values(last_used_at=func.now())
                    )
        finally:
            engine.dispose()
        return dict(json.loads(str(value))) if value is not None else None

    def put_cached(
        self,
        *,
        request_hash: str,
        provider_id: str,
        model: str,
        prompt_version: str,
        schema_version: str,
        response: dict[str, Any],
    ) -> None:
        engine = create_database_engine(self.database_path)
        statement = sqlite_insert(llm_cache).values(
            request_hash=request_hash,
            provider_id=provider_id,
            model=model,
            prompt_version=prompt_version,
            schema_version=schema_version,
            response_json=_json(response),
        )
        try:
            with engine.begin() as connection:
                connection.execute(
                    statement.on_conflict_do_update(
                        index_elements=[llm_cache.c.request_hash],
                        set_={"response_json": _json(response)},
                    )
                )
        finally:
            engine.dispose()

    def record_invocation(
        self,
        *,
        run_id: str | None,
        request_hash: str,
        provider_id: str,
        model: str,
        prompt_version: str,
        schema_version: str,
        attempts: int,
        latency_ms: int,
        status: str,
        error_code: str | None = None,
        error_message: str | None = None,
        cache_hit: bool = False,
    ) -> None:
        engine = create_database_engine(self.database_path)
        try:
            with engine.begin() as connection:
                connection.execute(
                    insert(llm_invocations).values(
                        id=str(uuid4()),
                        run_id=run_id,
                        request_hash=request_hash,
                        provider_id=provider_id,
                        model=model,
                        prompt_version=prompt_version,
                        schema_version=schema_version,
                        attempts=attempts,
                        latency_ms=max(0, latency_ms),
                        status=status,
                        error_code=error_code,
                        error_message=error_message,
                        cache_hit=cache_hit,
                    )
                )
        finally:
            engine.dispose()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
