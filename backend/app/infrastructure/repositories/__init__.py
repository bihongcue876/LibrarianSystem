"""Repository 实现包（基础设施层）。

**依赖倒置的落点**：这些类实现 `application/ports/` 定义的 Protocol，
由 `main.py` 的装配代码绑定到应用服务——应用服务本身不知道实现类的存在。
"""

from app.infrastructure.repositories.sqlalchemy_card_repository import (
    SqlAlchemyCardRepository,
)
from app.infrastructure.repositories.sqlalchemy_catalog_repository import (
    SqlAlchemyCatalogRepository,
)
from app.infrastructure.repositories.sqlalchemy_fine_repository import (
    SqlAlchemyFineRepository,
)
from app.infrastructure.repositories.sqlalchemy_loan_repository import (
    SqlAlchemyLoanRepository,
)
from app.infrastructure.repositories.sqlalchemy_policy_repository import (
    SqlAlchemyPolicyRepository,
)
from app.infrastructure.repositories.sqlalchemy_reader_repository import (
    SqlAlchemyReaderRepository,
)
from app.infrastructure.repositories.sqlalchemy_reservation_repository import (
    SqlAlchemyReservationRepository,
)

__all__ = [
    "SqlAlchemyCardRepository",
    "SqlAlchemyCatalogRepository",
    "SqlAlchemyFineRepository",
    "SqlAlchemyLoanRepository",
    "SqlAlchemyPolicyRepository",
    "SqlAlchemyReaderRepository",
    "SqlAlchemyReservationRepository",
]
