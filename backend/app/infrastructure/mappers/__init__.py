"""Mapper 包：ORM 模型（基础设施侧）↔ 领域对象。

**为什么需要这一层**：领域实体是纯 Python 对象（带业务行为、零框架依赖），
ORM 模型带 `Column`/`__tablename__`。两者必须是**两套对象**，
否则领域层就得 `import sqlalchemy` → 违反宪法第五条（`07-architecture.md` ADR-05）。
"""

from app.infrastructure.mappers.card_mapper import CardMapper
from app.infrastructure.mappers.catalog_mapper import CatalogMapper
from app.infrastructure.mappers.fine_mapper import FineMapper
from app.infrastructure.mappers.loan_mapper import LoanMapper
from app.infrastructure.mappers.policy_mapper import PolicyMapper
from app.infrastructure.mappers.reader_mapper import (
    LibrarianMapper,
    ReaderMapper,
    SystemAdminMapper,
)
from app.infrastructure.mappers.reservation_mapper import ReservationMapper

__all__ = [
    "CardMapper",
    "CatalogMapper",
    "FineMapper",
    "LibrarianMapper",
    "LoanMapper",
    "PolicyMapper",
    "ReaderMapper",
    "ReservationMapper",
    "SystemAdminMapper",
]
