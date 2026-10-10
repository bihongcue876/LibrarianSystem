"""依赖注入与鉴权守卫（`07-architecture.md` §6.1、§8 装配图）。

**依赖倒置的落点**：本文件把 `infrastructure` 的 Repository 实现绑定到应用服务。
应用服务只认识 `application/ports` 的 Protocol。

**权限校验必须在服务端完成**，不得依赖前端隐藏按钮（BR-042）。
"""

from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.application.exceptions import ForbiddenError, UnauthorizedError
from app.application.services import (
    AuthService,
    CardService,
    CatalogService,
    CirculationService,
    PolicyService,
    QueryService,
    ReservationService,
)
from app.application.unit_of_work import UnitOfWork
from app.domain.entities.reader import Reader, SystemAdmin
from app.infrastructure.db.session import get_session
from app.infrastructure.repositories import (
    SqlAlchemyCardRepository,
    SqlAlchemyCatalogRepository,
    SqlAlchemyFineRepository,
    SqlAlchemyLoanRepository,
    SqlAlchemyPolicyRepository,
    SqlAlchemyReaderRepository,
    SqlAlchemyReservationRepository,
)
from app.infrastructure.security.adapters import BcryptPasswordHasher, JwtTokenIssuer
from app.infrastructure.security.jwt import decode_token

ROLE_READER = "READER"
ROLE_LIBRARIAN = "LIBRARIAN"
ROLE_SYSTEM_ADMIN = "SYSTEM_ADMIN"

#: 安全能力的单例适配器（无状态，可复用）
_PASSWORD_HASHER = BcryptPasswordHasher()
_TOKEN_ISSUER = JwtTokenIssuer()

SessionDep = Annotated[Session, Depends(get_session)]


# ---------------------------------------------------------------------------
# 事务边界
# ---------------------------------------------------------------------------

def get_uow(session: SessionDep) -> UnitOfWork:
    return UnitOfWork(session)


UowDep = Annotated[UnitOfWork, Depends(get_uow)]


# ---------------------------------------------------------------------------
# 应用服务装配（依赖倒置：此处绑定具体实现）
# ---------------------------------------------------------------------------

def get_auth_service(session: SessionDep, uow: UowDep) -> AuthService:
    return AuthService(
        uow=uow,
        readers=SqlAlchemyReaderRepository(session),
        hasher=_PASSWORD_HASHER,
        tokens=_TOKEN_ISSUER,
    )


def get_card_service(session: SessionDep, uow: UowDep) -> CardService:
    return CardService(
        uow=uow,
        cards=SqlAlchemyCardRepository(session),
        readers=SqlAlchemyReaderRepository(session),
    )


def get_catalog_service(session: SessionDep, uow: UowDep) -> CatalogService:
    return CatalogService(uow=uow, catalog=SqlAlchemyCatalogRepository(session))


def get_circulation_service(session: SessionDep, uow: UowDep) -> CirculationService:
    return CirculationService(
        uow=uow,
        readers=SqlAlchemyReaderRepository(session),
        cards=SqlAlchemyCardRepository(session),
        catalog=SqlAlchemyCatalogRepository(session),
        loans=SqlAlchemyLoanRepository(session),
        reservations=SqlAlchemyReservationRepository(session),
        fines=SqlAlchemyFineRepository(session),
        policies=SqlAlchemyPolicyRepository(session),
    )


def get_reservation_service(session: SessionDep, uow: UowDep) -> ReservationService:
    return ReservationService(
        uow=uow,
        readers=SqlAlchemyReaderRepository(session),
        cards=SqlAlchemyCardRepository(session),
        catalog=SqlAlchemyCatalogRepository(session),
        reservations=SqlAlchemyReservationRepository(session),
        loans=SqlAlchemyLoanRepository(session),
        policies=SqlAlchemyPolicyRepository(session),
    )


def get_query_service(session: SessionDep) -> QueryService:
    return QueryService(
        readers=SqlAlchemyReaderRepository(session),
        catalog=SqlAlchemyCatalogRepository(session),
        loans=SqlAlchemyLoanRepository(session),
        reservations=SqlAlchemyReservationRepository(session),
        fines=SqlAlchemyFineRepository(session),
    )


def get_policy_service(session: SessionDep, uow: UowDep) -> PolicyService:
    return PolicyService(uow=uow, policies=SqlAlchemyPolicyRepository(session))


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
CardServiceDep = Annotated[CardService, Depends(get_card_service)]
CatalogServiceDep = Annotated[CatalogService, Depends(get_catalog_service)]
CirculationServiceDep = Annotated[CirculationService, Depends(get_circulation_service)]
ReservationServiceDep = Annotated[ReservationService, Depends(get_reservation_service)]
QueryServiceDep = Annotated[QueryService, Depends(get_query_service)]
PolicyServiceDep = Annotated[PolicyService, Depends(get_policy_service)]


# ---------------------------------------------------------------------------
# 当前账号与角色守卫
# ---------------------------------------------------------------------------

def _extract_token(request: Request) -> str:
    header = request.headers.get("Authorization") or ""
    if not header.lower().startswith("bearer "):
        raise UnauthorizedError("未提供有效的认证凭据")
    return header[7:].strip()


def get_current_account(request: Request, session: SessionDep):
    """解析 JWT 并加载当前账号（按 token 中的角色决定查哪张表）。

    三类账号可同名（BR-044），故必须按角色入口区分。
    """
    token = _extract_token(request)
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("登录已过期，请重新登录") from exc
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("认证凭据无效") from exc

    role = payload.get("role", ROLE_READER)
    account_id = payload.get("sub")
    if account_id is None:
        raise UnauthorizedError("认证凭据无效")

    readers = SqlAlchemyReaderRepository(session)
    if role == ROLE_SYSTEM_ADMIN:
        account = readers.find_admin_by_id(int(account_id))
    elif role == ROLE_LIBRARIAN:
        account = readers.find_librarian_by_id(int(account_id))
    else:
        account = readers.find_by_id(int(account_id))

    if account is None or getattr(account, "is_deleted", False):
        raise UnauthorizedError("账号不存在或已停用")
    return account


CurrentAccount = Annotated[object, Depends(get_current_account)]


def require_role(*roles: str):
    """生成角色守卫依赖。未登录 → 401；角色不符 → 403（BR-042）。"""

    def _guard(account: CurrentAccount):
        role = getattr(account, "ROLE", ROLE_READER)
        if role not in roles:
            raise ForbiddenError()
        return account

    return _guard


require_reader = require_role(ROLE_READER)
require_staff = require_role(ROLE_LIBRARIAN, ROLE_SYSTEM_ADMIN)
require_admin = require_role(ROLE_SYSTEM_ADMIN)

ReaderAccount = Annotated[Reader, Depends(require_reader)]
StaffAccount = Annotated[object, Depends(require_staff)]
AdminAccount = Annotated[SystemAdmin, Depends(require_admin)]


def get_optional_reader_id(account: CurrentAccount) -> int | None:
    return getattr(account, "reader_id", None)


__all__ = [
    "AdminAccount",
    "AuthServiceDep",
    "CardServiceDep",
    "CatalogServiceDep",
    "CirculationServiceDep",
    "CurrentAccount",
    "PolicyServiceDep",
    "QueryServiceDep",
    "ReaderAccount",
    "ReservationServiceDep",
    "SessionDep",
    "StaffAccount",
    "UowDep",
    "require_admin",
    "require_role",
    "require_staff",
    "ROLE_LIBRARIAN",
    "ROLE_READER",
    "ROLE_SYSTEM_ADMIN",
]
