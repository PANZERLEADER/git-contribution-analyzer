"""Create the phase-one workspace schema."""

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "repositories",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("root_path", sa.String(), nullable=False, unique=True),
        sa.Column("git_dir", sa.String(), nullable=False),
        sa.Column("default_branch", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("repository_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("schema_version", sa.String(length=20), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
    )


def downgrade() -> None:
    op.drop_table("analysis_runs")
    op.drop_table("repositories")
