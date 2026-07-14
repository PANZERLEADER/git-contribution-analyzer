"""Add Git history, identity, and delivery index tables."""

import sqlalchemy as sa
from alembic import op

revision = "0002_git_index"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "refs",
        sa.Column("repository_id", sa.String(length=36), nullable=False),
        sa.Column("ref_name", sa.String(), nullable=False),
        sa.Column("commit_hash", sa.String(length=64), nullable=False),
        sa.Column("ref_type", sa.String(length=20), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "observed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
        sa.PrimaryKeyConstraint("repository_id", "ref_name"),
    )
    op.create_table(
        "persons",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("repository_id", sa.String(length=36), nullable=False),
        sa.Column("canonical_name", sa.String(), nullable=False),
        sa.Column("canonical_email", sa.String(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("confirmed", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
        sa.UniqueConstraint(
            "repository_id", "canonical_email", name="uq_person_repository_email"
        ),
    )
    op.create_table(
        "identity_aliases",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("repository_id", sa.String(length=36), nullable=False),
        sa.Column("person_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("normalized_email", sa.String(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("confirmed", sa.Boolean(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"]),
        sa.UniqueConstraint(
            "repository_id", "name", "email", name="uq_alias_repository_identity"
        ),
    )
    op.create_table(
        "commits",
        sa.Column("repository_id", sa.String(length=36), nullable=False),
        sa.Column("hash", sa.String(length=64), nullable=False),
        sa.Column("author_alias_id", sa.String(length=36), nullable=False),
        sa.Column("committer_name", sa.String(), nullable=False),
        sa.Column("committer_email", sa.String(), nullable=False),
        sa.Column("authored_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_merge", sa.Boolean(), nullable=False),
        sa.Column("tree_hash", sa.String(length=64), nullable=False),
        sa.Column("patch_id", sa.String(length=64), nullable=True),
        sa.Column("reverts_hash", sa.String(length=64), nullable=True),
        sa.Column("insertions", sa.Integer(), nullable=False),
        sa.Column("deletions", sa.Integer(), nullable=False),
        sa.Column("files_changed", sa.Integer(), nullable=False),
        sa.Column(
            "indexed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["author_alias_id"], ["identity_aliases.id"]),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
        sa.PrimaryKeyConstraint("repository_id", "hash"),
    )
    op.create_index("ix_commits_author_date", "commits", ["author_alias_id", "authored_at"])
    op.create_index("ix_commits_patch_id", "commits", ["patch_id"])
    op.create_table(
        "commit_parents",
        sa.Column("repository_id", sa.String(length=36), nullable=False),
        sa.Column("commit_hash", sa.String(length=64), nullable=False),
        sa.Column("parent_index", sa.Integer(), nullable=False),
        sa.Column("parent_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("repository_id", "commit_hash", "parent_index"),
    )
    op.create_table(
        "file_changes",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("repository_id", sa.String(length=36), nullable=False),
        sa.Column("commit_hash", sa.String(length=64), nullable=False),
        sa.Column("old_path", sa.Text(), nullable=True),
        sa.Column("new_path", sa.Text(), nullable=True),
        sa.Column("change_type", sa.String(length=20), nullable=False),
        sa.Column("is_binary", sa.Boolean(), nullable=False),
        sa.Column("is_excluded", sa.Boolean(), nullable=False),
        sa.Column("insertions", sa.Integer(), nullable=False),
        sa.Column("deletions", sa.Integer(), nullable=False),
    )
    op.create_index("ix_file_changes_commit", "file_changes", ["repository_id", "commit_hash"])
    op.create_table(
        "commit_delivery",
        sa.Column("repository_id", sa.String(length=36), nullable=False),
        sa.Column("commit_hash", sa.String(length=64), nullable=False),
        sa.Column("target_ref", sa.String(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("release_ref", sa.String(), nullable=True),
        sa.Column("related_commit_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "evaluated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("repository_id", "commit_hash", "target_ref"),
    )


def downgrade() -> None:
    op.drop_table("commit_delivery")
    op.drop_index("ix_file_changes_commit", table_name="file_changes")
    op.drop_table("file_changes")
    op.drop_table("commit_parents")
    op.drop_index("ix_commits_patch_id", table_name="commits")
    op.drop_index("ix_commits_author_date", table_name="commits")
    op.drop_table("commits")
    op.drop_table("identity_aliases")
    op.drop_table("persons")
    op.drop_table("refs")
