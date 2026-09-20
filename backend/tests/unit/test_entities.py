"""领域实体单元测试（TC-020b 后半）。

覆盖三个状态机与两个关键行为：

- `BorrowCard`：`ACTIVE` ⇄ `SUSPENDED`，`ACTIVE`/`SUSPENDED` → `CANCELLED` → `ACTIVE`
- `LibraryItem`：`AVAILABLE` → `BORROWED` → `RESERVED`/`AVAILABLE`，非法流转必须被拒绝
- `Loan`：超期计算、续借边界、`OVERDUE` 不落库
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.entities.book_title import BookTitle
from app.domain.entities.borrow_card import BorrowCard
from app.domain.entities.fine_record import FineRecord
from app.domain.entities.library_item import Book, Magazine, Thesis
from app.domain.entities.loan import Loan
from app.domain.entities.reader import StudentReader, SystemAdmin, TeacherReader
from app.domain.entities.reservation import Reservation
from app.domain.enums import CardStatus, FineStatus, ItemStatus, ItemType, LoanStatus, ReaderType
from app.domain.exceptions import BusinessRuleError, ValidationError
from app.domain.factories import LibraryItemFactory, ReaderFactory
from app.domain.policies import BorrowPolicy, FineRule
from app.domain.value_objects import Barcode, CardNumber

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

FINE_RULE = FineRule.from_rows(
    [
        {"item_type": "FOREIGN_BOOK", "daily_price": "0.50", "grace_days": 2, "max_amount": "100.00"}
    ]
)


def make_admin() -> SystemAdmin:
    return SystemAdmin(admin_id=1, name="管理员", username="admin", password_hash="x")


def make_reader(**kwargs) -> StudentReader:
    defaults = dict(reader_id=10, name="张三", department="计算机", reader_type=ReaderType.GRADUATE)
    defaults.update(kwargs)
    return StudentReader(student_type=ReaderType.GRADUATE, **defaults)


def make_item(barcode: str = "BC00000001", status: ItemStatus = ItemStatus.AVAILABLE) -> Book:
    return Book(
        barcode=Barcode.parse(barcode),
        title_id=1,
        item_id=5,
        status=status,
        item_type=ItemType.FOREIGN_BOOK,
    )


# ---------------------------------------------------------------------------
# 工厂
# ---------------------------------------------------------------------------

class TestFactories:
    def test_reader_factory_dispatch(self):
        assert isinstance(ReaderFactory.create("GRADUATE"), StudentReader)
        assert isinstance(ReaderFactory.create("TEACHER"), TeacherReader)

    def test_library_item_factory_attaches_to_title(self):
        title = BookTitle(title_id=1, title="算法导论", item_type=ItemType.FOREIGN_BOOK)
        item = LibraryItemFactory.create(title, Barcode.generate(1))
        assert item in title.items
        assert item.item_type is ItemType.FOREIGN_BOOK
        assert item.status is ItemStatus.AVAILABLE

    def test_library_item_factory_subclasses(self):
        assert LibraryItemFactory.subclass_for("CHINESE_BOOK") is Book
        assert LibraryItemFactory.subclass_for("CHINESE_MAGAZINE") is Magazine
        assert LibraryItemFactory.subclass_for("THESIS") is Thesis

    def test_library_item_factory_requires_type(self):
        title = BookTitle(title_id=1, title="无类型")
        with pytest.raises(ValidationError):
            LibraryItemFactory.create(title, Barcode.generate(1))


# ---------------------------------------------------------------------------
# 借阅证状态机
# ---------------------------------------------------------------------------

class TestBorrowCardStateMachine:
    def _card(self) -> BorrowCard:
        return BorrowCard.issue(make_reader(), make_admin(), CardNumber.generate(2026, 1))

    def test_issue_sets_active(self):
        card = self._card()
        assert card.status is CardStatus.ACTIVE
        assert card.is_valid() is True

    def test_active_to_suspended_and_back(self):
        admin = make_admin()
        card = self._card()
        card.suspend(admin)
        assert card.status is CardStatus.SUSPENDED
        assert card.is_valid() is False
        card.resume(admin)
        assert card.status is CardStatus.ACTIVE

    def test_active_to_cancelled_to_restored(self):
        admin = make_admin()
        card = self._card()
        card.cancel(admin)
        assert card.status is CardStatus.CANCELLED
        assert card.cancelled_at is not None
        card.restore(admin)
        assert card.status is CardStatus.ACTIVE
        assert card.cancelled_at is None

    def test_illegal_transitions_rejected(self):
        admin = make_admin()
        card = self._card()
        with pytest.raises(ValidationError):
            card.restore(admin)          # ACTIVE 不可"恢复"
        card.suspend(admin)
        with pytest.raises(ValidationError):
            card.suspend(admin)          # 已挂失不可再挂失
        card.cancel(admin)
        with pytest.raises(ValidationError):
            card.cancel(admin)           # 已注销不可再注销
        with pytest.raises(ValidationError):
            card.suspend(admin)          # 已注销不可挂失

    def test_one_card_limit_semantics(self):
        """BR-003：`ACTIVE`/`SUSPENDED` 计入，`CANCELLED` 不计入。"""
        admin = make_admin()
        card = self._card()
        assert card.counts_towards_one_card_limit() is True
        card.suspend(admin)
        assert card.counts_towards_one_card_limit() is True
        card.cancel(admin)
        assert card.counts_towards_one_card_limit() is False

    def test_status_is_read_only(self):
        """状态字段对外只读——只能经实体方法流转。"""
        card = self._card()
        with pytest.raises(AttributeError):
            card.status = CardStatus.CANCELLED

    def test_issue_requires_admin(self):
        class NotAdmin:
            admin_id = None

            def may_manage_cards(self) -> bool:
                return False

        with pytest.raises(PermissionError):
            BorrowCard.issue(make_reader(), NotAdmin(), CardNumber.generate(2026, 1))


# ---------------------------------------------------------------------------
# 副本状态机
# ---------------------------------------------------------------------------

class TestLibraryItemStateMachine:
    def test_borrow_requires_available(self):
        item = make_item()
        item.mark_borrowed()
        assert item.status is ItemStatus.BORROWED
        with pytest.raises(ValidationError):
            item.mark_borrowed()  # 已借出不可再借

    def test_return_without_reservation_releases_to_available(self):
        item = make_item()
        item.mark_borrowed()
        item.mark_returned(has_reservation=False)
        assert item.status is ItemStatus.AVAILABLE

    def test_return_with_reservation_becomes_reserved(self):
        item = make_item()
        item.mark_borrowed()
        item.mark_returned(has_reservation=True)
        assert item.status is ItemStatus.RESERVED

    def test_release_reservation(self):
        item = make_item(status=ItemStatus.RESERVED)
        item.release_reservation()
        assert item.status is ItemStatus.AVAILABLE

    def test_borrowed_cannot_be_removed(self):
        """BR-034 / FR-013 验收 4：在借副本不允许直接删除。"""
        item = make_item()
        item.mark_borrowed()
        with pytest.raises(ValidationError):
            item.remove()

    def test_available_can_be_removed(self):
        item = make_item()
        item.remove()
        assert item.status is ItemStatus.REMOVED

    @pytest.mark.parametrize("status", [ItemStatus.LOST, ItemStatus.DAMAGED, ItemStatus.REMOVED])
    def test_not_borrowable_statuses(self, status):
        item = make_item(status=status)
        assert item.is_available() is False

    def test_lost_then_restore(self):
        item = make_item()
        item.mark_lost()
        assert item.status is ItemStatus.LOST
        item.mark_available()
        assert item.status is ItemStatus.AVAILABLE

    def test_rehydrate_dispatches_subclass(self):
        from app.domain.entities.library_item import LibraryItem

        restored = LibraryItem.rehydrate(
            barcode="BC00000009", title_id=1, item_id=9, item_type="THESIS",
            status="AVAILABLE",
        )
        assert isinstance(restored, Thesis)


# ---------------------------------------------------------------------------
# BookTitle 聚合
# ---------------------------------------------------------------------------

class TestBookTitle:
    def test_availability_queries(self):
        title = BookTitle(title_id=1, title="算法导论", item_type=ItemType.FOREIGN_BOOK)
        LibraryItemFactory.create(title, Barcode.generate(1))
        LibraryItemFactory.create(title, Barcode.generate(2))
        assert title.total_items() == 2
        assert len(title.available_items()) == 2
        assert title.has_available_item() is True

    def test_can_be_reserved_only_when_none_available(self):
        title = BookTitle(title_id=1, title="算法导论", item_type=ItemType.FOREIGN_BOOK)
        first = LibraryItemFactory.create(title, Barcode.generate(1))
        assert title.can_be_reserved() is False  # 仍有可借副本（BR-020）
        first.mark_borrowed()
        assert title.can_be_reserved() is True

    def test_zero_copy_title_satisfies_br020_literally(self):
        """BR-020 字面含义：无副本时"所有副本均不可借"成立，故不排除零副本题录。"""
        title = BookTitle(title_id=1, title="待采购", item_type=ItemType.FOREIGN_BOOK)
        assert title.can_be_reserved() is True

    def test_deleted_title_cannot_be_reserved(self):
        title = BookTitle(title_id=1, title="已下架", item_type=ItemType.FOREIGN_BOOK, is_deleted=True)
        assert title.can_be_reserved() is False

    def test_remove_cascades_to_unborrowed_items(self):
        """FR-011 验收 3：题录软删除时未借出副本同步置 `REMOVED`。"""
        title = BookTitle(title_id=1, title="算法导论", item_type=ItemType.FOREIGN_BOOK)
        available = LibraryItemFactory.create(title, Barcode.generate(1))
        borrowed = LibraryItemFactory.create(title, Barcode.generate(2))
        borrowed.mark_borrowed()

        title.remove()

        assert title.is_deleted is True
        assert available.status is ItemStatus.REMOVED
        assert borrowed.status is ItemStatus.BORROWED  # FR-011 验收 4：不阻塞删除


# ---------------------------------------------------------------------------
# Loan
# ---------------------------------------------------------------------------

class TestLoan:
    def _loan(self, **kwargs) -> Loan:
        """构造一条基于 `NOW` 的借阅记录；`kwargs` 可覆盖任意字段。"""
        base = Loan.create(make_reader(), make_item(), POLICY, librarian=None, now=NOW)
        fields = {
            "loan_id": 1,
            "reader_id": base.reader_id,
            "item_id": base.item_id,
            "borrowed_at": base.borrowed_at,
            "due_at": base.due_at,
        }
        fields.update(kwargs)
        return Loan(**fields)

    def test_create_snapshots_due_at(self):
        loan = self._loan()
        assert loan.due_at == NOW + timedelta(days=60)  # GRADUATE 60 天
        assert loan.persisted_status is LoanStatus.BORROWED

    def test_due_at_not_affected_by_later_policy_change(self):
        """BR-050：`due_at` 是快照，规则修改不追溯。"""
        loan = Loan.create(make_reader(), make_item(), POLICY, now=NOW)
        original_due = loan.due_at
        POLICY.update("GRADUATE", 10, 90)
        assert loan.due_at == original_due

    @pytest.mark.parametrize(
        "offset_days,expected_overdue,expected_days",
        [(-1, False, 0), (0, False, 0), (1, True, 1), (21, True, 21)],
    )
    def test_overdue_calculation(self, offset_days, expected_overdue, expected_days):
        loan = self._loan()
        moment = loan.due_at + timedelta(days=offset_days)
        assert loan.is_overdue(moment) is expected_overdue
        assert loan.overdue_days(moment) == expected_days

    def test_overdue_is_derived_not_persisted(self):
        loan = self._loan()
        later = loan.due_at + timedelta(days=5)
        assert loan.derived_status(later) is LoanStatus.OVERDUE
        assert loan.persisted_status is LoanStatus.BORROWED  # 落库仍是两态
        assert LoanStatus.OVERDUE.is_persistable is False

    def test_renew_extends_seven_days_and_increments(self):
        loan = self._loan()
        original_due = loan.due_at
        loan.renew()
        assert loan.due_at == original_due + timedelta(days=7)
        assert loan.renew_count == 1

    def test_renew_twice_then_rejected(self):
        loan = self._loan()
        loan.renew()
        loan.renew()
        assert loan.renew_count == 2
        with pytest.raises(BusinessRuleError) as exc:
            loan.renew()
        assert exc.value.code == "RENEW_LIMIT_EXCEEDED"

    def test_overdue_loan_cannot_renew(self):
        loan = self._loan(due_at=NOW - timedelta(days=3), borrowed_at=NOW - timedelta(days=63))
        with pytest.raises(BusinessRuleError) as exc:
            loan.renew()
        assert exc.value.code == "RENEW_OVERDUE"

    def test_return_sets_status_and_time(self):
        loan = self._loan()
        loan.return_item(NOW + timedelta(days=10))
        assert loan.persisted_status is LoanStatus.RETURNED
        assert loan.returned_at == NOW + timedelta(days=10)
        assert loan.is_open() is False
        assert loan.is_overdue(NOW + timedelta(days=999)) is False  # 已归还不再算超期

    def test_renew_after_return_rejected(self):
        loan = self._loan()
        loan.return_item(NOW)
        with pytest.raises(ValidationError):
            loan.renew()


# ---------------------------------------------------------------------------
# Reservation
# ---------------------------------------------------------------------------

class TestReservation:
    def _reservation(self, reader_id: int, minutes: int, reservation_id: int) -> Reservation:
        return Reservation(
            reservation_id=reservation_id,
            reader_id=reader_id,
            title_id=1,
            created_at=NOW + timedelta(minutes=minutes),
            status="ACTIVE",
        )

    def test_queue_order_by_created_at_not_id(self):
        """BR-021：按 `created_at` 排序，不依赖自增主键。"""
        first = self._reservation(1, 0, reservation_id=99)   # 早创建但 ID 大
        second = self._reservation(2, 10, reservation_id=1)  # 晚创建但 ID 小
        queue = [second, first]
        assert first.queue_position(queue) == 1
        assert second.queue_position(queue) == 2

    def test_validity_start_differs_by_status(self):
        """BR-025：`ACTIVE` 自 `created_at`，`READY` 自 `ready_at`。"""
        active = self._reservation(1, 0, 1)
        assert active.validity_start() == active.created_at

        ready = self._reservation(2, 0, 2)
        ready.mark_ready(NOW + timedelta(days=3))
        assert ready.validity_start() == ready.ready_at

    def test_expiry_is_lazy(self):
        res = self._reservation(1, 0, 1)
        assert res.is_expired(NOW + timedelta(days=6)) is False
        assert res.is_expired(NOW + timedelta(days=7)) is True

    def test_ready_expiry_counts_from_ready_at(self):
        res = self._reservation(1, 0, 1)
        res.mark_ready(NOW + timedelta(days=5))
        assert res.is_expired(NOW + timedelta(days=11)) is False
        assert res.is_expired(NOW + timedelta(days=12)) is True

    def test_both_active_and_ready_cancellable(self):
        """BR-025a：有效预约均可取消。"""
        active = self._reservation(1, 0, 1)
        active.cancel()
        assert active.status.value == "CANCELLED"

        ready = self._reservation(2, 0, 2)
        ready.mark_ready(NOW)
        ready.cancel()
        assert ready.status.value == "CANCELLED"

    def test_cancelled_cannot_be_cancelled_again(self):
        res = self._reservation(1, 0, 1)
        res.cancel()
        with pytest.raises(ValidationError):
            res.cancel()

    def test_expired_cannot_be_cancelled(self):
        res = self._reservation(1, 0, 1)
        res.expire(NOW)
        with pytest.raises(ValidationError):
            res.cancel()

    def test_effective_status_occupies_quota(self):
        """BR-026：有效预约占用 1 个借阅额度。"""
        assert self._reservation(1, 0, 1).is_active() is True
        expired = self._reservation(1, 0, 1)
        expired.expire(NOW)
        assert expired.is_active() is False


# ---------------------------------------------------------------------------
# FineRecord
# ---------------------------------------------------------------------------

class TestFineRecord:
    def _overdue_loan(self) -> Loan:
        loan = Loan.create(make_reader(), make_item(), POLICY, now=NOW)
        loan.due_at = NOW - timedelta(days=21)
        return loan

    def test_create_snapshots_unit_price_and_days(self):
        loan = self._overdue_loan()
        record = FineRecord.create(loan, ItemType.FOREIGN_BOOK, NOW, FINE_RULE)

        assert record.overdue_days == 21
        assert record.billed_days == 19
        assert record.amount.to_text() == "9.50"
        assert record.unit_price.to_text() == "0.50"
        assert record.status is FineStatus.UNPAID

    def test_unit_price_snapshot_not_affected_by_rule_change(self):
        """BR-050：`unit_price` 快照后，规则修改不影响已有记录。"""
        record = FineRecord.create(self._overdue_loan(), ItemType.FOREIGN_BOOK, NOW, FINE_RULE)
        FINE_RULE.update("FOREIGN_BOOK", "9.99", 2, "100.00")
        assert record.unit_price.to_text() == "0.50"

    def test_unpaid_blocks_borrowing(self):
        record = FineRecord.create(self._overdue_loan(), ItemType.FOREIGN_BOOK, NOW, FINE_RULE)
        assert record.is_unpaid() is True
        assert record.status.blocks_borrowing is True

    @pytest.mark.parametrize("role", [None, "READER"])
    def test_pay_requires_staff_role(self, role):
        record = FineRecord.create(self._overdue_loan(), ItemType.FOREIGN_BOOK, NOW, FINE_RULE)

        class Account:
            ROLE = role
            account_id = 1

        with pytest.raises(PermissionError):
            record.pay(Account())

    def test_pay_records_operator(self):
        from app.domain.entities.reader import Librarian

        record = FineRecord.create(self._overdue_loan(), ItemType.FOREIGN_BOOK, NOW, FINE_RULE)
        librarian = Librarian(librarian_id=7, name="馆员", username="lib")
        record.pay(librarian)

        assert record.status is FineStatus.PAID
        assert record.paid_at is not None
        assert record.operator_id == 7
        assert record.operator_role == "LIBRARIAN"
        assert record.is_unpaid() is False

    def test_double_pay_rejected(self):
        from app.domain.entities.reader import Librarian

        record = FineRecord.create(self._overdue_loan(), ItemType.FOREIGN_BOOK, NOW, FINE_RULE)
        librarian = Librarian(librarian_id=7, name="馆员", username="lib")
        record.pay(librarian)
        with pytest.raises(ValidationError):
            record.pay(librarian)


# ---------------------------------------------------------------------------
# 读者额度占用
# ---------------------------------------------------------------------------

class TestReaderQuota:
    def test_occupies_quota_counts_loans_and_reservations(self):
        """BR-007：额度 = 未归还借阅 + 有效预约。"""
        reader = make_reader()
        loans = [
            Loan(loan_id=1, reader_id=10, item_id=1, status="BORROWED"),
            Loan(loan_id=2, reader_id=10, item_id=2, status="BORROWED"),
            Loan(loan_id=3, reader_id=10, item_id=3, status="RETURNED"),
        ]
        reservations = [
            Reservation(reservation_id=1, reader_id=10, title_id=1, status="ACTIVE"),
            Reservation(reservation_id=2, reader_id=10, title_id=2, status="EXPIRED"),
        ]
        assert reader.occupies_quota(loans, reservations) == 3

    def test_remaining_quota(self):
        reader = make_reader()  # GRADUATE：上限 10
        loans = [Loan(loan_id=1, reader_id=10, item_id=1, status="BORROWED")]
        assert reader.remaining_quota(loans, [], POLICY) == 9

    def test_teacher_has_highest_limit(self):
        teacher = TeacherReader(reader_id=1, reader_type=ReaderType.TEACHER)
        assert teacher.borrow_limit(POLICY) == 20
