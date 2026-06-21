"""persist coverage + measurement_profile on audit + pillar_score

Revision ID: b2c3d4e5f6a7
Revises: f1a2b3c4d5e6
Create Date: 2026-06-21 22:10:00.000000

Hand-written: the global `coverage`, per-pillar coverage/coverage_label/
not_applicable and the `measurement_profile` were computed but not persisted, so
reloaded reports lost them (coverage shown as 0, every pillar "insufficient", and
scorecard comparison via the API failing with 409 for lack of a profile). Adds
the columns with safe server defaults for existing rows.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "audit",
        sa.Column("coverage", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "audit",
        sa.Column(
            "measurement_profile", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )
    op.add_column(
        "pillar_score",
        sa.Column("not_applicable", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "pillar_score",
        sa.Column("coverage", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "pillar_score",
        sa.Column(
            "coverage_label",
            sa.String(length=16),
            nullable=False,
            server_default="insufficient",
        ),
    )


def downgrade() -> None:
    op.drop_column("pillar_score", "coverage_label")
    op.drop_column("pillar_score", "coverage")
    op.drop_column("pillar_score", "not_applicable")
    op.drop_column("audit", "measurement_profile")
    op.drop_column("audit", "coverage")
