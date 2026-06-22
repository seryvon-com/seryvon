"""add prompt_set column to audit table (M4b — citation prompt set)

Revision ID: c3d4e5f6a7b8
Revises: e5f6a7b8c9d0
Create Date: 2026-06-22 00:00:00.000000

Hand-written: adds the `prompt_set` JSONB column to `audit` to persist the
deterministic citation prompt set generated from the crawl signals (document 08).
Nullable: audits run before this migration will have NULL (prompt set unavailable).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("audit", sa.Column("prompt_set", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("audit", "prompt_set")
