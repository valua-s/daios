"""completed_workouts: несколько активностей в день + источник Strava

Revision ID: 11
Revises: 10
Create Date: 2026-08-01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "11"
down_revision = "10"
branch_labels = None
depends_on = None

_EVENT_NAMES_OLD = (
    "morning_brief",
    "evening_summary",
    "collect_content",
    "sync_workouts",
    "evening_brief",
    "midnight_backlog",
    "tasks_reminder",
)
_EVENT_NAMES_NEW = (*_EVENT_NAMES_OLD, "sync_strava")


def _quoted_list(names: tuple[str, ...]) -> str:
    return ", ".join(f"'{n}'" for n in names)


def upgrade() -> None:
    op.add_column(
        "completed_workouts",
        sa.Column("source", sa.Text(), nullable=False, server_default=sa.text("'manual'")),
    )
    op.add_column(
        "completed_workouts",
        sa.Column("strava_activity_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "completed_workouts",
        sa.Column("started_at", sa.DateTime(), nullable=True),
    )

    # День перестаёт быть уникальным: тренировок за день может быть несколько.
    op.drop_constraint("uq_completed_workouts_workout_date", "completed_workouts", type_="unique")
    op.create_index(
        "ix_completed_workouts_workout_date",
        "completed_workouts",
        ["workout_date"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_completed_workouts_strava_activity_id",
        "completed_workouts",
        ["strava_activity_id"],
        unique=True,
    )
    # Ручная отметка остаётся одна на день — на неё опирается upsert из UI.
    op.create_index(
        "uq_completed_workouts_manual_date",
        "completed_workouts",
        ["workout_date"],
        unique=True,
        postgresql_where=sa.text("source = 'manual'"),
    )

    op.drop_constraint("ck_schedules_event_name", "schedules", type_="check")
    op.create_check_constraint(
        "ck_schedules_event_name",
        "schedules",
        f"event_name IN ({_quoted_list(_EVENT_NAMES_NEW)})",
    )


def downgrade() -> None:
    op.execute("DELETE FROM schedules WHERE event_name = 'sync_strava'")
    op.drop_constraint("ck_schedules_event_name", "schedules", type_="check")
    op.create_check_constraint(
        "ck_schedules_event_name",
        "schedules",
        f"event_name IN ({_quoted_list(_EVENT_NAMES_OLD)})",
    )

    op.execute("DELETE FROM completed_workouts WHERE source = 'strava'")

    op.drop_index("uq_completed_workouts_manual_date", table_name="completed_workouts")
    op.drop_index("ix_completed_workouts_strava_activity_id", table_name="completed_workouts")
    op.drop_index("ix_completed_workouts_workout_date", table_name="completed_workouts", if_exists=True)
    op.create_unique_constraint(
        "uq_completed_workouts_workout_date", "completed_workouts", ["workout_date"],
    )

    op.drop_column("completed_workouts", "started_at")
    op.drop_column("completed_workouts", "strava_activity_id")
    op.drop_column("completed_workouts", "source")
