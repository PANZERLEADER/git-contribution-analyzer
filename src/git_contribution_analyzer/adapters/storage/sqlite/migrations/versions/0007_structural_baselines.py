"""Add versioned structural facts and baseline caches."""

import sqlalchemy as sa
from alembic import op

revision = "0007_structural_baselines"
down_revision = "0006_identity_merges"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "structural_commit_facts",
        sa.Column("repository_id", sa.String(length=36), nullable=False),
        sa.Column("commit_hash", sa.String(length=64), nullable=False),
        sa.Column("fact_rule_version", sa.String(length=40), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("path_count", sa.Integer(), nullable=False),
        sa.Column("edge_count", sa.Integer(), nullable=False),
        sa.Column("context_capped", sa.Boolean(), nullable=False),
        sa.Column("excluded_reason", sa.String(length=40), nullable=True),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
        sa.PrimaryKeyConstraint("repository_id", "commit_hash", "fact_rule_version"),
    )
    op.create_table(
        "structural_file_occurrences",
        sa.Column("repository_id", sa.String(length=36), nullable=False),
        sa.Column("commit_hash", sa.String(length=64), nullable=False),
        sa.Column("fact_rule_version", sa.String(length=40), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["repository_id", "commit_hash", "fact_rule_version"],
            [
                "structural_commit_facts.repository_id",
                "structural_commit_facts.commit_hash",
                "structural_commit_facts.fact_rule_version",
            ],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("repository_id", "commit_hash", "fact_rule_version", "path"),
    )
    op.create_index(
        "ix_structural_file_occurrences_path",
        "structural_file_occurrences",
        ["repository_id", "fact_rule_version", "path"],
    )
    op.create_table(
        "structural_edge_occurrences",
        sa.Column("repository_id", sa.String(length=36), nullable=False),
        sa.Column("commit_hash", sa.String(length=64), nullable=False),
        sa.Column("fact_rule_version", sa.String(length=40), nullable=False),
        sa.Column("left_path", sa.Text(), nullable=False),
        sa.Column("right_path", sa.Text(), nullable=False),
        sa.CheckConstraint("left_path < right_path", name="ck_structural_edge_order"),
        sa.ForeignKeyConstraint(
            ["repository_id", "commit_hash", "fact_rule_version"],
            [
                "structural_commit_facts.repository_id",
                "structural_commit_facts.commit_hash",
                "structural_commit_facts.fact_rule_version",
            ],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "repository_id",
            "commit_hash",
            "fact_rule_version",
            "left_path",
            "right_path",
        ),
    )
    op.create_index(
        "ix_structural_edge_occurrences_paths",
        "structural_edge_occurrences",
        ["repository_id", "fact_rule_version", "left_path", "right_path"],
    )
    op.create_table(
        "structural_baselines",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("repository_id", sa.String(length=36), nullable=False),
        sa.Column("baseline_commit", sa.String(length=64), nullable=True),
        sa.Column("cutoff_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("branch", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("filter_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("time_strategy", sa.String(length=24), nullable=False),
        sa.Column("fact_rule_version", sa.String(length=40), nullable=False),
        sa.Column("metric_rule_version", sa.String(length=40), nullable=False),
        sa.Column("threshold_version", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("eligible_commit_count", sa.Integer(), nullable=False),
        sa.Column("eligible_file_count", sa.Integer(), nullable=False),
        sa.Column("raw_edge_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
    )
    op.create_index(
        "ix_structural_baselines_repository_status",
        "structural_baselines",
        ["repository_id", "status", "cutoff_at"],
    )
    op.create_table(
        "structural_file_counts",
        sa.Column("baseline_id", sa.String(length=64), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("change_count", sa.Integer(), nullable=False),
        sa.Column("recent_change_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["baseline_id"], ["structural_baselines.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("baseline_id", "path"),
    )
    op.create_table(
        "structural_edge_counts",
        sa.Column("baseline_id", sa.String(length=64), nullable=False),
        sa.Column("left_path", sa.Text(), nullable=False),
        sa.Column("right_path", sa.Text(), nullable=False),
        sa.Column("co_change_count", sa.Integer(), nullable=False),
        sa.Column("recent_co_change_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["baseline_id"], ["structural_baselines.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("baseline_id", "left_path", "right_path"),
    )
    op.create_table(
        "structural_materializations",
        sa.Column("baseline_id", sa.String(length=64), nullable=False),
        sa.Column("metric_rule_version", sa.String(length=40), nullable=False),
        sa.Column("threshold_version", sa.String(length=40), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["baseline_id"], ["structural_baselines.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("baseline_id", "metric_rule_version", "threshold_version"),
    )


def downgrade() -> None:
    op.drop_table("structural_materializations")
    op.drop_table("structural_edge_counts")
    op.drop_table("structural_file_counts")
    op.drop_index("ix_structural_baselines_repository_status", table_name="structural_baselines")
    op.drop_table("structural_baselines")
    op.drop_index(
        "ix_structural_edge_occurrences_paths", table_name="structural_edge_occurrences"
    )
    op.drop_table("structural_edge_occurrences")
    op.drop_index(
        "ix_structural_file_occurrences_path", table_name="structural_file_occurrences"
    )
    op.drop_table("structural_file_occurrences")
    op.drop_table("structural_commit_facts")
