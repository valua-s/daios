from __future__ import annotations

from sqlalchemy import delete as sa_delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.schedule import Schedule
from backend.models.settings import UserSetting


class UserSettingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all(self) -> dict[str, str]:
        result = await self._session.execute(select(UserSetting))
        return {row.key: row.value for row in result.scalars().all()}

    async def upsert(self, key: str, value: str) -> None:
        stmt = (
            insert(UserSetting)
            .values(key=key, value=value)
            .on_conflict_do_update(index_elements=["key"], set_={"value": value})
        )
        await self._session.execute(stmt)

    async def delete(self, key: str) -> None:
        await self._session.execute(sa_delete(UserSetting).where(UserSetting.key == key))


class ScheduleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all(self) -> list[Schedule]:
        result = await self._session.execute(select(Schedule))
        return list(result.scalars().all())

    async def get(self, event_name: str) -> Schedule | None:
        result = await self._session.execute(
            select(Schedule).where(Schedule.event_name == event_name)
        )
        return result.scalars().first()

    async def upsert(self, event_name: str, cron_expr: str, enabled: bool, description: str) -> Schedule:
        existing = await self.get(event_name)
        if existing:
            existing.cron_expr = cron_expr
            existing.enabled = enabled
            return existing
        schedule = Schedule(
            event_name=event_name,
            cron_expr=cron_expr,
            enabled=enabled,
            description=description,
        )
        self._session.add(schedule)
        return schedule
