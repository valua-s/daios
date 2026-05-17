"""schema hardening: rename tasks.date, composite index, check/unique constraints

Revision ID: 7
Revises: 6
Create Date: 2026-05-16
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "7"
down_revision = "6"
branch_labels = None
depends_on = None


_TASK_SOURCES = ("telegram", "web", "backlog")
_EVENT_NAMES = (
    "morning_brief",
    "evening_summary",
    "collect_content",
    "sync_workouts",
    "evening_brief",
    "midnight_backlog",
    "tasks_reminder",
)


def _quoted_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def _has_column(insp: sa.engine.reflection.Inspector, table: str, column: str) -> bool:
    return any(c["name"] == column for c in insp.get_columns(table))


def _has_constraint(bind, name: str) -> bool:
    return bool(
        bind.execute(
            sa.text("SELECT 1 FROM pg_constraint WHERE conname = :n"),
            {"n": name},
        ).scalar()
    )


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # tasks.date → tasks.scheduled_date (idempotent)
    if _has_column(insp, "tasks", "date") and not _has_column(insp, "tasks", "scheduled_date"):
        op.alter_column("tasks", "date", new_column_name="scheduled_date")

    op.drop_index("ix_tasks_date", table_name="tasks", if_exists=True)
    op.create_index(
        "ix_tasks_scheduled_date",
        "tasks",
        ["scheduled_date"],
        unique=False,
        if_not_exists=True,
    )
    # composite index for the hot "today + status" query
    op.create_index(
        "ix_tasks_scheduled_date_status",
        "tasks",
        ["scheduled_date", "status"],
        unique=False,
        if_not_exists=True,
    )
    # tasks.source CHECK constraint (kept as Text, no native PG enum)
    if not _has_constraint(bind, "ck_tasks_source"):
        op.create_check_constraint(
            "ck_tasks_source",
            "tasks",
            f"source IS NULL OR source IN ({_quoted_list(_TASK_SOURCES)})",
        )

    # focus: only one row per (period, period_key)
    if not _has_constraint(bind, "uq_focus_period_period_key"):
        op.create_unique_constraint(
            "uq_focus_period_period_key",
            "focus",
            ["period", "period_key"],
        )

    # note_items: stable sort_order within a note
    if not _has_constraint(bind, "uq_note_items_note_id_sort_order"):
        op.create_unique_constraint(
            "uq_note_items_note_id_sort_order",
            "note_items",
            ["note_id", "sort_order"],
        )

    # schedules.event_name CHECK constraint
    if not _has_constraint(bind, "ck_schedules_event_name"):
        op.create_check_constraint(
            "ck_schedules_event_name",
            "schedules",
            f"event_name IN ({_quoted_list(_EVENT_NAMES)})",
        )


def downgrade() -> None:
    op.drop_constraint("ck_schedules_event_name", "schedules", type_="check")
    op.drop_constraint("uq_note_items_note_id_sort_order", "note_items", type_="unique")
    op.drop_constraint("uq_focus_period_period_key", "focus", type_="unique")
    op.drop_constraint("ck_tasks_source", "tasks", type_="check")
    op.drop_index("ix_tasks_scheduled_date_status", table_name="tasks")
    op.drop_index("ix_tasks_scheduled_date", table_name="tasks")
    op.create_index("ix_tasks_date", "tasks", ["scheduled_date"], unique=False)
    op.alter_column("tasks", "scheduled_date", new_column_name="date")
