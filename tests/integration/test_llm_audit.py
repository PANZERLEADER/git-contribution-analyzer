from __future__ import annotations

from sqlalchemy import select, text

from git_contribution_analyzer.adapters.llm.cache import (
    CachedAuditedProvider,
    llm_request_hash,
)
from git_contribution_analyzer.adapters.llm.mock import MockLlmProvider
from git_contribution_analyzer.adapters.storage.sqlite.database import (
    create_database_engine,
    initialize_database,
)
from git_contribution_analyzer.adapters.storage.sqlite.llm_audit import SqliteLlmAuditStore
from git_contribution_analyzer.adapters.storage.sqlite.models import llm_invocations
from git_contribution_analyzer.application.ports.llm import LlmTask


def _task() -> LlmTask:
    return LlmTask(
        task_id="semantic-report",
        prompt_version="semantic-v1",
        schema_version="semantic-v1",
        system_prompt="Return JSON only. API key secret-test-key",
        user_prompt="source body should never be persisted",
        output_schema={"type": "object"},
        allowed_evidence_ids=("EV-001",),
    )


def test_should_cache_completion_and_audit_cache_hit_without_prompt_content(tmp_path) -> None:
    database = tmp_path / "gca.db"
    initialize_database(database)
    store = SqliteLlmAuditStore(database)
    delegate = MockLlmProvider(response={"result": "evidence backed"})
    provider = CachedAuditedProvider(delegate, store)

    first = provider.complete(_task())
    second = provider.complete(_task())

    assert first.content == second.content
    engine = create_database_engine(database)
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                select(llm_invocations).order_by(llm_invocations.c.created_at)
            ).mappings().all()
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
    finally:
        engine.dispose()
    assert revision == "0007_structural_baselines"
    assert len(rows) == 2
    assert rows[0]["attempts"] == 1
    assert rows[0]["cache_hit"] is False
    assert rows[1]["attempts"] == 0
    assert rows[1]["cache_hit"] is True
    assert rows[0]["request_hash"] == llm_request_hash(_task(), "mock", "deterministic")
    database_bytes = database.read_bytes()
    assert b"secret-test-key" not in database_bytes
    assert b"source body should never be persisted" not in database_bytes
