"""convert issue.raw_value from Text to JSONB

The issue's `raw_value` mirrors `criterion_result.raw_value` (a JSON-serializable
value that is frequently a dict). It was created as Text, which makes psycopg
raise "cannot adapt type 'dict'" whenever a triggering criterion carries a dict
raw_value. Convert to JSONB to match the model.

Revision ID: a7b8c9d0e1f2
Revises: 93fa419284ad
Create Date: 2026-06-26 09:30:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "93fa419284ad"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Order matters: drop the "" default and the NOT NULL constraint BEFORE the
    # type cast, because the USING clause maps empty/legacy text to NULL — which
    # would violate the still-present NOT NULL if done in the wrong order.
    op.execute("ALTER TABLE issue ALTER COLUMN raw_value DROP DEFAULT")
    op.execute("ALTER TABLE issue ALTER COLUMN raw_value DROP NOT NULL")
    op.execute(
        "ALTER TABLE issue ALTER COLUMN raw_value TYPE JSONB "
        "USING (CASE WHEN raw_value IS NULL OR raw_value = '' "
        "THEN NULL ELSE to_jsonb(raw_value) END)"
    )


def downgrade() -> None:
    op.alter_column(
        "issue",
        "raw_value",
        existing_type=postgresql.JSONB(),
        type_=sa.Text(),
        existing_nullable=True,
        nullable=False,
        server_default="",
        postgresql_using="COALESCE(raw_value::text, '')",
    )
