from pydantic import BaseModel, EmailStr, model_validator
from typing import Self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserDto(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    email: str
    name: str


class AuthResponse(BaseModel):
    token: str
    user: UserDto


class ForgotRequest(BaseModel):
    email: EmailStr


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str
    new_password_confirm: str

    @model_validator(mode="after")
    def passwords_match(self) -> Self:
        if self.new_password != self.new_password_confirm:
            raise ValueError("Passwords do not match")
        return self


class MessageResponse(BaseModel):
    ok: bool
    message: str | None = None


class ErrorResponse(BaseModel):
    error: str
