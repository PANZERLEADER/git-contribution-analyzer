from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
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
    Column("active", Boolean, nullable=False, default=True),
    Column("merged_into_person_id", String(36), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("repository_id", "canonical_email", name="uq_person_repository_email"),
)

identity_merge_events = Table(
    "identity_merge_events",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("repository_id", String(36), ForeignKey("repositories.id"), nullable=False),
    Column("event_type", String(20), nullable=False),
    Column("target_person_id", String(36), ForeignKey("persons.id"), nullable=False),
    Column("source_person_ids_json", Text, nullable=False),
    Column("moved_alias_ids_json", Text, nullable=False),
    Column("source_snapshots_json", Text, nullable=False),
    Column("status", String(20), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("reverted_at", DateTime(timezone=True), nullable=True),
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

structural_commit_facts = Table(
    "structural_commit_facts",
    metadata,
    Column("repository_id", String(36), ForeignKey("repositories.id"), primary_key=True),
    Column("commit_hash", String(64), primary_key=True),
    Column("fact_rule_version", String(40), primary_key=True),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    Column("path_count", Integer, nullable=False),
    Column("edge_count", Integer, nullable=False),
    Column("context_capped", Boolean, nullable=False),
    Column("excluded_reason", String(40), nullable=True),
    Column("processed_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

structural_file_occurrences = Table(
    "structural_file_occurrences",
    metadata,
    Column("repository_id", String(36), nullable=False, primary_key=True),
    Column("commit_hash", String(64), nullable=False, primary_key=True),
    Column("fact_rule_version", String(40), nullable=False, primary_key=True),
    Column("path", Text, nullable=False, primary_key=True),
    ForeignKeyConstraint(
        ["repository_id", "commit_hash", "fact_rule_version"],
        [
            "structural_commit_facts.repository_id",
            "structural_commit_facts.commit_hash",
            "structural_commit_facts.fact_rule_version",
        ],
        ondelete="CASCADE",
    ),
)

structural_edge_occurrences = Table(
    "structural_edge_occurrences",
    metadata,
    Column("repository_id", String(36), nullable=False, primary_key=True),
    Column("commit_hash", String(64), nullable=False, primary_key=True),
    Column("fact_rule_version", String(40), nullable=False, primary_key=True),
    Column("left_path", Text, nullable=False, primary_key=True),
    Column("right_path", Text, nullable=False, primary_key=True),
    CheckConstraint("left_path < right_path", name="ck_structural_edge_order"),
    ForeignKeyConstraint(
        ["repository_id", "commit_hash", "fact_rule_version"],
        [
            "structural_commit_facts.repository_id",
            "structural_commit_facts.commit_hash",
            "structural_commit_facts.fact_rule_version",
        ],
        ondelete="CASCADE",
    ),
)

structural_baselines = Table(
    "structural_baselines",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("repository_id", String(36), ForeignKey("repositories.id"), nullable=False),
    Column("baseline_commit", String(64), nullable=True),
    Column("cutoff_at", DateTime(timezone=True), nullable=False),
    Column("branch", Text, nullable=False),
    Column("scope", Text, nullable=True),
    Column("filter_fingerprint", String(64), nullable=False),
    Column("time_strategy", String(24), nullable=False),
    Column("fact_rule_version", String(40), nullable=False),
    Column("metric_rule_version", String(40), nullable=False),
    Column("threshold_version", String(40), nullable=False),
    Column("status", String(20), nullable=False),
    Column("eligible_commit_count", Integer, nullable=False, default=0),
    Column("eligible_file_count", Integer, nullable=False, default=0),
    Column("raw_edge_count", Integer, nullable=False, default=0),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("completed_at", DateTime(timezone=True), nullable=True),
    Column("error_message", Text, nullable=True),
)

structural_file_counts = Table(
    "structural_file_counts",
    metadata,
    Column(
        "baseline_id",
        String(64),
        ForeignKey("structural_baselines.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("path", Text, primary_key=True),
    Column("change_count", Integer, nullable=False),
    Column("recent_change_count", Integer, nullable=False),
)

structural_edge_counts = Table(
    "structural_edge_counts",
    metadata,
    Column(
        "baseline_id",
        String(64),
        ForeignKey("structural_baselines.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("left_path", Text, primary_key=True),
    Column("right_path", Text, primary_key=True),
    Column("co_change_count", Integer, nullable=False),
    Column("recent_co_change_count", Integer, nullable=False),
)

structural_materializations = Table(
    "structural_materializations",
    metadata,
    Column(
        "baseline_id",
        String(64),
        ForeignKey("structural_baselines.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("metric_rule_version", String(40), primary_key=True),
    Column("threshold_version", String(40), primary_key=True),
    Column("content_hash", String(64), nullable=False),
    Column("result_json", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
