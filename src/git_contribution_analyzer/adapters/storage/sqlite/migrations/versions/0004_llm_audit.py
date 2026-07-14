"""Add LLM invocation audit and response cache."""

import sqlalchemy as sa
from alembic import op

revision = "0004_llm_audit"
down_revision = "0003_analysis"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_cache",
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("provider_id", sa.String(length=40), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("prompt_version", sa.String(length=40), nullable=False),
        sa.Column("schema_version", sa.String(length=40), nullable=False),
        sa.Column("response_json", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "last_used_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("request_hash"),
    )
    op.create_table(
        "llm_invocations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=True),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("provider_id", sa.String(length=40), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("prompt_version", sa.String(length=40), nullable=False),
        sa.Column("schema_version", sa.String(length=40), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_code", sa.String(length=40), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("cache_hit", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["run_id"], ["analysis_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_llm_invocations_request_hash", "llm_invocations", ["request_hash"]
    )
    op.create_index("ix_llm_invocations_run_id", "llm_invocations", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_llm_invocations_run_id", table_name="llm_invocations")
    op.drop_index("ix_llm_invocations_request_hash", table_name="llm_invocations")
    op.drop_table("llm_invocations")
    op.drop_table("llm_cache")
