"""`LoanRepository` 接口（借阅记录）。"""

from __future__ import annotations

from typing import Protocol, Sequence, runtime_checkable

from app.domain.entities.loan import Loan


@runtime_checkable
class LoanRepository(Protocol):
    """借阅记录持久化接口。"""

    def find_by_id(self, loan_id: int) -> Loan | None: ...

    def find_active_by_item(self, item_id: int) -> Loan | None:
        """取该副本当前**未归还**的借阅记录（还书用，UC-102）。"""

    def find_active_by_reader(self, reader_id: int) -> Sequence[Loan]:
        """取该读者全部未归还借阅——额度占用计算用（BR-007）。"""

    def find_by_reader(self, reader_id: int) -> Sequence[Loan]:
        """取该读者全部借阅记录（含历史），按借出时间倒序。"""

    def find_overdue(self, now=None) -> Sequence[Loan]:
        """取全部已超期且未归还的记录（派生状态查询：`status='BORROWED' AND due_at < now`）。"""

    def count_active_by_reader(self, reader_id: int) -> int: ...

    def add(self, loan: Loan) -> Loan: ...

    def update(self, loan: Loan) -> None: ...
