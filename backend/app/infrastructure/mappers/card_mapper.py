"""`BorrowCard` ↔ `borrow_cards` 表（单表继承无涉）。"""

from __future__ import annotations

from app.domain.entities.borrow_card import BorrowCard
from app.domain.enums import CardStatus
from app.infrastructure.mappers._time import to_db, to_domain
from app.infrastructure.models import BorrowCardModel


class CardMapper:
    """借阅证双向转换。"""

    @staticmethod
    def to_domain(model: BorrowCardModel) -> BorrowCard:
        return BorrowCard.rehydrate(
            card_id=model.card_id,
            card_no=model.card_no,
            reader_id=model.reader_id,
            status=CardStatus(model.status),
            issued_at=to_domain(model.issued_at),
            issued_by=model.issued_by,
            cancelled_at=to_domain(model.cancelled_at),
            expired_at=to_domain(model.expired_at),
        )

    @staticmethod
    def to_model(card: BorrowCard, model: BorrowCardModel | None = None) -> BorrowCardModel:
        target = model or BorrowCardModel()
        target.card_id = card.card_id
        target.card_no = str(card.card_no)
        target.reader_id = card.reader_id
        target.status = card.status.value
        target.issued_at = to_db(card.issued_at)
        target.issued_by = card.issued_by
        target.cancelled_at = to_db(card.cancelled_at)
        target.expired_at = to_db(card.expired_at)
        return target
