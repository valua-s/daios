"""users table + seed admin

Revision ID: 3
Revises: 2
Create Date: 2026-05-02
"""
from __future__ import annotations

import bcrypt
import sqlalchemy as sa
from alembic import op

from backend.core.config import settings

revision = "3"
down_revision = "2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("hash_password", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    admin_password = settings.admin_password.get_secret_value()
    hashed = bcrypt.hashpw(admin_password.encode(), bcrypt.gensalt()).decode()

    users_table = sa.table(
        "users",
        sa.column("email", sa.String),
        sa.column("name", sa.String),
        sa.column("hash_password", sa.String),
    )
    op.execute(
        sa.insert(users_table)
        .values(email=settings.admin_email, name=settings.admin_name, hash_password=hashed)
        .prefix_with("")  # noqa: pretty-format
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
