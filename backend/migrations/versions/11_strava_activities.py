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

_TABLE = "completed_workouts"


def _quoted_list(names: tuple[str, ...]) -> str:
    return ", ".join(f"'{n}'" for n in names)


def _has_column(insp: sa.engine.reflection.Inspector, table: str, column: str) -> bool:
    return any(c["name"] == column for c in insp.get_columns(table))


def _has_index(insp: sa.engine.reflection.Inspector, table: str, name: str) -> bool:
    return any(i["name"] == name for i in insp.get_indexes(table))


# naming_convention добавляет префикс "ck_schedules_" к переданному имени,
# поэтому в БД констрейнт мог осесть под удвоенным именем.
_EVENT_NAME_CHECKS = (
    "ck_schedules_event_name",
    "ck_schedules_ck_schedules_event_name",
)


def _reset_event_name_check(names: tuple[str, ...]) -> None:
    for constraint in _EVENT_NAME_CHECKS:
        op.execute(f'ALTER TABLE schedules DROP CONSTRAINT IF EXISTS "{constraint}"')
    op.execute(
        "ALTER TABLE schedules ADD CONSTRAINT ck_schedules_event_name "
        f"CHECK (event_name IN ({_quoted_list(names)}))"
    )


def _has_constraint(bind: sa.Connection, name: str) -> bool:
    return bool(
        bind.execute(
            sa.text("SELECT 1 FROM pg_constraint WHERE conname = :n"),
            {"n": name},
        ).scalar()
    )


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not _has_column(insp, _TABLE, "source"):
        op.add_column(
            _TABLE,
            sa.Column("source", sa.Text(), nullable=False, server_default=sa.text("'manual'")),
        )
    if not _has_column(insp, _TABLE, "strava_activity_id"):
        op.add_column(_TABLE, sa.Column("strava_activity_id", sa.BigInteger(), nullable=True))
    if not _has_column(insp, _TABLE, "started_at"):
        op.add_column(_TABLE, sa.Column("started_at", sa.DateTime(), nullable=True))

    insp = sa.inspect(bind)

    # День перестаёт быть уникальным: тренировок за день может быть несколько.
    if _has_constraint(bind, "uq_completed_workouts_workout_date"):
        op.drop_constraint("uq_completed_workouts_workout_date", _TABLE, type_="unique")

    if not _has_index(insp, _TABLE, "ix_completed_workouts_workout_date"):
        op.create_index("ix_completed_workouts_workout_date", _TABLE, ["workout_date"])

    if not _has_index(insp, _TABLE, "ix_completed_workouts_strava_activity_id"):
        op.create_index(
            "ix_completed_workouts_strava_activity_id",
            _TABLE,
            ["strava_activity_id"],
            unique=True,
        )

    # Ручная отметка остаётся одна на день — на неё опирается upsert из UI.
    if not _has_index(insp, _TABLE, "uq_completed_workouts_manual_date"):
        op.create_index(
            "uq_completed_workouts_manual_date",
            _TABLE,
            ["workout_date"],
            unique=True,
            postgresql_where=sa.text("source = 'manual'"),
        )

    _reset_event_name_check(_EVENT_NAMES_NEW)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    op.execute("DELETE FROM schedules WHERE event_name = 'sync_strava'")
    _reset_event_name_check(_EVENT_NAMES_OLD)

    op.execute("DELETE FROM completed_workouts WHERE source = 'strava'")
    op.execute(
        "DELETE FROM completed_workouts a USING completed_workouts b "
        "WHERE a.workout_date = b.workout_date AND a.id > b.id"
    )

    for index_name in (
        "uq_completed_workouts_manual_date",
        "ix_completed_workouts_strava_activity_id",
        "ix_completed_workouts_workout_date",
    ):
        if _has_index(insp, _TABLE, index_name):
            op.drop_index(index_name, table_name=_TABLE)

    if not _has_constraint(bind, "uq_completed_workouts_workout_date"):
        op.create_unique_constraint("uq_completed_workouts_workout_date", _TABLE, ["workout_date"])

    for column in ("started_at", "strava_activity_id", "source"):
        if _has_column(insp, _TABLE, column):
            op.drop_column(_TABLE, column)
