"""add action-signal detail columns to aso_readiness

Exposes the individual action signals (agent-usable forms, OpenAPI links,
and the total action_signals count) that already feed the `agent_ready`
computation in `scoring/readiness.py`, so the UI can show why a site does
or doesn't reach the Ready threshold instead of just the final boolean.

Revision ID: b1c2d3e4f5a6
Revises: a7b8c9d0e1f2
Create Date: 2026-07-01 10:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b1c2d3e4f5a6"
down_revision: str | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "aso_readiness",
        sa.Column("has_agent_forms", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "aso_readiness",
        sa.Column("has_openapi", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "aso_readiness",
        sa.Column("action_signals", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("aso_readiness", "action_signals")
    op.drop_column("aso_readiness", "has_openapi")
    op.drop_column("aso_readiness", "has_agent_forms")
