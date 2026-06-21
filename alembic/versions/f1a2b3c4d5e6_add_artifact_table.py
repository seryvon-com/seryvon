"""add artifact table (C-P2 object store)

Revision ID: f1a2b3c4d5e6
Revises: d8ddd3948ee0
Create Date: 2026-06-21 00:00:00.000000

Hand-written (no live DB for autogenerate): adds the `artifact` table holding the
object-store metadata for raw collection artifacts (document 05, §4). The bytes
live in MinIO/S3; this table is the queryable handle.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "d8ddd3948ee0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "artifact",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("audit_id", sa.UUID(), nullable=True),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("bucket", sa.String(length=255), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("compression", sa.String(length=8), nullable=False),
        sa.Column("encryption", sa.Boolean(), nullable=False),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["audit_id"], ["audit.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bucket", "object_key", name="uq_artifact_object"),
    )
    op.create_index(op.f("ix_artifact_audit_id"), "artifact", ["audit_id"], unique=False)
    op.create_index(op.f("ix_artifact_sha256"), "artifact", ["sha256"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_artifact_sha256"), table_name="artifact")
    op.drop_index(op.f("ix_artifact_audit_id"), table_name="artifact")
    op.drop_table("artifact")
