from __future__ import annotations

from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Типовые CRUD-операции для любой модели.
    Наследники добавляют только специфичные методы.
    """

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, record_id: int) -> ModelT | None:
        return await self._session.get(self.model, record_id)

    async def get_all(self) -> list[ModelT]:
        result = await self._session.execute(select(self.model))
        return list(result.scalars().all())

    async def create(self, **kwargs: Any) -> ModelT:
        instance = self.model(**kwargs)
        self._session.add(instance)
        await self._session.flush()  # получить id без commit
        return instance

    async def update(self, record_id: int, **kwargs: Any) -> ModelT | None:
        instance = await self.get(record_id)
        if instance is None:
            return None
        for key, value in kwargs.items():
            setattr(instance, key, value)
        await self._session.flush()
        return instance

    async def delete(self, record_id: int) -> bool:
        instance = await self.get(record_id)
        if instance is None:
            return False
        await self._session.delete(instance)
        await self._session.flush()
        return True
