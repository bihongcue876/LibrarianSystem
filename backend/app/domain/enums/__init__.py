"""领域枚举包。取值与 `05-domain-model.md` 逐项一致。"""

from app.domain.enums.card_status import CardStatus
from app.domain.enums.fine_status import FineStatus
from app.domain.enums.item_status import ItemStatus
from app.domain.enums.item_type import ItemType
from app.domain.enums.loan_status import LoanStatus
from app.domain.enums.reader_type import ReaderType
from app.domain.enums.reservation_status import ReservationStatus

__all__ = [
    "CardStatus",
    "FineStatus",
    "ItemStatus",
    "ItemType",
    "LoanStatus",
    "ReaderType",
    "ReservationStatus",
]
