"""RenewalService（`05-domain-model.md` §5.5）。

判定条件（BR-015 ~ BR-018）：**未超期** 且 **`renew_count` < 2** 且 **未超出借阅额度**。

两个容易实现错的地方：

- **存在预约排队不构成禁止续借的条件**（BR-018）——不要自行加这条限制。
- 续借**不额外占用额度**（BR-019）。
"""

from __future__ import annotations

from typing import Sequence

from app.domain.entities.loan import Loan
from app.domain.entities.reader import Reader
from app.domain.entities.reservation import Reservation
from app.domain.exceptions import (
    BORROW_LIMIT_EXCEEDED,
    RENEW_LIMIT_EXCEEDED,
    RENEW_OVERDUE,
    BusinessRuleError,
)


class RenewalService:
    """续借判定与执行。无状态。"""

    @staticmethod
    def can_renew(
        loan: Loan,
        reader: Reader,
        loans: Sequence[Loan],
        reservations: Sequence[Reservation],
        policy,
        now=None,
    ) -> bool:
        """是否可续借。**注意参数 `reservations` 不参与判定**（BR-018）。"""
        if not loan.is_open():
            return False
        if loan.is_overdue(now):
            return False
        if loan.renew_count >= Loan.MAX_RENEW_COUNT:
            return False
        limit = reader.borrow_limit(policy)
        occupied = reader.occupies_quota(loans, reservations)
        return occupied <= limit

    @staticmethod
    def renew(
        loan: Loan,
        reader: Reader,
        loans: Sequence[Loan],
        reservations: Sequence[Reservation],
        policy,
        now=None,
    ) -> None:
        """执行续借：`due_at` +7 天、`renew_count` +1。

        失败抛出：`RENEW_OVERDUE`（已超期）、`RENEW_LIMIT_EXCEEDED`（次数已满）、
        `BORROW_LIMIT_EXCEEDED`（额度已超）——均为 HTTP 400（FR-018）。
        """
        if not loan.is_open():
            raise BusinessRuleError("借阅记录已归还，不可续借", code="LOAN_ALREADY_RETURNED")
        if loan.is_overdue(now):
            raise BusinessRuleError(
                "借阅记录已超期，不可续借", code=RENEW_OVERDUE, http_status=400
            )
        if loan.renew_count >= Loan.MAX_RENEW_COUNT:
            raise BusinessRuleError(
                f"续借次数已达上限 {Loan.MAX_RENEW_COUNT} 次",
                code=RENEW_LIMIT_EXCEEDED,
                http_status=400,
            )
        occupied = reader.occupies_quota(loans, reservations)
        limit = reader.borrow_limit(policy)
        if occupied > limit:
            raise BusinessRuleError(
                "当前占用额度已超出上限，不可续借",
                code=BORROW_LIMIT_EXCEEDED,
                http_status=400,
                detail={"current": occupied, "limit": limit},
            )
        loan.renew(now=now)
