from __future__ import annotations

import datetime
import logging

import bcrypt
import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.api.schemas import AuthResponse, UserDto
from backend.auth.repos.auth_repo import UserRepository

logger = logging.getLogger(__name__)


class AuthService:

    def __init__(
        self,
        session: AsyncSession,
        secret_key: str,
        algorithm: str,
        ttl_hours: int = 24,
    ) -> None:
        self._repo = UserRepository(session)
        self._session = session
        self._secret_key = secret_key
        self._algorithm = algorithm
        self._ttl_hours = ttl_hours

    # ── helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    @staticmethod
    def _verify_password(password: str, hashed: str) -> bool:
        return bcrypt.checkpw(password.encode(), hashed.encode())

    def _create_token(self, user_id: int, email: str) -> str:
        payload = {
            "sub": str(user_id),
            "email": email,
            "iat": datetime.datetime.now(datetime.UTC),
            "exp": datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=self._ttl_hours),
        }
        return jwt.encode(payload, self._secret_key, algorithm=self._algorithm)

    def decode_token(self, token: str) -> dict:
        return jwt.decode(token, self._secret_key, algorithms=[self._algorithm])

    # ── public API ──────────────────────────────────────────────────────

    async def login(self, email: str, password: str) -> AuthResponse:
        user = await self._repo.get_user_by_email(email)
        if not user or not self._verify_password(password, user.hash_password):
            msg = "Invalid email or password"
            raise ValueError(msg)

        token = self._create_token(user.id, user.email)
        return AuthResponse(
            token=token,
            user=UserDto.model_validate(user),
        )

    async def forgot_password(self, email: str) -> None:
        user = await self._repo.get_user_by_email(email)
        if not user:
            msg = "Email not found"
            raise ValueError(msg)
        logger.info("Password recovery requested for %s", email)

    async def change_password(
        self, user_id: int, old_password: str, new_password: str
    ) -> None:
        user = await self._repo.get_user_by_id(user_id)
        if not user:
            msg = "User not found"
            raise ValueError(msg)
        if not self._verify_password(old_password, user.hash_password):
            msg = "Old password is incorrect"
            raise ValueError(msg)

        hashed = self._hash_password(new_password)
        await self._repo.update_password(user.id, hashed)
        await self._session.commit()
