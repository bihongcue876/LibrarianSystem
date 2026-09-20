"""`FineRepository` 接口（罚款记录）。"""

from __future__ import annotations

from typing import Protocol, Sequence, runtime_checkable

from app.domain.entities.fine_record import FineRecord


@runtime_checkable
class FineRepository(Protocol):
    """罚款持久化接口。"""

    def find_by_id(self, fine_id: int) -> FineRecord | None: ...

    def find_by_loan(self, loan_id: int) -> FineRecord | None:
        """一条借阅记录最多一条罚款（`loan_id` UNIQUE，BR-029）。"""

    def find_unpaid_by_reader(self, reader_id: int) -> Sequence[FineRecord]:
        """取未缴罚款——借书拦截校验用（BR-011）。"""

    def find_by_reader(self, reader_id: int) -> Sequence[FineRecord]:
        """取该读者全部罚款记录（含已缴）。"""

    def sum_unpaid_by_reader(self, reader_id: int) -> str:
        """未缴罚款总额（定点小数字符串）。"""

    def add(self, record: FineRecord) -> FineRecord: ...

    def update(self, record: FineRecord) -> None: ...
