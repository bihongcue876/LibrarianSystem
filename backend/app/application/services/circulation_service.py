"""`CirculationService`（`09-design-model.md` §2、§3、§8）。

借书、还书、续借、罚款收缴——**跨模块编排最多**的应用服务
（依赖全部 7 个 Repository，见 `08-package-diagram.md` §4）。

**职责边界**：本服务只做编排（取数据 → 调领域对象 → 落库 → 组装 DTO）。
所有判定逻辑下沉到领域层：`BorrowEligibilityService` / `RenewalService` /
`ReservationQueueService` / `BorrowPolicy` / `FineRule`。

**事务边界**：借书与还书都是「全部成功才提交」，
还书涉及借阅、副本、罚款、预约**四项状态变更**，任一失败全部回滚（FR-017 验收 7）。
"""

from __future__ import annotations

from datetime import datetime

from app.application.exceptions import ForbiddenError
from app.application.ports import (
    CardRepository,
    CatalogRepository,
    FineRepository,
    LoanRepository,
    PolicyRepository,
    ReaderRepository,
    ReservationRepository,
)
from app.application.unit_of_work import UnitOfWork
from app.domain.clock import utc_now
from app.domain.domain_services import (
    BorrowEligibilityService,
    RenewalService,
    ReservationQueueService,
)
from app.domain.entities.fine_record import FineRecord
from app.domain.entities.loan import Loan
from app.domain.entities.reader import Librarian, SystemAdmin
from app.domain.exceptions import NotFoundError

ROLE_READER = "READER"


