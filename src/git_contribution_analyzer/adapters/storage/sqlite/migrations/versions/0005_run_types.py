"""Add explicit analysis run types and lineage."""

import sqlalchemy as sa
from alembic import op

revision = "0005_run_types"
down_revision = "0004_llm_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "analysis_runs",
        sa.Column(
            "run_type",
            sa.String(length=32),
            server_default="ANALYSIS",
            nullable=False,
        ),
    )
    op.add_column(
        "analysis_runs",
        sa.Column("parent_run_id", sa.String(length=36), nullable=True),
    )
    op.create_index(
        "ix_analysis_runs_run_type",
        "analysis_runs",
        ["repository_id", "run_type", "started_at"],
    )
    op.create_index(
        "ix_analysis_runs_parent_run_id",
        "analysis_runs",
        ["parent_run_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_analysis_runs_parent_run_id", table_name="analysis_runs")
    op.drop_index("ix_analysis_runs_run_type", table_name="analysis_runs")
    op.drop_column("analysis_runs", "parent_run_id")
    op.drop_column("analysis_runs", "run_type")
