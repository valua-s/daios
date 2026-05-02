from __future__ import annotations

from dishka.integrations.litestar import FromDishka
from litestar import Controller, Request, post
from litestar.exceptions import HTTPException

from backend.auth.api.schemas import (
    AuthResponse,
    ChangePasswordRequest,
    ForgotRequest,
    LoginRequest,
    MessageResponse,
)
from backend.auth.guards import jwt_auth_guard
from backend.auth.service.auth_service import AuthService


class AuthController(Controller):
    path = "/api/auth"

    @post("/login")
    async def login(
        self,
        data: LoginRequest,
        auth_service: FromDishka[AuthService],
    ) -> AuthResponse:
        try:
            return await auth_service.login(data.email, data.password)
        except ValueError as e:
            raise HTTPException(status_code=401, detail=str(e))

    @post("/forgot")
    async def forgot(
        self,
        data: ForgotRequest,
        auth_service: FromDishka[AuthService],
    ) -> MessageResponse:
        try:
            await auth_service.forgot_password(data.email)
            return MessageResponse(ok=True, message="Recovery link sent")
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    @post("/change-password", guards=[jwt_auth_guard])
    async def change_password(
        self,
        data: ChangePasswordRequest,
        auth_service: FromDishka[AuthService],
        request: Request,
    ) -> MessageResponse:
        user_id = int(request.scope["user"]["id"])
        try:
            await auth_service.change_password(user_id, data.old_password, data.new_password)
            return MessageResponse(ok=True, message="Password changed")
        except ValueError as e:
            raise HTTPException(status_code=401, detail=str(e))

    @post("/logout", guards=[jwt_auth_guard])
    async def logout(self) -> MessageResponse:
        return MessageResponse(ok=True)
