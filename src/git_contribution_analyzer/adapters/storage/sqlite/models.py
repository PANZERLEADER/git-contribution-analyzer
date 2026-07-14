from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)

metadata = MetaData()

repositories = Table(
    "repositories",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("root_path", String, nullable=False, unique=True),
    Column("git_dir", String, nullable=False),
    Column("default_branch", String, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

analysis_runs = Table(
    "analysis_runs",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("repository_id", String(36), nullable=False),
    Column("status", String(20), nullable=False),
    Column("schema_version", String(20), nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("completed_at", DateTime(timezone=True), nullable=True),
    Column("person_id", String(36), nullable=True),
    Column("parameters_json", Text, nullable=False, default="{}"),
    Column("baseline_commit", String(64), nullable=True),
    Column("rule_version", String(40), nullable=False, default="rules-v1"),
    Column("provider_id", String(40), nullable=False, default="none"),
    Column("run_type", String(32), nullable=False, default="ANALYSIS"),
    Column("parent_run_id", String(36), nullable=True),
    Column("result_json", Text, nullable=True),
    Column("error_message", Text, nullable=True),
)

contribution_items = Table(
    "contribution_items",
    metadata,
    Column("run_id", String(36), ForeignKey("analysis_runs.id"), primary_key=True),
    Column("item_id", String(20), primary_key=True),
    Column("item_order", Integer, nullable=False),
    Column("group_key", String, nullable=False),
    Column("title", Text, nullable=False),
    Column("confidence", String(20), nullable=False),
    Column("commits_json", Text, nullable=False),
    Column("evidence_ids_json", Text, nullable=False),
)

evidence = Table(
    "evidence",
    metadata,
    Column("run_id", String(36), ForeignKey("analysis_runs.id"), primary_key=True),
    Column("evidence_id", String(20), primary_key=True),
    Column("evidence_type", String(40), nullable=False),
    Column("summary", Text, nullable=False),
    Column("commit_hashes_json", Text, nullable=False),
    Column("paths_json", Text, nullable=False),
    Column("metrics_json", Text, nullable=False),
)

capability_assessments = Table(
    "capability_assessments",
    metadata,
    Column("run_id", String(36), ForeignKey("analysis_runs.id"), primary_key=True),
    Column("capability", String(60), primary_key=True),
    Column("confidence", String(20), nullable=False),
    Column("rationale", Text, nullable=False),
    Column("evidence_ids_json", Text, nullable=False),
    Column("gaps_json", Text, nullable=False),
)

llm_invocations = Table(
    "llm_invocations",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("run_id", String(36), ForeignKey("analysis_runs.id"), nullable=True),
    Column("request_hash", String(64), nullable=False),
    Column("provider_id", String(40), nullable=False),
    Column("model", String(120), nullable=False),
    Column("prompt_version", String(40), nullable=False),
    Column("schema_version", String(40), nullable=False),
    Column("attempts", Integer, nullable=False),
    Column("latency_ms", Integer, nullable=False),
    Column("status", String(20), nullable=False),
    Column("error_code", String(40), nullable=True),
    Column("error_message", Text, nullable=True),
    Column("cache_hit", Boolean, nullable=False, default=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

llm_cache = Table(
    "llm_cache",
    metadata,
    Column("request_hash", String(64), primary_key=True),
    Column("provider_id", String(40), nullable=False),
    Column("model", String(120), nullable=False),
    Column("prompt_version", String(40), nullable=False),
    Column("schema_version", String(40), nullable=False),
    Column("response_json", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("last_used_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

refs = Table(
    "refs",
    metadata,
    Column("repository_id", String(36), ForeignKey("repositories.id"), primary_key=True),
    Column("ref_name", String, primary_key=True),
    Column("commit_hash", String(64), nullable=False),
    Column("ref_type", String(20), nullable=False),
    Column("active", Boolean, nullable=False, default=True),
    Column("observed_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

persons = Table(
    "persons",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("repository_id", String(36), ForeignKey("repositories.id"), nullable=False),
    Column("canonical_name", String, nullable=False),
    Column("canonical_email", String, nullable=False),
    Column("kind", String(20), nullable=False, default="HUMAN"),
    Column("confirmed", Boolean, nullable=False, default=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("repository_id", "canonical_email", name="uq_person_repository_email"),
)

identity_aliases = Table(
    "identity_aliases",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("repository_id", String(36), ForeignKey("repositories.id"), nullable=False),
    Column("person_id", String(36), ForeignKey("persons.id"), nullable=False),
    Column("name", String, nullable=False),
    Column("email", String, nullable=False),
    Column("normalized_email", String, nullable=False),
    Column("source", String(20), nullable=False),
    Column("confidence", Float, nullable=False),
    Column("confirmed", Boolean, nullable=False, default=False),
    Column("rationale", Text, nullable=True),
    UniqueConstraint("repository_id", "name", "email", name="uq_alias_repository_identity"),
)

commits = Table(
    "commits",
    metadata,
    Column("repository_id", String(36), ForeignKey("repositories.id"), primary_key=True),
    Column("hash", String(64), primary_key=True),
    Column("author_alias_id", String(36), ForeignKey("identity_aliases.id"), nullable=False),
    Column("committer_name", String, nullable=False),
    Column("committer_email", String, nullable=False),
    Column("authored_at", DateTime(timezone=True), nullable=False),
    Column("committed_at", DateTime(timezone=True), nullable=False),
    Column("subject", Text, nullable=False),
    Column("body", Text, nullable=False),
    Column("is_merge", Boolean, nullable=False),
    Column("tree_hash", String(64), nullable=False),
    Column("patch_id", String(64), nullable=True),
    Column("reverts_hash", String(64), nullable=True),
    Column("insertions", Integer, nullable=False),
    Column("deletions", Integer, nullable=False),
    Column("files_changed", Integer, nullable=False),
    Column("indexed_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

commit_parents = Table(
    "commit_parents",
    metadata,
    Column("repository_id", String(36), nullable=False, primary_key=True),
    Column("commit_hash", String(64), nullable=False, primary_key=True),
    Column("parent_index", Integer, nullable=False, primary_key=True),
    Column("parent_hash", String(64), nullable=False),
)

file_changes = Table(
    "file_changes",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("repository_id", String(36), nullable=False),
    Column("commit_hash", String(64), nullable=False),
    Column("old_path", Text, nullable=True),
    Column("new_path", Text, nullable=True),
    Column("change_type", String(20), nullable=False),
    Column("is_binary", Boolean, nullable=False),
    Column("is_excluded", Boolean, nullable=False, default=False),
    Column("insertions", Integer, nullable=False),
    Column("deletions", Integer, nullable=False),
)

commit_delivery = Table(
    "commit_delivery",
    metadata,
    Column("repository_id", String(36), nullable=False, primary_key=True),
    Column("commit_hash", String(64), nullable=False, primary_key=True),
    Column("target_ref", String, nullable=False, primary_key=True),
    Column("status", String(20), nullable=False),
    Column("release_ref", String, nullable=True),
    Column("related_commit_hash", String(64), nullable=True),
    Column("evaluated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
