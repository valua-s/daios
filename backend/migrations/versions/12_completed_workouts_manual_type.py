"""completed_workouts: ручная отметка уникальна по дате и типу активности

Revision ID: 12
Revises: 11
Create Date: 2026-08-06
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "12"
down_revision = "11"
branch_labels = None
depends_on = None

_TABLE = "completed_workouts"
_OLD_INDEX = "uq_completed_workouts_manual_date"
_NEW_INDEX = "uq_completed_workouts_manual_date_type"


def _has_index(insp: sa.engine.reflection.Inspector, name: str) -> bool:
    return any(i["name"] == name for i in insp.get_indexes(_TABLE))


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())

    if _has_index(insp, _OLD_INDEX):
        op.drop_index(_OLD_INDEX, table_name=_TABLE)

    if not _has_index(insp, _NEW_INDEX):
        op.create_index(
            _NEW_INDEX,
            _TABLE,
            ["workout_date", "activity_type"],
            unique=True,
            postgresql_where=sa.text("source = 'manual'"),
        )


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())

    # Возврат к одной ручной записи в день: лишние типы за дату удаляются.
    op.execute(
        "DELETE FROM completed_workouts a USING completed_workouts b "
        "WHERE a.source = 'manual' AND b.source = 'manual' "
        "AND a.workout_date = b.workout_date AND a.id > b.id"
    )

    if _has_index(insp, _NEW_INDEX):
        op.drop_index(_NEW_INDEX, table_name=_TABLE)

    if not _has_index(insp, _OLD_INDEX):
        op.create_index(
            _OLD_INDEX,
            _TABLE,
            ["workout_date"],
            unique=True,
            postgresql_where=sa.text("source = 'manual'"),
        )
