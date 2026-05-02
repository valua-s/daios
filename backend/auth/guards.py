from __future__ import annotations

import jwt
from litestar.connection import ASGIConnection
from litestar.exceptions import NotAuthorizedException
from litestar.handlers.base import BaseRouteHandler

from backend.core.config import settings


def jwt_auth_guard(connection: ASGIConnection, _: BaseRouteHandler) -> None:
    auth_header = connection.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise NotAuthorizedException(detail="Missing or invalid token")

    token = auth_header.removeprefix("Bearer ")
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError as exc:
        raise NotAuthorizedException(detail="Invalid or expired token") from exc

    connection.scope["user"] = {"id": int(payload["sub"]), "email": payload.get("email")}
