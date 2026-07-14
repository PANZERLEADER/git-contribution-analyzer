"""Add deterministic analysis runs, evidence, and report persistence."""

import sqlalchemy as sa
from alembic import op

revision = "0003_analysis"
down_revision = "0002_git_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("analysis_runs", sa.Column("person_id", sa.String(length=36), nullable=True))
    op.add_column(
        "analysis_runs",
        sa.Column("parameters_json", sa.Text(), server_default="{}", nullable=False),
    )
    op.add_column(
        "analysis_runs", sa.Column("baseline_commit", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "analysis_runs",
        sa.Column("rule_version", sa.String(length=40), server_default="rules-v1", nullable=False),
    )
    op.add_column(
        "analysis_runs",
        sa.Column("provider_id", sa.String(length=40), server_default="none", nullable=False),
    )
    op.add_column("analysis_runs", sa.Column("result_json", sa.Text(), nullable=True))
    op.add_column("analysis_runs", sa.Column("error_message", sa.Text(), nullable=True))
    op.create_table(
        "contribution_items",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("item_id", sa.String(length=20), nullable=False),
        sa.Column("item_order", sa.Integer(), nullable=False),
        sa.Column("group_key", sa.String(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("confidence", sa.String(length=20), nullable=False),
        sa.Column("commits_json", sa.Text(), nullable=False),
        sa.Column("evidence_ids_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["analysis_runs.id"]),
        sa.PrimaryKeyConstraint("run_id", "item_id"),
    )
    op.create_table(
        "evidence",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("evidence_id", sa.String(length=20), nullable=False),
        sa.Column("evidence_type", sa.String(length=40), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("commit_hashes_json", sa.Text(), nullable=False),
        sa.Column("paths_json", sa.Text(), nullable=False),
        sa.Column("metrics_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["analysis_runs.id"]),
        sa.PrimaryKeyConstraint("run_id", "evidence_id"),
    )
    op.create_table(
        "capability_assessments",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("capability", sa.String(length=60), nullable=False),
        sa.Column("confidence", sa.String(length=20), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("evidence_ids_json", sa.Text(), nullable=False),
        sa.Column("gaps_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["analysis_runs.id"]),
        sa.PrimaryKeyConstraint("run_id", "capability"),
    )


def downgrade() -> None:
    op.drop_table("capability_assessments")
    op.drop_table("evidence")
    op.drop_table("contribution_items")
    op.drop_column("analysis_runs", "error_message")
    op.drop_column("analysis_runs", "result_json")
    op.drop_column("analysis_runs", "provider_id")
    op.drop_column("analysis_runs", "rule_version")
    op.drop_column("analysis_runs", "baseline_commit")
    op.drop_column("analysis_runs", "parameters_json")
    op.drop_column("analysis_runs", "person_id")
