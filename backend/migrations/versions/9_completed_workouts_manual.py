"""completed_workouts: переход на ручной ввод (без Strava)

Revision ID: 9
Revises: 8
Create Date: 2026-05-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "9"
down_revision = "8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Старые записи привязаны к Strava и теряют смысл без оригинального источника.
    op.execute("TRUNCATE TABLE completed_workouts")

    op.drop_index("ix_completed_workouts_strava_activity_id", table_name="completed_workouts", if_exists=True)
    op.drop_constraint("uq_completed_workouts_strava_activity_id", "completed_workouts", type_="unique", if_exists=True)
    op.drop_column("completed_workouts", "strava_activity_id")
    op.drop_column("completed_workouts", "distance_km_override")
    op.drop_column("completed_workouts", "started_at")
    op.drop_column("completed_workouts", "raw_json")
    op.drop_column("completed_workouts", "fetched_at")

    op.add_column(
        "completed_workouts",
        sa.Column("note", sa.Text(), nullable=True),
    )
    op.alter_column(
        "completed_workouts",
        "activity_type",
        existing_type=sa.Text(),
        server_default=sa.text("'running'"),
    )
    op.create_unique_constraint(
        "uq_completed_workouts_workout_date",
        "completed_workouts",
        ["workout_date"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_completed_workouts_workout_date", "completed_workouts", type_="unique")
    op.alter_column(
        "completed_workouts",
        "activity_type",
        existing_type=sa.Text(),
        server_default=None,
    )
    op.drop_column("completed_workouts", "note")

    op.add_column("completed_workouts", sa.Column("fetched_at", sa.DateTime(), nullable=True))
    op.add_column(
        "completed_workouts",
        sa.Column("raw_json", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("completed_workouts", sa.Column("started_at", sa.DateTime(), nullable=True))
    op.add_column("completed_workouts", sa.Column("distance_km_override", sa.Float(), nullable=True))
    op.add_column("completed_workouts", sa.Column("strava_activity_id", sa.BigInteger(), nullable=True))
    op.create_unique_constraint(
        "uq_completed_workouts_strava_activity_id",
        "completed_workouts",
        ["strava_activity_id"],
    )
    op.create_index(
        "ix_completed_workouts_strava_activity_id",
        "completed_workouts",
        ["strava_activity_id"],
        unique=True,
    )
