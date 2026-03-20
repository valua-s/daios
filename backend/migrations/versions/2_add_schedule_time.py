"""add scheduled_time to tasks

Revision ID: 2
Revises: 1
Create Date: 2026-03-16
"""
from alembic import op
import sqlalchemy as sa

revision = "2"
down_revision = "1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("scheduled_time", sa.Time(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tasks", "scheduled_time")