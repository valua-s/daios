"""add cron_expr_weekend to schedules

Revision ID: 5
Revises: 4
Create Date: 2026-05-03
"""
from alembic import op
import sqlalchemy as sa

revision = "5"
down_revision = "4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("schedules")}
    if "cron_expr_weekend" not in cols:
        op.add_column(
            "schedules",
            sa.Column("cron_expr_weekend", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("schedules")}
    if "cron_expr_weekend" in cols:
        op.drop_column("schedules", "cron_expr_weekend")
