"""认证与账号路由（Controller）——`14-api-spec.md` §2。

**职责**：解析请求、注入当前账号、调用应用服务、返回响应。**不含业务判定**。
"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.presentation.dependencies import (
    AdminAccount,
    AuthServiceDep,
    CurrentAccount,
)
from app.presentation.schemas import (
    AccountResponse,
    AddLibrarianRequest,
    LoginRequest,
    RegisterReaderRequest,
    ResetPasswordRequest,
    TokenResponse,
)

router = APIRouter(tags=["auth"])


@router.post("/api/auth/register", status_code=status.HTTP_201_CREATED, response_model=AccountResponse)
def register_reader(payload: RegisterReaderRequest, service: AuthServiceDep) -> AccountResponse:
    """读者注册（UC-001）。注册后**不具备借阅资格**，须先办证（BR-012）。"""
    reader = service.register_reader(
        username=payload.username,
        password=payload.password,
        name=payload.name,
        department=payload.department,
        reader_type=payload.reader_type,
    )
    return AccountResponse(
        account_id=reader.reader_id or 0,
        username=reader.username,
        name=reader.name,
        role=reader.ROLE,
        reader_type=reader.reader_type.value if reader.reader_type else None,
        department=reader.department,
    )


@router.post("/api/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, service: AuthServiceDep) -> TokenResponse:
    """登录（UC-002）。失败提示统一为"用户名或密码错误"（BR-047）。"""
    result = service.login(payload.username, payload.password, payload.role)
    result["expires_at"] = result["expires_at"].isoformat()
    return TokenResponse(**result)


@router.post(
    "/api/admin/librarians",
    status_code=status.HTTP_201_CREATED,
    response_model=AccountResponse,
)
def add_librarian(
    payload: AddLibrarianRequest, _: AdminAccount, service: AuthServiceDep
) -> AccountResponse:
    """添加图书管理员（UC-206）。仅系统管理员可调用（BR-041）。"""
    librarian = service.add_librarian(payload.username, payload.password, payload.name)
    return AccountResponse(
        account_id=librarian.librarian_id or 0,
        username=librarian.username,
        name=librarian.name,
        role=librarian.ROLE,
    )


@router.get("/api/admin/librarians", response_model=list[AccountResponse])
def list_librarians(
    _: AdminAccount, service: AuthServiceDep, include_deleted: bool = False
) -> list[AccountResponse]:
    return [
        AccountResponse(
            account_id=librarian.librarian_id or 0,
            username=librarian.username,
            name=librarian.name,
            role=librarian.ROLE,
        )
        for librarian in service.list_librarians(include_deleted=include_deleted)
    ]


@router.delete("/api/admin/librarians/{librarian_id}", status_code=status.HTTP_200_OK)
def delete_librarian(librarian_id: int, _: AdminAccount, service: AuthServiceDep) -> dict:
    """删除图书管理员（UC-207，软删除）。系统管理员之间不可互相删除（BR-043）。"""
    service.delete_librarian(librarian_id)
    return {"deleted": True, "librarian_id": librarian_id}


@router.post("/api/admin/accounts/{account_id}/reset-password", status_code=status.HTTP_200_OK)
def reset_password(
    account_id: int,
    payload: ResetPasswordRequest,
    _: AdminAccount,
    service: AuthServiceDep,
) -> dict:
    """重置账号密码（FR-003 验收标准 5、Q-05 裁定）。

    系统**不提供**自助找回密码接口。
    """
    service.reset_password(account_id, payload.new_password, payload.role)
    return {"reset": True, "account_id": account_id}


@router.get("/api/auth/me", response_model=AccountResponse)
def me(account: CurrentAccount) -> AccountResponse:
    """当前登录账号信息（用于前端判断角色与展示）。"""
    role = getattr(account, "ROLE", "READER")
    return AccountResponse(
        account_id=_account_id(account),
        username=getattr(account, "username", ""),
        name=getattr(account, "name", ""),
        role=role,
        reader_type=(
            account.reader_type.value
            if getattr(account, "reader_type", None) is not None
            else None
        ),
        department=getattr(account, "department", None),
    )


def _account_id(account) -> int:
    for attr in ("reader_id", "librarian_id", "admin_id"):
        value = getattr(account, attr, None)
        if value is not None:
            return int(value)
    return 0
