"""drop content_items.minio_key — Minio removed from stack

Revision ID: 8
Revises: 7
Create Date: 2026-05-17
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "8"
down_revision = "7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("content_items", "minio_key")


def downgrade() -> None:
    op.add_column(
        "content_items",
        sa.Column("minio_key", sa.Text(), nullable=True),
    )
