"""FineRecord 实体（`05-domain-model.md` §7.1、`06-domain-class-diagram.md` 图 6）。

关键设计：

- **快照 `unit_price`**：罚款在还书时一次性计算（BR-029），单价随记录保存，
  因此规则修改**不追溯**已生成的罚款（BR-050）。
- `operator_role` 记录收缴人角色（`LIBRARIAN` / `SYSTEM_ADMIN`）——`operator_id` 不建外键，
  因为收缴人可能来自 `librarians` 或 `system_admins` 两张表（决策见 `13-database-design.md` §4.9）。
- 金额全程使用 `Money`（`Decimal`），禁止 `float`（Q-04）。
"""

from __future__ import annotations

from datetime import datetime

from app.domain.entities.loan import Loan
from app.domain.enums import FineStatus, ItemType
from app.domain.exceptions import ValidationError
from app.domain.value_objects.money import Money

OPERATOR_ROLE_LIBRARIAN = "LIBRARIAN"
OPERATOR_ROLE_SYSTEM_ADMIN = "SYSTEM_ADMIN"


from app.domain.clock import utc_now


class FineRecord:
    """罚款记录。`FineRecord` 1 — 1 `Loan`（BR-029：一次性计算）。"""

    def __init__(
        self,
        fine_id: int | None = None,
        loan_id: int | None = None,
        reader_id: int | None = None,
        amount: Money | None = None,
        overdue_days: int = 0,
        billed_days: int = 0,
        unit_price: Money | None = None,
        status: FineStatus | str = FineStatus.UNPAID,
        created_at: datetime | None = None,
        paid_at: datetime | None = None,
        operator_id: int | None = None,
        operator_role: str | None = None,
    ) -> None:
        self.fine_id = fine_id
        self.loan_id = loan_id
        self.reader_id = reader_id
        self.amount = amount or Money.zero()
        self.overdue_days = overdue_days
        self.billed_days = billed_days
        self.unit_price = unit_price or Money.zero()
        self._status = FineStatus(status)
        self.created_at = created_at or utc_now()
        self.paid_at = paid_at
        self.operator_id = operator_id
        self.operator_role = operator_role

    @property
    def status(self) -> FineStatus:
        return self._status

    # ---- 构造 ------------------------------------------------------------

    @classmethod
    def create(
        cls,
        loan: Loan,
        item_type: ItemType | str,
        returned_at: datetime,
        fine_rule,
        now: datetime | None = None,
    ) -> "FineRecord":
        """按罚款规则计算并创建记录（`09-design-model.md` §8.3）。

        调用方须先确认 `overdue_days > 0`；未超期不应创建记录（BR-029）。
        """
        overdue_days = loan.overdue_days(returned_at)
        amount = fine_rule.calculate_fine(item_type, overdue_days)
        billed_days = fine_rule.billed_days(overdue_days, item_type)
        return cls(
            loan_id=loan.loan_id,
            reader_id=loan.reader_id,
            amount=amount,
            overdue_days=overdue_days,
            billed_days=billed_days,
            unit_price=fine_rule.unit_price_of(item_type),  # 快照，规则修改不追溯（BR-050）
            status=FineStatus.UNPAID,
            created_at=now or utc_now(),
        )

    @classmethod
    def rehydrate(cls, **kwargs) -> "FineRecord":
        """**仅供 Mapper 从持久化状态重建**。"""
        return cls(**kwargs)

    # ---- 收缴 ------------------------------------------------------------

    def pay(self, operator) -> None:
        """标记为已缴。记录操作人 ID 与角色（BR-031）。"""
        if self._status is FineStatus.PAID:
            raise ValidationError("该罚款已缴清", code="FINE_ALREADY_PAID")
        role = getattr(operator, "ROLE", None)
        if role not in (OPERATOR_ROLE_LIBRARIAN, OPERATOR_ROLE_SYSTEM_ADMIN):
            raise PermissionError("仅图书管理员或系统管理员可收缴罚款")
        self._status = FineStatus.PAID
        self.paid_at = utc_now()
        self.operator_id = getattr(operator, "account_id", None)
        self.operator_role = role

    def is_unpaid(self) -> bool:
        """未缴清时禁止借书（BR-011）。"""
        return self._status is FineStatus.UNPAID

    def __str__(self) -> str:  # pragma: no cover
        return f"FineRecord(id={self.fine_id}, amount={self.amount}, {self._status.value})"

    def __repr__(self) -> str:  # pragma: no cover
        return self.__str__()
