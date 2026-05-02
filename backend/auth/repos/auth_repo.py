from __future__ import annotations

from sqlalchemy import select, update

from backend.auth.models.user import User
from backend.auth.repos.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def create_user(self, email: str, hash_password: str, name: str) -> User:
        return await self.create(email=email, hash_password=hash_password, name=name)

    async def get_user_by_email(self, email: str) -> User | None:
        return await self._session.scalar(select(User).where(User.email == email))

    async def get_user_by_id(self, user_id: int) -> User | None:
        return await self._session.get(User, user_id)

    async def update_password(self, user_id: int, hash_password: str) -> None:
        await self._session.execute(
            update(User).where(User.id == user_id).values(hash_password=hash_password)
        )
        await self._session.flush()

    async def email_exists(self, email: str) -> bool:
        user = await self._session.scalar(select(User.id).where(User.email == email))
        return user is not None
