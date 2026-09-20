"""`CardService`（`09-design-model.md` §6）。

借阅证的签发、注销、恢复、挂失、解挂、查询。
**仅系统管理员**可管理借阅证（BR-041）。
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.application.ports import CardRepository, ReaderRepository
from app.application.unit_of_work import UnitOfWork
from app.domain.entities.borrow_card import BorrowCard
from app.domain.entities.reader import SystemAdmin
from app.domain.exceptions import ConflictError, NotFoundError
from app.domain.value_objects.card_number import CardNumber


class CardService:
    """借阅证应用服务。"""

    def __init__(
        self,
        uow: UnitOfWork,
        cards: CardRepository,
        readers: ReaderRepository,
    ) -> None:
        self._uow = uow
        self._cards = cards
        self._readers = readers

    # ---- 办理（UC-201 / FR-005） ----------------------------------------

    def issue_card(self, reader_id: int, operator: SystemAdmin) -> BorrowCard:
        """为读者办证。

        校验：读者存在 → 一人一证限制（BR-003，`CANCELLED` 不计入）→ 生成证号（BR-004）。
        """
        with self._uow:
            reader = self._readers.find_active_by_id(reader_id)
            if reader is None:
                raise NotFoundError("读者不存在", code="READER_NOT_FOUND")

            existing = self._cards.find_active_by_reader(reader_id)
            if existing is not None:
                raise ConflictError("该读者已有有效借阅证", code="CARD_ALREADY_EXISTS")

            year = datetime.now(timezone.utc).year
            card_no = CardNumber.generate(year, self._cards.next_sequence(year))
            card = BorrowCard.issue(reader, operator, card_no)
            self._cards.add(card)
            self._uow.commit()
        return card

    # ---- 状态流转（UC-202/203/204） -------------------------------------

    def cancel_card(self, card_id: int, operator: SystemAdmin) -> BorrowCard:
        card = self._require_card(card_id)
        with self._uow:
            card.cancel(operator)
            self._cards.update(card)
            self._uow.commit()
        return card

    def restore_card(self, card_id: int, operator: SystemAdmin) -> BorrowCard:
        """恢复已注销的证（FR-007）。

        恢复时若该读者已有**其他**有效借阅证，返回 409（FR-007 验收 2）。
        """
        card = self._require_card(card_id)
        with self._uow:
            existing = self._cards.find_active_by_reader(card.reader_id)
            if existing is not None and existing.card_id != card.card_id:
                raise ConflictError("该读者已有其他有效借阅证", code="CARD_ALREADY_EXISTS")
            card.restore(operator)
            self._cards.update(card)
            self._uow.commit()
        return card

    def suspend_card(self, card_id: int, operator: SystemAdmin) -> BorrowCard:
        card = self._require_card(card_id)
        with self._uow:
            card.suspend(operator)
            self._cards.update(card)
            self._uow.commit()
        return card

    def resume_card(self, card_id: int, operator: SystemAdmin) -> BorrowCard:
        card = self._require_card(card_id)
        with self._uow:
            card.resume(operator)
            self._cards.update(card)
            self._uow.commit()
        return card

    # ---- 查询（UC-205 / FR-009） ----------------------------------------

    def get_by_card_no(self, card_no: str) -> BorrowCard:
        card = self._cards.find_by_card_no(card_no)
        if card is None:
            raise NotFoundError("借阅证不存在", code="CARD_NOT_FOUND")
        return card

    def list_by_reader(self, reader_id: int) -> list[BorrowCard]:
        return list(self._cards.list_by_reader(reader_id))

    # ---- 内部 ------------------------------------------------------------

    def _require_card(self, card_id: int) -> BorrowCard:
        card = self._cards.find_by_id(card_id)
        if card is None:
            raise NotFoundError("借阅证不存在", code="CARD_NOT_FOUND")
        return card
