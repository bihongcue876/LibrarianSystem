"""ORM 模型包。7 组模型映射 `13-database-design.md` 的 11 张表。"""

from app.infrastructure.models.card_model import BorrowCardModel
from app.infrastructure.models.catalog_model import BookTitleModel, LibraryItemModel
from app.infrastructure.models.fine_model import FineRecordModel
from app.infrastructure.models.loan_model import LoanModel
from app.infrastructure.models.policy_model import BorrowPolicyModel, FineRuleModel
from app.infrastructure.models.reader_model import (
    LibrarianModel,
    ReaderModel,
    SystemAdminModel,
)
from app.infrastructure.models.reservation_model import ReservationModel


def load_all_models() -> None:
    """触发全部模型的类定义注册到 `Base.metadata`。

    必须在 `create_all()` 之前调用——声明式模型只有被导入才会注册到元数据。
    """
    return None


__all__ = [
    "BookTitleModel",
    "BorrowCardModel",
    "BorrowPolicyModel",
    "FineRecordModel",
    "FineRuleModel",
    "LibrarianModel",
    "LibraryItemModel",
    "LoanModel",
    "ReaderModel",
    "ReservationModel",
    "SystemAdminModel",
    "load_all_models",
]