class CirculationService:
    """流通应用服务。"""

    def __init__(
        self,
        uow: UnitOfWork,
        readers: ReaderRepository,
        cards: CardRepository,
        catalog: CatalogRepository,
        loans: LoanRepository,
        reservations: ReservationRepository,
        fines: FineRepository,
        policies: PolicyRepository,
    ) -> None:
        self._uow = uow
        self._readers = readers
        self._cards = cards
        self._catalog = catalog
        self._loans = loans
        self._reservations = reservations
        self._fines = fines
        self._policies = policies
        self._eligibility = BorrowEligibilityService()
        self._renewal = RenewalService()
        self._queue = ReservationQueueService()

    # ---- 借书前置校验（FR-015，只读） -----------------------------------

    def precheck(self, card_no: str, barcode: str, now: datetime | None = None) -> dict:
        """预检查：返回读者信息、额度与三项告警。**不产生任何数据变更**。"""
        moment = now or utc_now()
        card = self._cards.find_by_card_no(card_no)
        item = self._catalog.find_item_by_barcode(barcode)

        if card is None:
            results = [self._eligibility.validate_card(None)]
            return {"reader": None, "quota": None, "alerts": _empty_alerts(), "can_borrow": False,
                    "checks": [_as_dict(result) for result in results]}

        reader = self._readers.find_active_by_id(card.reader_id)
        if reader is None:
            raise NotFoundError("读者不存在", code="READER_NOT_FOUND")

        loans = list(self._loans.find_active_by_reader(reader.reader_id))
        reservations = list(self._reservations.find_active_by_reader(reader.reader_id))
        fines = list(self._fines.find_unpaid_by_reader(reader.reader_id))
        policy = self._policies.get_borrow_policy()

        results = self._eligibility.check_all(
            reader, card, loans, reservations, fines, policy, item, moment
        )
        limit = reader.borrow_limit(policy)
        occupied = reader.occupies_quota(loans, reservations)
        return {
            "reader": {
                "reader_id": reader.reader_id,
                "name": reader.name,
                "reader_type": reader.reader_type.value if reader.reader_type else None,
            },
            "quota": {"limit": limit, "occupied": occupied, "remaining": max(limit - occupied, 0)},
            "alerts": {
                "has_overdue": not self._eligibility.check_overdue(loans, moment).ok,
                "has_unpaid_fine": bool(fines),
                "has_due_soon": _has_due_soon(loans, moment),
            },
            "can_borrow": all(result.ok for result in results),
            "checks": [_as_dict(result) for result in results],
        }

    # ---- 借书（UC-101 / FR-016） ----------------------------------------

    def borrow_book(self, card_no: str, barcode: str, operator, now: datetime | None = None) -> dict:
        """办理借书。六项校验按固定顺序，遇首个失败即返回。"""
        moment = now or utc_now()
        with self._uow:
            card = self._cards.find_by_card_no(card_no)
            item = self._catalog.find_item_by_barcode(barcode)

            if card is None:
                # 借阅证不存在 → CARD_INVALID（400），不能先报副本错误
                self._eligibility.check_and_raise(
                    _DUMMY_READER, None, [], [], [], self._policies.get_borrow_policy(), item, moment
                )

            reader = self._readers.find_active_by_id(card.reader_id)
            if reader is None:
                raise NotFoundError("读者不存在", code="READER_NOT_FOUND")

            loans = list(self._loans.find_active_by_reader(reader.reader_id))
            reservations = list(self._reservations.find_active_by_reader(reader.reader_id))
            fines = list(self._fines.find_unpaid_by_reader(reader.reader_id))
            policy = self._policies.get_borrow_policy()

            self._eligibility.check_and_raise(
                reader, card, loans, reservations, fines, policy, item, moment
            )

            loan = Loan.create(reader, item, policy, operator, now=moment)
            item.mark_borrowed()
            self._loans.add(loan)
            self._catalog.update_item(item)
            self._uow.commit()

        return {
            "loan_id": loan.loan_id,
            "reader_id": loan.reader_id,
            "item_id": loan.item_id,
            "barcode": str(item.barcode),
            "borrowed_at": loan.borrowed_at,
            "due_at": loan.due_at,
            "status": loan.persisted_status.value,
            "remaining_quota": max(reader.remaining_quota(loans, reservations, policy) - 1, 0),
        }
    # ---- 还书（UC-102 / FR-017） ----------------------------------------

    def return_book(self, barcode: str, operator, now: datetime | None = None) -> dict:
        """办理还书。**仅凭馆藏条码，不要求借阅证**。

        一个事务内完成四项变更：借阅记录、副本状态、罚款记录（条件）、预约队列。
        """
        moment = now or utc_now()
        with self._uow:
            item = self._catalog.find_item_by_barcode(barcode)
            if item is None:
                raise NotFoundError("非本馆藏书", code="ITEM_NOT_FOUND")

            loan = self._loans.find_active_by_item(item.item_id)
            if loan is None:
                raise NotFoundError("未找到该副本的在借记录", code="LOAN_NOT_FOUND")

            overdue_days = loan.overdue_days(moment)
            fine_rule = self._policies.get_fine_rule()

            loan.return_item(moment)

            fine: FineRecord | None = None
            if overdue_days > 0:
                candidate = FineRecord.create(loan, item.item_type, moment, fine_rule, now=moment)
                # 计罚天数为 0（处于宽限期内）时不生成记录——否则会产生
                # 金额为 0 的 UNPAID 罚款，反过来阻断读者借书（BR-011），
                # 与 BR-027「宽限期内不罚」的意图相悖。
                if candidate.billed_days > 0 and candidate.amount.is_positive():
                    fine = candidate

            title = self._catalog.find_title_by_id(item.title_id, with_items=False)
            title_deleted = title is not None and title.is_deleted

            # 预约队列：惰性失效清理（BR-025b）。被置为 EXPIRED 的预约必须**同事务落库**，
            # 否则库中永远 ACTIVE、持续占用读者额度。
            queue = list(self._reservations.find_active_by_title(item.title_id))
            for expired in self._queue.dequeue_expired(queue, now=moment):
                self._reservations.update(expired)

            head: object | None = None
            if title_deleted:
                # 题录已软删除（FR-011 验收 4）：副本归还后直接置 `REMOVED`，
                # 不再为预约队列预留。队列中的残留预约由惰性判定逐次清理。
                item.mark_returned(has_reservation=False)
                title.mark_returned_item_removed(item)
            else:
                head = self._queue.handover(queue, item=None, now=moment)
                if head is None:
                    item.mark_returned(has_reservation=False)
                else:
                    item.mark_returned(has_reservation=True)
                    self._reservations.update(head)

            self._loans.update(loan)
            self._catalog.update_item(item)
            if fine is not None:
                self._fines.add(fine)
            self._uow.commit()

        return {
            "loan_id": loan.loan_id,
            "returned_at": loan.returned_at,
            "overdue_days": overdue_days,
            "billed_days": fine.billed_days if fine else 0,
            "fine": (
                {
                    "fine_id": fine.fine_id,
                    "amount": fine.amount.to_text(),
                    "status": fine.status.value,
                }
                if fine is not None
                else None
            ),
            "item_status": item.status.value,
            "reservation_advanced": (
                {
                    "reservation_id": head.reservation_id,
                    "status": head.status.value,
                    "reader_id": head.reader_id,
                }
                if head is not None
                else None
            ),
        }

    # ---- 续借（UC-007 / FR-018） ----------------------------------------

    def renew_loan(self, loan_id: int, account, now: datetime | None = None) -> dict:
        """续借。读者仅可续借本人记录，图书管理员可代任意读者续借。"""
        moment = now or utc_now()
        with self._uow:
            loan = self._loans.find_by_id(loan_id)
            if loan is None:
                raise NotFoundError("借阅记录不存在", code="LOAN_NOT_FOUND")

            role = getattr(account, "ROLE", ROLE_READER)
            if role == ROLE_READER and getattr(account, "reader_id", None) != loan.reader_id:
                raise ForbiddenError("只能续借本人的借阅记录")

            reader = self._readers.find_active_by_id(loan.reader_id)
            if reader is None:
                raise NotFoundError("读者不存在", code="READER_NOT_FOUND")

            loans = list(self._loans.find_active_by_reader(reader.reader_id))
            reservations = list(self._reservations.find_active_by_reader(reader.reader_id))
            policy = self._policies.get_borrow_policy()

            # 存在预约排队不影响续借（BR-018）——reservations 不参与判定
            self._renewal.renew(loan, reader, loans, reservations, policy, now=moment)
            self._loans.update(loan)
            self._uow.commit()

        return {
            "loan_id": loan.loan_id,
            "due_at": loan.due_at,
            "renew_count": loan.renew_count,
            "status": loan.persisted_status.value,
        }

    # ---- 收缴罚款（UC-104 / FR-026） ------------------------------------

    def collect_fine(self, fine_id: int, operator: Librarian | SystemAdmin) -> dict:
        """线下收取罚款后标记为 `PAID`（BR-031）。"""
        with self._uow:
            record = self._fines.find_by_id(fine_id)
            if record is None:
                raise NotFoundError("罚款记录不存在", code="FINE_NOT_FOUND")
            record.pay(operator)
            self._fines.update(record)
            self._uow.commit()

        return {
            "fine_id": record.fine_id,
            "status": record.status.value,
            "paid_at": record.paid_at,
            "operator_id": record.operator_id,
            "operator_role": record.operator_role,
        }


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------

class _DummyReader:
    """仅用于"借阅证不存在"分支的占位读者。

    该分支会在 `validate_card` 处立即失败并抛 `CARD_INVALID`，
    读者对象的其余属性不会被读取。这样写的目的是**保证校验顺序**：
    借阅证校验必须先于副本校验，不能被数据加载顺序打乱。
    """

    reader_id = None
    is_deleted = False

    def borrow_limit(self, policy) -> int:  # pragma: no cover - 不会被调用
        return 0

    def borrow_days(self, policy) -> int:  # pragma: no cover
        return 0

    def occupies_quota(self, loans, reservations) -> int:  # pragma: no cover
        return 0


_DUMMY_READER = _DummyReader()


def _as_dict(result) -> dict:
    return {
        "step": result.step,
        "ok": result.ok,
        "code": result.code,
        "message": result.message,
        "detail": result.detail,
    }


def _empty_alerts() -> dict:
    return {"has_overdue": False, "has_unpaid_fine": False, "has_due_soon": False}


def _has_due_soon(loans, now: datetime, within_days: int = 3) -> bool:
    from datetime import timedelta

    threshold = now + timedelta(days=within_days)
    return any(loan.is_open() and now <= loan.due_at <= threshold for loan in loans)
