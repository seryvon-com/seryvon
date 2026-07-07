"""widen issue.priority_bucket to fit 3-level tokens

The action plan buckets moved from `P1..P4` to `high` / `medium` / `low`
(scoring/issues.py). `medium` is 6 chars, but the column was VARCHAR(4)
sized for the legacy codes, causing StringDataRightTruncation on persist.

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-07-03 12:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c2d3e4f5a6b7"
down_revision: str | None = "b1c2d3e4f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "issue",
        "priority_bucket",
        existing_type=sa.String(length=4),
        type_=sa.String(length=16),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "issue",
        "priority_bucket",
        existing_type=sa.String(length=16),
        type_=sa.String(length=4),
        existing_nullable=False,
    )
