"""Add reversible identity merge state."""

import sqlalchemy as sa
from alembic import op

revision = "0006_identity_merges"
down_revision = "0005_run_types"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "persons",
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.add_column(
        "persons",
        sa.Column("merged_into_person_id", sa.String(length=36), nullable=True),
    )
    op.create_index(
        "ix_persons_active_identity",
        "persons",
        ["repository_id", "active", "canonical_name", "canonical_email"],
    )
    op.create_index(
        "ix_persons_merged_into_person_id",
        "persons",
        ["merged_into_person_id"],
    )
    op.create_table(
        "identity_merge_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "repository_id",
            sa.String(length=36),
            sa.ForeignKey("repositories.id"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=20), nullable=False),
        sa.Column(
            "target_person_id",
            sa.String(length=36),
            sa.ForeignKey("persons.id"),
            nullable=False,
        ),
        sa.Column("source_person_ids_json", sa.Text(), nullable=False),
        sa.Column("moved_alias_ids_json", sa.Text(), nullable=False),
        sa.Column("source_snapshots_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("reverted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_identity_merge_events_status",
        "identity_merge_events",
        ["repository_id", "status", "created_at"],
    )
    op.create_index(
        "ix_identity_merge_events_target",
        "identity_merge_events",
        ["repository_id", "target_person_id"],
    )


def downgrade() -> None:
    active = op.get_bind().execute(
        sa.text("SELECT COUNT(*) FROM identity_merge_events WHERE status = 'ACTIVE'")
    ).scalar_one()
    if active:
        raise RuntimeError("Cannot downgrade while ACTIVE identity merge events exist")
    op.drop_index("ix_identity_merge_events_target", table_name="identity_merge_events")
    op.drop_index("ix_identity_merge_events_status", table_name="identity_merge_events")
    op.drop_table("identity_merge_events")
    op.drop_index("ix_persons_merged_into_person_id", table_name="persons")
    op.drop_index("ix_persons_active_identity", table_name="persons")
    op.drop_column("persons", "merged_into_person_id")
    op.drop_column("persons", "active")
