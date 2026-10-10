"""Loan 实体（`05-domain-model.md` §5.1、`06-domain-class-diagram.md` 图 4）。

**聚合根**：借出、续借、归还的状态变更必须原子化。

两个关键设计（`06` §4、§10.3）：

- `create()` 在借出时刻**快照** `due_at`——这是"规则修改不追溯已有借阅"（BR-050）的实现基础。
- `OVERDUE` 是**派生状态**（由 `due_at` 与当前时刻实时判定），**不落库**；
  持久化只存 `BORROWED` / `RETURNED`。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from app.domain.clock import utc_now
from app.domain.enums import LoanStatus
from app.domain.exceptions import BusinessRuleError, ValidationError

if TYPE_CHECKING:  # pragma: no cover
    from app.domain.entities.library_item import LibraryItem
    from app.domain.entities.reader import Librarian, Reader
    from app.domain.policies import BorrowPolicy


class Loan:
    """借阅记录。"""

    def __init__(
        self,
        loan_id: int | None = None,
        reader_id: int | None = None,
        item_id: int | None = None,
        borrowed_at: datetime | None = None,
        due_at: datetime | None = None,
        returned_at: datetime | None = None,
        status: LoanStatus | str = LoanStatus.BORROWED,
        librarian_id: int | None = None,
        renew_count: int = 0,
    ) -> None:
        self.loan_id = loan_id
        self.reader_id = reader_id
        self.item_id = item_id
        self.borrowed_at = borrowed_at or utc_now()
        self.due_at = due_at or self.borrowed_at
        self.returned_at = returned_at
        self._status = LoanStatus(status)
        self.librarian_id = librarian_id
        self.renew_count = renew_count

    # ---- 状态 ------------------------------------------------------------

    @property
    def status(self) -> LoanStatus:
        return self._status

    @property
    def persisted_status(self) -> LoanStatus:
        """数据库实际存储的两态（`13-database-design.md` 的 CHECK 约束）。"""
        return LoanStatus.RETURNED if self._status is LoanStatus.RETURNED else LoanStatus.BORROWED

    # ---- 构造 ------------------------------------------------------------

    @classmethod
    def create(
        cls,
        reader: "Reader",
        item: "LibraryItem",
        policy: "BorrowPolicy",
        librarian: "Librarian | None" = None,
        now: datetime | None = None,
    ) -> "Loan":
        """创建借阅记录，并按读者类型**快照** `due_at`。

        `librarian_id` 取经办人（图书管理员）。系统管理员代行流通业务时该值为
        `None`——其身份不由本表留痕，取舍见 `13-database-design.md` §4.7。
        """
        moment = now or utc_now()
        days = reader.borrow_days(policy)
        return cls(
            reader_id=reader.reader_id,
            item_id=item.item_id,
            borrowed_at=moment,
            due_at=moment + timedelta(days=days),
            status=LoanStatus.BORROWED,
            librarian_id=getattr(librarian, "librarian_id", None),
            renew_count=0,
        )

    @classmethod
    def rehydrate(cls, **kwargs) -> "Loan":
        """**仅供 Mapper 从持久化状态重建**。"""
        status = kwargs.pop("status", LoanStatus.BORROWED)
        return cls(status=status, **kwargs)

    # ---- 超期判定（派生） ------------------------------------------------

    def is_overdue(self, now: datetime | None = None) -> bool:
        """是否超期。已归还的记录一律返回 False。"""
        if self._status is LoanStatus.RETURNED:
            return False
        return (now or utc_now()) > self.due_at

    def overdue_days(self, now: datetime | None = None) -> int:
        """超期天数（未超期为 0）。"""
        if self._status is LoanStatus.RETURNED:
            reference = self.returned_at or utc_now()
        else:
            reference = now or utc_now()
        delta = (reference - self.due_at).days
        return max(delta, 0)

    def derived_status(self, now: datetime | None = None) -> LoanStatus:
        """业务语义上的状态（含派生的 `OVERDUE`）。"""
        if self._status is LoanStatus.RETURNED:
            return LoanStatus.RETURNED
        return LoanStatus.OVERDUE if self.is_overdue(now) else LoanStatus.BORROWED

    # ---- 续借 ------------------------------------------------------------

    MAX_RENEW_COUNT = 2
    RENEW_DAYS = 7

    def can_renew(self, now: datetime | None = None) -> bool:
        """自身是否满足续借条件（次数未满 + 未超期）。

        **额度判定不在此处**——那需要读者与其他借阅数据，
        由 `RenewalService` 承担（BR-017）。
        """
        if self._status is LoanStatus.RETURNED:
            return False
        if self.renew_count >= self.MAX_RENEW_COUNT:
            return False
        return not self.is_overdue(now)

    def renew(self, now: datetime | None = None) -> None:
        """执行续借：`due_at` +7 天，次数 +1（BR-015）。

        `now` 与 `RenewalService` 的注入时钟保持一致，避免"注入时钟判定未超期、
        实体内部用真实时钟判超期"的两道关卡结论矛盾。
        """
        if self._status is LoanStatus.RETURNED:
            raise ValidationError("借阅记录已归还，不可续借", code="LOAN_ALREADY_RETURNED")
        if self.renew_count >= self.MAX_RENEW_COUNT:
            raise BusinessRuleError(
                f"续借次数已达上限 {self.MAX_RENEW_COUNT} 次", code="RENEW_LIMIT_EXCEEDED"
            )
        if self.is_overdue(now):
            raise BusinessRuleError("借阅记录已超期，不可续借", code="RENEW_OVERDUE")
        self.due_at = self.due_at + timedelta(days=self.RENEW_DAYS)
        self.renew_count += 1

    # ---- 归还 ------------------------------------------------------------

    def return_item(self, now: datetime | None = None) -> None:
        """归还：状态置 `RETURNED`，写入 `returned_at`。"""
        if self._status is LoanStatus.RETURNED:
            raise ValidationError("借阅记录已归还", code="LOAN_ALREADY_RETURNED")
        self.returned_at = now or utc_now()
        self._status = LoanStatus.RETURNED

    # ---- 判定 ------------------------------------------------------------

    def is_open(self) -> bool:
        """是否未归还（占用借阅额度）。"""
        return self._status is not LoanStatus.RETURNED

    def __str__(self) -> str:  # pragma: no cover
        return f"Loan(id={self.loan_id}, item={self.item_id}, {self._status.value})"

    def __repr__(self) -> str:  # pragma: no cover
        return self.__str__()
