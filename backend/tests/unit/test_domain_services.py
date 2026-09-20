"""领域服务单元测试（TASK-006 验收标准）。

重点验证**校验顺序固定**与**额度口径含预约**——
这两点是最容易被实现错的。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.domain_services import (
    BorrowEligibilityService,
    RenewalService,
    ReservationQueueService,
)
from app.domain.domain_services.borrow_eligibility_service import CHECK_ORDER
from app.domain.entities.borrow_card import BorrowCard
from app.domain.entities.fine_record import FineRecord
from app.domain.entities.library_item import Book
from app.domain.entities.loan import Loan
from app.domain.entities.reader import StudentReader, SystemAdmin
from app.domain.entities.reservation import Reservation
from app.domain.enums import FineStatus, ItemStatus, ItemType, ReaderType
from app.domain.exceptions import BusinessRuleError, ValidationError
from app.domain.policies import BorrowPolicy
from app.domain.value_objects import Barcode, CardNumber, Money

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)

POLICY = BorrowPolicy.from_rows(
    [
        {"reader_type": "COLLEGE", "max_borrow_count": 5, "borrow_days": 30},
        {"reader_type": "UNDERGRADUATE", "max_borrow_count": 5, "borrow_days": 30},
        {"reader_type": "GRADUATE", "max_borrow_count": 10, "borrow_days": 60},
        {"reader_type": "DOCTOR", "max_borrow_count": 15, "borrow_days": 90},
        {"reader_type": "TEACHER", "max_borrow_count": 20, "borrow_days": 90},
    ]
)


def reader(reader_type: ReaderType = ReaderType.UNDERGRADUATE, reader_id: int = 10) -> StudentReader:
    return StudentReader(
        reader_id=reader_id,
        name="张三",
        department="计算机",
        reader_type=reader_type,
        student_type=reader_type,
    )


def card(status: str = "ACTIVE", reader_id: int = 10) -> BorrowCard:
    return BorrowCard(
        card_no=CardNumber.generate(2026, 1), reader_id=reader_id, card_id=1, status=status
    )


def item(status: ItemStatus = ItemStatus.AVAILABLE) -> Book:
    return Book(
        barcode=Barcode.generate(1), title_id=1, item_id=1, status=status,
        item_type=ItemType.FOREIGN_BOOK,
    )


def loan(reader_id: int = 10, days_until_due: int = 10, loan_id: int = 1) -> Loan:
    return Loan(
        loan_id=loan_id,
        reader_id=reader_id,
        item_id=loan_id,
        borrowed_at=NOW - timedelta(days=1),
        due_at=NOW + timedelta(days=days_until_due),
        status="BORROWED",
    )


def unpaid_fine(reader_id: int = 10) -> FineRecord:
    return FineRecord(
        fine_id=1, loan_id=1, reader_id=reader_id, amount=Money.of("0.50"), status=FineStatus.UNPAID
    )


def reservation(status: str = "ACTIVE", reader_id: int = 10, reservation_id: int = 1) -> Reservation:
    return Reservation(
        reservation_id=reservation_id, reader_id=reader_id, title_id=1, created_at=NOW, status=status
    )


@pytest.fixture()
def service() -> BorrowEligibilityService:
    return BorrowEligibilityService()


# ---------------------------------------------------------------------------
# 单项校验
# ---------------------------------------------------------------------------

class TestIndividualChecks:
    def test_validate_card(self, service):
        assert service.validate_card(card()).ok is True
        assert service.validate_card(None).code == "CARD_INVALID"
        assert service.validate_card(card("SUSPENDED")).code == "CARD_INVALID"
        assert service.validate_card(card("CANCELLED")).code == "CARD_INVALID"

    def test_check_quota_boundary(self, service):
        """上限 5：占 4 通过，占 5 拒绝（BR-008 用 ≥）。"""
        undergraduate = reader(ReaderType.UNDERGRADUATE)
        four = [loan(loan_id=i) for i in range(1, 5)]
        five = [loan(loan_id=i) for i in range(1, 6)]

        assert service.check_quota(undergraduate, four, [], POLICY).ok is True
        result = service.check_quota(undergraduate, five, [], POLICY)
        assert result.ok is False
        assert result.code == "BORROW_LIMIT_EXCEEDED"
        assert result.detail == {"current": 5, "limit": 5}

    def test_quota_counts_reservations_too(self, service):
        """BR-007：额度口径 = 未归还借阅 + **有效预约**。"""
        undergraduate = reader(ReaderType.UNDERGRADUATE)
        loans = [loan(loan_id=i) for i in range(1, 5)]          # 4 借阅
        reservations = [reservation(reservation_id=1)]           # 1 预约 → 共 5
        result = service.check_quota(undergraduate, loans, reservations, POLICY)
        assert result.ok is False
        assert result.detail["current"] == 5

    def test_returned_loans_do_not_occupy(self, service):
        undergraduate = reader(ReaderType.UNDERGRADUATE)
        returned = Loan(loan_id=1, reader_id=10, item_id=1, status="RETURNED")
        assert service.check_quota(undergraduate, [returned], [], POLICY).ok is True

    def test_expired_reservations_do_not_occupy(self, service):
        undergraduate = reader(ReaderType.UNDERGRADUATE)
        expired = reservation(status="EXPIRED")
        loans = [loan(loan_id=i) for i in range(1, 6)]
        # 5 笔借阅已达上限，失效预约不改变结论
        assert service.check_quota(undergraduate, loans, [expired], POLICY).ok is False

    def test_check_overdue(self, service):
        assert service.check_overdue([loan(days_until_due=5)], NOW).ok is True
        overdue = loan(days_until_due=-3)
        result = service.check_overdue([overdue], NOW)
        assert result.ok is False
        assert result.code == "OVERDUE_LOAN_EXISTS"

    def test_returned_overdue_loan_not_counted(self, service):
        returned = Loan(
            loan_id=1, reader_id=10, item_id=1,
            due_at=NOW - timedelta(days=5), returned_at=NOW - timedelta(days=1), status="RETURNED",
        )
        assert service.check_overdue([returned], NOW).ok is True

    def test_check_unpaid_fine(self, service):
        assert service.check_unpaid_fine([]).ok is True
        result = service.check_unpaid_fine([unpaid_fine()])
        assert result.ok is False
        assert result.code == "UNPAID_FINE_EXISTS"

    def test_paid_fine_does_not_block(self, service):
        paid = FineRecord(
            fine_id=1, loan_id=1, reader_id=10, amount=Money.of("0.50"), status=FineStatus.PAID
        )
        assert service.check_unpaid_fine([paid]).ok is True

    @pytest.mark.parametrize("status", ["BORROWED", "RESERVED", "LOST", "DAMAGED", "REMOVED"])
    def test_check_item_rejects_non_available(self, service, status):
        result = service.check_item(item(ItemStatus(status)))
        assert result.ok is False
        assert result.code == "ITEM_NOT_AVAILABLE"

    def test_check_item_missing(self, service):
        assert service.check_item(None).code == "ITEM_NOT_AVAILABLE"


# ---------------------------------------------------------------------------
# 组合判定的顺序
# ---------------------------------------------------------------------------

class TestFixedOrder:
    def test_check_order_constant(self):
        assert CHECK_ORDER == ("card", "quota", "overdue", "fine", "item")

    def test_first_failure_wins_card_before_quota(self, service):
        """全部条件都失败时，必须报**第一个**——借阅证（CARD_INVALID）。"""
        undergraduate = reader(ReaderType.UNDERGRADUATE)
        with pytest.raises(ValidationError) as exc:
            service.check_and_raise(
                undergraduate,
                card("CANCELLED"),
                [loan(loan_id=i) for i in range(1, 6)],
                [],
                [unpaid_fine()],
                POLICY,
                item(ItemStatus.BORROWED),
                NOW,
            )
        assert exc.value.code == "CARD_INVALID"

    def test_quota_before_overdue(self, service):
        """借阅证有效时，额度先于超期报告。"""
        undergraduate = reader(ReaderType.UNDERGRADUATE)
        loans = [loan(loan_id=i) for i in range(1, 6)] + [loan(loan_id=99, days_until_due=-5)]
        with pytest.raises(BusinessRuleError) as exc:
            service.check_and_raise(
                undergraduate, card(), loans, [], [], POLICY, item(), NOW
            )
        assert exc.value.code == "BORROW_LIMIT_EXCEEDED"

    def test_overdue_before_fine(self, service):
        undergraduate = reader(ReaderType.UNDERGRADUATE)
        with pytest.raises(BusinessRuleError) as exc:
            service.check_and_raise(
                undergraduate,
                card(),
                [loan(days_until_due=-5)],
                [],
                [unpaid_fine()],
                POLICY,
                item(),
                NOW,
            )
        assert exc.value.code == "OVERDUE_LOAN_EXISTS"

    def test_fine_before_item(self, service):
        undergraduate = reader(ReaderType.UNDERGRADUATE)
        with pytest.raises(BusinessRuleError) as exc:
            service.check_and_raise(
                undergraduate,
                card(),
                [],
                [],
                [unpaid_fine()],
                POLICY,
                item(ItemStatus.LOST),
                NOW,
            )
        assert exc.value.code == "UNPAID_FINE_EXISTS"

    def test_all_pass_returns_none(self, service):
        undergraduate = reader(ReaderType.UNDERGRADUATE)
        assert (
            service.check_and_raise(undergraduate, card(), [], [], [], POLICY, item(), NOW) is None
        )

    def test_check_all_reports_every_step(self, service):
        """`check_all` 返回全部五项（供预检查 FR-015 使用），不提前退出。"""
        undergraduate = reader(ReaderType.UNDERGRADUATE)
        results = service.check_all(
            undergraduate, card(), [], [], [], POLICY, item(), NOW
        )
        assert [result.step for result in results] == list(CHECK_ORDER)
        assert all(result.ok for result in results)

    def test_business_rule_failures_use_400(self, service):
        """FR-016 验收标准 2：业务规则失败为 400，不是 409。"""
        undergraduate = reader(ReaderType.UNDERGRADUATE)
        with pytest.raises(BusinessRuleError) as exc:
            service.check_and_raise(
                undergraduate,
                card(),
                [loan(loan_id=i) for i in range(1, 6)],
                [],
                [],
                POLICY,
                item(),
                NOW,
            )
        assert exc.value.http_status == 400


# ---------------------------------------------------------------------------
# 续借服务
# ---------------------------------------------------------------------------

class TestRenewalService:
    def test_can_renew_when_clean(self):
        assert RenewalService.can_renew(loan(), reader(), [loan()], [], POLICY, NOW) is True

    def test_cannot_renew_when_overdue(self):
        overdue = loan(days_until_due=-2)
        assert RenewalService.can_renew(overdue, reader(), [overdue], [], POLICY, NOW) is False

    def test_cannot_renew_when_limit_reached(self):
        full = loan()
        full.renew_count = 2
        assert RenewalService.can_renew(full, reader(), [full], [], POLICY, NOW) is False

    def test_cannot_renew_when_returned(self):
        returned = Loan(loan_id=1, reader_id=10, item_id=1, status="RETURNED")
        assert RenewalService.can_renew(returned, reader(), [returned], [], POLICY, NOW) is False

    def test_reservations_do_not_block_renewal(self):
        """BR-018：存在预约排队**不构成**禁止续借的条件。"""
        other_reader_reservations = [reservation(reader_id=99, reservation_id=5)]
        assert (
            RenewalService.can_renew(loan(), reader(), [loan()], other_reader_reservations, POLICY, NOW)
            is True
        )

    def test_renew_extends_and_increments(self):
        target = loan()
        RenewalService.renew(target, reader(), [target], [], POLICY, NOW)
        assert target.renew_count == 1
        assert target.due_at == NOW + timedelta(days=17)  # 10 + 7

    def test_renew_raises_renew_overdue(self):
        overdue = loan(days_until_due=-2)
        with pytest.raises(BusinessRuleError) as exc:
            RenewalService.renew(overdue, reader(), [overdue], [], POLICY, NOW)
        assert exc.value.code == "RENEW_OVERDUE"

    def test_renew_raises_renew_limit_exceeded(self):
        full = loan()
        full.renew_count = 2
        with pytest.raises(BusinessRuleError) as exc:
            RenewalService.renew(full, reader(), [full], [], POLICY, NOW)
        assert exc.value.code == "RENEW_LIMIT_EXCEEDED"

    def test_renew_raises_when_quota_exceeded(self):
        """BR-017：占用额度超上限时不可续借。"""
        undergraduate = reader(ReaderType.UNDERGRADUATE)
        loans = [loan(loan_id=i) for i in range(1, 7)]  # 6 > 上限 5
        target = loans[0]
        with pytest.raises(BusinessRuleError) as exc:
            RenewalService.renew(target, undergraduate, loans, [], POLICY, NOW)
        assert exc.value.code == "BORROW_LIMIT_EXCEEDED"


# ---------------------------------------------------------------------------
# 预约队列服务
# ---------------------------------------------------------------------------

class TestReservationQueueService:
    MAX = 5

    @pytest.fixture()
    def queue(self) -> ReservationQueueService:
        return ReservationQueueService()

    def _filled_queue(self, count: int) -> list[Reservation]:
        return [
            Reservation(
                reservation_id=i,
                reader_id=100 + i,
                title_id=1,
                created_at=NOW + timedelta(minutes=i),
                status="ACTIVE",
            )
            for i in range(1, count + 1)
        ]

    def test_peek_returns_earliest(self, queue):
        records = self._filled_queue(3)
        assert queue.peek(list(reversed(records))).reader_id == 101

    def test_peek_empty(self, queue):
        assert queue.peek([]) is None

    def test_position(self, queue):
        records = self._filled_queue(3)
        assert queue.position_of(records[1], records) == 2

    def test_can_reserve_requires_no_available_item(self, queue):
        """BR-020：有可借副本时拒绝预约，错误码 `ITEM_AVAILABLE_NO_RESERVATION` 且为 400。"""
        result = queue.can_reserve(None, [], has_available_item=True)
        assert result.code == "ITEM_AVAILABLE_NO_RESERVATION"

    def test_can_reserve_rejects_duplicate(self, queue):
        """BR-023：同一读者不得重复预约。"""
        existing = self._filled_queue(2)
        result = queue.can_reserve(None, existing, reader_id=101, has_available_item=False)
        assert result.code == "DUPLICATE_RESERVATION"

    def test_can_reserve_rejects_full_queue(self, queue):
        """BR-022：队列上限 5 人。"""
        existing = self._filled_queue(5)
        result = queue.can_reserve(None, existing, reader_id=999, has_available_item=False)
        assert result.code == "RESERVATION_QUEUE_FULL"

    def test_can_reserve_passes_at_four(self, queue):
        existing = self._filled_queue(4)
        result = queue.can_reserve(None, existing, reader_id=999, has_available_item=False)
        assert result.ok is True

    def test_ignores_title_none_with_available_flag(self, queue):
        """`title=None` 且显式给出可借性时不报 TITLE_NOT_FOUND（便于纯队列测试）。"""
        assert queue.can_reserve(None, [], has_available_item=False).ok is True

    def test_dequeue_expired_marks_and_returns(self, queue):
        records = self._filled_queue(3)
        records[0].created_at = NOW - timedelta(days=8)  # 已超 7 天
        expired = queue.dequeue_expired(records, NOW)
        assert len(expired) == 1
        assert expired[0].status.value == "EXPIRED"
        assert queue.peek(records).reader_id == 102

    def test_handover_advances_head_and_reserves_item(self, queue):
        """BR-024a：队首置 `READY`，副本置 `RESERVED`。"""
        records = self._filled_queue(2)
        target_item = item()
        head = queue.handover(records, target_item, NOW)
        assert head.reader_id == 101
        assert head.status.value == "READY"
        assert head.ready_at == NOW
        assert target_item.status is ItemStatus.RESERVED

    def test_handover_skips_expired_head(self, queue):
        """BR-025b：失效判定与顺延在同一调用内完成。"""
        records = self._filled_queue(2)
        records[0].created_at = NOW - timedelta(days=9)
        head = queue.handover(records, item(), NOW)
        assert head.reader_id == 102
        assert records[0].status.value == "EXPIRED"

    def test_handover_returns_none_when_queue_empty(self, queue):
        assert queue.handover([], item(), NOW) is None

    def test_handover_keeps_item_reserved_on_second_handover(self, queue):
        """BR-024a：队首取消后转交下一位，副本**保持** `RESERVED`。"""
        records = self._filled_queue(2)
        target_item = item()
        queue.handover(records, target_item, NOW)
        records[0].cancel()

        head = queue.handover(records, target_item, NOW)
        assert head.reader_id == 102
        assert target_item.status is ItemStatus.RESERVED  # 未释放为 AVAILABLE
