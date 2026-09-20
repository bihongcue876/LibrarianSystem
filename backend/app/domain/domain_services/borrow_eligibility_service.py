"""BorrowEligibilityService（`05-domain-model.md` §5.4）。

**纯函数式领域服务**：只判定、不改状态、不访问数据库。这是它与应用服务的关键区别。

校验顺序**固定**为「借阅证 → 数量 → 超期 → 罚款 → 副本」（`09-design-model.md` §2.2）。
该顺序决定了失败时返回哪个错误码——**遇首个失败即返回，不累积错误**。
（"权限"是第 0 项，由表现层的角色守卫完成，不属于本服务。）

状态码依据 `02-requirements.md` FR-016 验收标准 2：业务规则失败统一为 **400**。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from app.domain.entities.borrow_card import BorrowCard
from app.domain.entities.fine_record import FineRecord
from app.domain.entities.library_item import LibraryItem
from app.domain.entities.loan import Loan
from app.domain.entities.reader import Reader
from app.domain.entities.reservation import Reservation
from app.domain.exceptions import (
    BORROW_LIMIT_EXCEEDED,
    CARD_INVALID,
    ITEM_NOT_AVAILABLE,
    OVERDUE_LOAN_EXISTS,
    UNPAID_FINE_EXISTS,
    BusinessRuleError,
    ValidationError,
)
from app.domain.value_objects.money import Money

# 校验步骤标识（顺序即执行顺序）
STEP_CARD = "card"
STEP_QUOTA = "quota"
STEP_OVERDUE = "overdue"
STEP_FINE = "fine"
STEP_ITEM = "item"

CHECK_ORDER: tuple[str, ...] = (STEP_CARD, STEP_QUOTA, STEP_OVERDUE, STEP_FINE, STEP_ITEM)


@dataclass(frozen=True, slots=True)
class CheckResult:
    """单项校验结果。"""

    step: str
    ok: bool
    code: str = ""
    message: str = ""
    detail: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def passed(cls, step: str, message: str = "") -> "CheckResult":
        return cls(step=step, ok=True, message=message)

    @classmethod
    def failed(cls, step: str, code: str, message: str, **detail: Any) -> "CheckResult":
        return cls(step=step, ok=False, code=code, message=message, detail=detail)


class BorrowEligibilityService:
    """借阅资格判定服务。无状态、纯函数式。"""

    # ---- 单项校验 --------------------------------------------------------

    @staticmethod
    def validate_card(card: BorrowCard | None) -> CheckResult:
        """借阅证必须存在且状态为 `ACTIVE`（BR-001）。"""
        if card is None:
            return CheckResult.failed(STEP_CARD, CARD_INVALID, "借阅证不存在")
        if not card.is_valid():
            return CheckResult.failed(
                STEP_CARD, CARD_INVALID, f"借阅证状态为 {card.status.value}，不可借书",
                status=card.status.value,
            )
        return CheckResult.passed(STEP_CARD, "借阅证有效")

    def check_quota(
        self,
        reader: Reader,
        loans: Sequence[Loan],
        reservations: Sequence[Reservation],
        policy,
    ) -> CheckResult:
        """占用额度必须小于上限（BR-007、BR-008）。

        额度口径 = **未归还借阅 + 有效预约**。
        """
        limit = reader.borrow_limit(policy)
        occupied = reader.occupies_quota(loans, reservations)
        if occupied >= limit:
            return CheckResult.failed(
                STEP_QUOTA, BORROW_LIMIT_EXCEEDED, "超出借阅数量上限",
                current=occupied, limit=limit,
            )
        return CheckResult.passed(STEP_QUOTA, f"额度充足（{occupied}/{limit}）")

    @staticmethod
    def check_overdue(loans: Sequence[Loan], now=None) -> CheckResult:
        """不得存在超期未还的借阅记录（BR-010）。"""
        overdue = [loan for loan in loans if loan.is_open() and loan.is_overdue(now)]
        if overdue:
            return CheckResult.failed(
                STEP_OVERDUE, OVERDUE_LOAN_EXISTS, "存在超期未还的图书",
                overdue_loan_ids=[loan.loan_id for loan in overdue],
            )
        return CheckResult.passed(STEP_OVERDUE, "无超期未还")

    @staticmethod
    def check_unpaid_fine(fines: Sequence[FineRecord]) -> CheckResult:
        """不得存在未缴清的罚款（BR-011）。"""
        unpaid = [fine for fine in fines if fine.is_unpaid()]
        if unpaid:
            total = Money.zero()
            for fine in unpaid:
                total = total.add(fine.amount)
            return CheckResult.failed(
                STEP_FINE,
                UNPAID_FINE_EXISTS,
                "存在未缴清的罚款",
                unpaid_fine_ids=[fine.fine_id for fine in unpaid],
                total_amount=total.to_text(),
            )
        return CheckResult.passed(STEP_FINE, "无欠款")

    @staticmethod
    def check_item(item: LibraryItem | None) -> CheckResult:
        """副本必须存在、属本馆且状态为 `AVAILABLE`（BR-033）。"""
        if item is None:
            return CheckResult.failed(STEP_ITEM, ITEM_NOT_AVAILABLE, "馆藏副本不存在")
        if not item.is_available():
            return CheckResult.failed(
                STEP_ITEM, ITEM_NOT_AVAILABLE, f"副本状态为 {item.status.value}，不可借出",
                status=item.status.value,
            )
        return CheckResult.passed(STEP_ITEM, "副本可借")

    # ---- 组合判定 --------------------------------------------------------

    def check_all(
        self,
        reader: Reader,
        card: BorrowCard | None,
        loans: Sequence[Loan],
        reservations: Sequence[Reservation],
        fines: Sequence[FineRecord],
        policy,
        item: LibraryItem | None,
        now=None,
    ) -> list[CheckResult]:
        """返回**全部**校验结果（供借书前置预检查 FR-015 使用，不抛异常）。"""
        return [check() for check in self._check_plan(
            reader, card, loans, reservations, fines, policy, item, now
        )]

    def check_and_raise(
        self,
        reader: Reader,
        card: BorrowCard | None,
        loans: Sequence[Loan],
        reservations: Sequence[Reservation],
        fines: Sequence[FineRecord],
        policy,
        item: LibraryItem | None,
        now=None,
    ) -> None:
        """按固定顺序校验，**遇首个失败即抛异常**（FR-016）。

        实现上按顺序**逐个**求值并在首个失败处抛出，而不是先算出全部结果再筛选——
        后者会让排在后面的校验的计算副作用（如访问空缺的关联数据）在前面已经失败时
        仍然发生，与「不累积错误」的语义不符。

        抛出的异常映射：`CARD_INVALID` → 400 `ValidationError`；
        其余四项 → 400 `BusinessRuleError`。
        """
        for step, check in zip(CHECK_ORDER, self._check_plan(
            reader, card, loans, reservations, fines, policy, item, now
        ), strict=True):
            result = check()
            if result.ok:
                continue
            if step == STEP_CARD:
                raise ValidationError(
                    result.message, code=result.code, http_status=400, detail=result.detail
                )
            raise BusinessRuleError(
                result.message, code=result.code, http_status=400, detail=result.detail
            )

    def _check_plan(
        self,
        reader: Reader,
        card: BorrowCard | None,
        loans: Sequence[Loan],
        reservations: Sequence[Reservation],
        fines: Sequence[FineRecord],
        policy,
        item: LibraryItem | None,
        now=None,
    ) -> tuple:
        """按固定顺序返回校验动作序列（**惰性**，调用时才求值）。"""
        return (
            lambda: self.validate_card(card),
            lambda: self.check_quota(reader, loans, reservations, policy),
            lambda: self.check_overdue(loans, now),
            lambda: self.check_unpaid_fine(fines),
            lambda: self.check_item(item),
        )
