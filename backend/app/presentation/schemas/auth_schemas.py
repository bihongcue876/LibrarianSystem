"""认证与账号 DTO（`14-api-spec.md` §2）。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.domain.enums import ReaderType

LoginRole = Literal["READER", "LIBRARIAN", "SYSTEM_ADMIN"]


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=6, max_length=24)
    role: LoginRole = Field(default="READER", description="登录入口：READER / LIBRARIAN / SYSTEM_ADMIN")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    account_id: int
    username: str
    expires_at: str | None = None


class RegisterReaderRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(..., min_length=6, max_length=24)
    name: str = Field(..., min_length=1, max_length=64)
    department: str = Field(..., min_length=1, max_length=128)
    reader_type: ReaderType


class AccountResponse(BaseModel):
    account_id: int
    username: str
    name: str
    role: str
    reader_type: str | None = None
    department: str | None = None


class AddLibrarianRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(..., min_length=6, max_length=24)
    name: str = Field(..., min_length=1, max_length=64)


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=6, max_length=24)
    role: Literal["READER", "LIBRARIAN"] = Field(
        default="READER", description="目标账号角色：READER / LIBRARIAN"
    )
