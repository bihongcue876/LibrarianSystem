"""`CardRepository` 接口（借阅证）。"""

from __future__ import annotations

from typing import Protocol, Sequence, runtime_checkable

from app.domain.entities.borrow_card import BorrowCard
from app.domain.value_objects.card_number import CardNumber


@runtime_checkable
class CardRepository(Protocol):
    """借阅证持久化接口。"""

    def find_by_id(self, card_id: int) -> BorrowCard | None: ...

    def find_by_card_no(self, card_no: CardNumber | str) -> BorrowCard | None: ...

    def find_active_by_reader(self, reader_id: int) -> BorrowCard | None:
        """取该读者的**有效**借阅证（`ACTIVE` 或 `SUSPENDED`）——一人一证校验用（BR-003）。"""

    def list_by_reader(self, reader_id: int) -> Sequence[BorrowCard]:
        """列出该读者的全部借阅证，含历史注销记录。"""

    def next_sequence(self, year: int) -> int:
        """取该年度内下一个可用的证号序号（MAX + 1，从 1 开始）。"""

    def add(self, card: BorrowCard) -> BorrowCard: ...

    def update(self, card: BorrowCard) -> None: ...
