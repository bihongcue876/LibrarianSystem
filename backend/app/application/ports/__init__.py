"""Repository 接口（Ports）。定义在**应用层**而非领域层（`07-architecture.md` ADR-02）。

**接口契约**：

- 返回**领域实体**，不返回 ORM 模型（避免持久化细节泄漏到上层）。
- 只负责持久化：**不做业务判定、不提交事务**（事务边界在应用服务）。
- 查询默认过滤已软删除记录（BR-037）。
"""

from app.application.ports.card_repository import CardRepository
from app.application.ports.catalog_repository import CatalogRepository
from app.application.ports.fine_repository import FineRepository
from app.application.ports.loan_repository import LoanRepository
from app.application.ports.policy_repository import PolicyRepository
from app.application.ports.reader_repository import ReaderRepository
from app.application.ports.reservation_repository import ReservationRepository
from app.application.ports.security import PasswordHasher, TokenIssuer

__all__ = [
    "CardRepository",
    "CatalogRepository",
    "FineRepository",
    "LoanRepository",
    "PasswordHasher",
    "PolicyRepository",
    "ReaderRepository",
    "ReservationRepository",
    "TokenIssuer",
]
