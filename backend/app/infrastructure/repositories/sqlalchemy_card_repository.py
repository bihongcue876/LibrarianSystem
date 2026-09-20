"""`CardRepository` 的 SQLAlchemy 实现。"""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.entities.borrow_card import BorrowCard
from app.domain.enums import CardStatus
from app.domain.value_objects.card_number import CardNumber
from app.infrastructure.mappers import CardMapper
from app.infrastructure.models import BorrowCardModel

ACTIVE_STATUSES = (CardStatus.ACTIVE.value, CardStatus.SUSPENDED.value)


class SqlAlchemyCardRepository:
    """实现 `application.ports.CardRepository`。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def find_by_id(self, card_id: int) -> BorrowCard | None:
        model = self._session.get(BorrowCardModel, card_id)
        return CardMapper.to_domain(model) if model else None

    def find_by_card_no(self, card_no: CardNumber | str) -> BorrowCard | None:
        model = self._session.scalar(
            select(BorrowCardModel).where(BorrowCardModel.card_no == str(card_no))
        )
        return CardMapper.to_domain(model) if model else None

    def find_active_by_reader(self, reader_id: int) -> BorrowCard | None:
        """`ACTIVE` / `SUSPENDED` 计入一人一证限制，`CANCELLED` 不计入（BR-003）。"""
        model = self._session.scalar(
            select(BorrowCardModel).where(
                BorrowCardModel.reader_id == reader_id,
                BorrowCardModel.status.in_(ACTIVE_STATUSES),
            )
        )
        return CardMapper.to_domain(model) if model else None

    def list_by_reader(self, reader_id: int) -> Sequence[BorrowCard]:
        models = self._session.scalars(
            select(BorrowCardModel)
            .where(BorrowCardModel.reader_id == reader_id)
            .order_by(BorrowCardModel.card_id.asc())
        ).all()
        return [CardMapper.to_domain(model) for model in models]

    def next_sequence(self, year: int) -> int:
        """取该年度下一个序号：`MAX(序号) + 1`（`13` §4.4 的 SUBSTR 方案）。"""
        year_prefix = f"CARD{year:04d}"
        current_max = self._session.scalar(
            select(func.max(BorrowCardModel.card_no)).where(
                BorrowCardModel.card_no.like(f"{year_prefix}%")
            )
        )
        if not current_max:
            return 1
        return int(str(current_max)[8:14]) + 1

    def add(self, card: BorrowCard) -> BorrowCard:
        model = CardMapper.to_model(card)
        self._session.add(model)
        self._session.flush()
        card.card_id = model.card_id
        return card

    def update(self, card: BorrowCard) -> None:
        if card.card_id is None:
            return
        model = self._session.get(BorrowCardModel, card.card_id)
        if model is None:
            return
        CardMapper.to_model(card, model)
