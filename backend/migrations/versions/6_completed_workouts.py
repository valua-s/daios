"""completed_workouts (Strava)

Revision ID: 6
Revises: 5
Create Date: 2026-05-15
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "6"
down_revision = "5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "completed_workouts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("strava_activity_id", sa.BigInteger(), nullable=False),
        sa.Column("workout_date", sa.Date(), nullable=False),
        sa.Column("activity_type", sa.Text(), nullable=False),
        sa.Column("distance_km", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("distance_km_override", sa.Float(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("strava_activity_id"),
    )
    op.create_index(
        op.f("ix_completed_workouts_strava_activity_id"),
        "completed_workouts",
        ["strava_activity_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_completed_workouts_workout_date"),
        "completed_workouts",
        ["workout_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_completed_workouts_workout_date"), table_name="completed_workouts")
    op.drop_index(op.f("ix_completed_workouts_strava_activity_id"), table_name="completed_workouts")
    op.drop_table("completed_workouts")
