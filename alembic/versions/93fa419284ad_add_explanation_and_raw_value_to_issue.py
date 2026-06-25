"""add explanation and raw_value to issue

Revision ID: 93fa419284ad
Revises: c3d4e5f6a7b8
Create Date: 2026-06-24 14:18:52.177567
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "93fa419284ad"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("issue", sa.Column("explanation", sa.Text(), nullable=False, server_default=""))
    op.add_column("issue", sa.Column("raw_value", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("issue", "raw_value")
    op.drop_column("issue", "explanation")
