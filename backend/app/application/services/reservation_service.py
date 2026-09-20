"""`ReservationService`（`09-design-model.md` §4）。

预约的创建、取消与查询。队列规则全部委托 `ReservationQueueService`。
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.application.exceptions import ForbiddenError
from app.application.ports import (
    CardRepository,
    CatalogRepository,
    LoanRepository,
    PolicyRepository,
    ReaderRepository,
    ReservationRepository,
)
from app.application.unit_of_work import UnitOfWork
from app.domain.domain_services import ReservationQueueService
from app.domain.entities.reservation import Reservation
from app.domain.enums import ItemStatus
from app.domain.exceptions import BusinessRuleError, NotFoundError


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ReservationService:
    """预约应用服务。"""

    def __init__(
        self,
        uow: UnitOfWork,
        readers: ReaderRepository,
        cards: CardRepository,
        catalog: CatalogRepository,
        reservations: ReservationRepository,
        loans: LoanRepository,
        policies: PolicyRepository,
    ) -> None:
        self._uow = uow
        self._readers = readers
        self._cards = cards
        self._catalog = catalog
        self._reservations = reservations
        self._loans = loans
        self._policies = policies
        self._queue = ReservationQueueService()

    # ---- 预约（UC-005 / FR-021） ----------------------------------------

    def create_reservation(self, reader_id: int, title_id: int, now: datetime | None = None) -> dict:
        """创建预约。

        预约人取自 **JWT 身份**，不接受请求体中的 `reader_id`（BR-039）。
        """
        moment = now or utc_now()
        with self._uow:
            reader = self._readers.find_active_by_id(reader_id)
            if reader is None:
                raise NotFoundError("读者不存在", code="READER_NOT_FOUND")

            # 无有效借阅证不可预约（FR-021 验收 5、BR-012）
            card = self._cards.find_active_by_reader(reader_id)
            if card is None or not card.is_valid():
                raise BusinessRuleError(
                    "读者无有效借阅证，不可预约", code="CARD_REQUIRED", http_status=400
                )

            title = self._catalog.find_title_by_id(title_id)
            if title is None or title.is_deleted:
                raise NotFoundError("图书标题不存在", code="TITLE_NOT_FOUND")

            # 额度校验：占用额度 ≥ 上限时禁止借书与预约（BR-008）
            loans = list(self._loans.find_active_by_reader(reader_id))
            active_reservations = list(self._reservations.find_active_by_reader(reader_id))
            policy = self._policies.get_borrow_policy()
            if reader.occupies_quota(loans, active_reservations) >= reader.borrow_limit(policy):
                raise BusinessRuleError(
                    "超出借阅数量上限，不可预约",
                    code="BORROW_LIMIT_EXCEEDED",
                    http_status=400,
                )

            # 可借性 / 重复 / 容量（BR-020、BR-023、BR-022）
            queue = list(self._reservations.find_active_by_title(title_id))
            self._queue.can_reserve_or_raise(
                title, queue, reader_id=reader_id, has_available_item=title.has_available_item()
            )

            reservation = Reservation.create(reader, title, now=moment)
            self._reservations.add(reservation)
            self._uow.commit()

        queue = list(self._reservations.find_active_by_title(title_id))
        return self._serialize(reservation, queue)

    # ---- 取消（UC-006 / FR-022） ----------------------------------------

    def cancel_reservation(self, reservation_id: int, account) -> dict:
        """取消预约。**`ACTIVE` 与 `READY` 均可取消**（BR-025a）。

        若该预约持有 `RESERVED` 副本，副本**转交下一位预约者**并保持 `RESERVED`；
        队列无有效预约时才释放为 `AVAILABLE`（BR-024a）。
        """
        moment = utc_now()
        with self._uow:
            reservation = self._reservations.find_by_id(reservation_id)
            if reservation is None:
                raise NotFoundError("预约记录不存在", code="RESERVATION_NOT_FOUND")

            if getattr(account, "reader_id", None) != reservation.reader_id:
                raise ForbiddenError("只能取消本人的预约")

            was_ready = reservation.status.value == "READY"
            title_id = reservation.title_id
            reservation.cancel()
            self._reservations.update(reservation)

            advanced = None
            if was_ready:
                # 该预约持有的副本需要交接
                item = self._find_reserved_item(title_id)
                queue = list(self._reservations.find_active_by_title(title_id))
                head = self._queue.handover(queue, item=None, now=moment)
                if head is not None:
                    self._reservations.update(head)
                    if item is not None:
                        item.mark_reserved()  # 副本保持 RESERVED，归属转给新队首
                        self._catalog.update_item(item)
                    advanced = {"reservation_id": head.reservation_id, "status": head.status.value}
                elif item is not None:
                    # 队列已空，副本释放为 AVAILABLE
                    item.release_reservation()
                    self._catalog.update_item(item)

            self._uow.commit()

        return {
            "reservation_id": reservation.reservation_id,
            "status": reservation.status.value,
            "advanced_to": advanced,
        }

    # ---- 查询（FR-024 / UC-004 步骤 5） ---------------------------------

    def list_by_reader(self, reader_id: int, only_active: bool = False) -> list[dict]:
        moment = utc_now()
        records = (
            list(self._reservations.find_active_by_reader(reader_id))
            if only_active
            else list(self._reservations.find_by_reader(reader_id))
        )
        queue = list(self._reservations.find_active_by_reader(reader_id))
        return [self._serialize(record, queue, moment) for record in records]

    # ---- 内部 ------------------------------------------------------------

    def _serialize(self, reservation: Reservation, queue: list[Reservation], now=None) -> dict:
        moment = now or utc_now()
        return {
            "reservation_id": reservation.reservation_id,
            "title_id": reservation.title_id,
            "reader_id": reservation.reader_id,
            "status": reservation.status.value,
            "created_at": reservation.created_at,
            "ready_at": reservation.ready_at,
            "queue_position": reservation.queue_position(queue),
            "expires_at": reservation.expires_at(),
            "is_expired": reservation.is_expired(moment),
        }

    def _find_reserved_item(self, title_id: int):
        for item in self._catalog.find_items_by_title(title_id):
            if item.status is ItemStatus.RESERVED:
                return item
        return None
