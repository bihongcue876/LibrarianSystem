"""ReservationQueueService（`05-domain-model.md` §6.3）。

负责队列语义：排序、上限校验、队首识别、失效清理与顺延。

排序**按 `created_at` 升序**（BR-021），**不依赖自增主键**——自增主键在不同并发
路径下可能乱序。

副本交接规则（BR-024a）：`RESERVED` 副本的归属**始终跟随队列头部**；队首失效或取消时
转交下一位（对方 `ACTIVE` → `READY`，副本保持 `RESERVED`）；队列无有效预约才释放为 `AVAILABLE`。

失效判定为**惰性**（Q-01），但判定后须在**同一次操作内**完成队列顺延与副本交接（BR-025b）。
"""

from __future__ import annotations

from typing import Sequence

from app.domain.domain_services.borrow_eligibility_service import CheckResult
from app.domain.entities.library_item import LibraryItem
from app.domain.entities.reservation import DEFAULT_VALIDITY_DAYS, Reservation
from app.domain.entities.book_title import BookTitle
from app.domain.exceptions import (
    DUPLICATE_RESERVATION,
    ITEM_AVAILABLE_NO_RESERVATION,
    RESERVATION_QUEUE_FULL,
    BusinessRuleError,
)

#: 单个标题的预约队列上限（BR-022）
MAX_QUEUE_SIZE = 5

STEP_RESERVABLE = "reservable"


class ReservationQueueService:
    """预约队列管理服务。无状态。"""

    # ---- 排序与查询 ------------------------------------------------------

    @staticmethod
    def order(reservations: Sequence[Reservation]) -> list[Reservation]:
        """按 `created_at` 升序排序（BR-021）。仅包含有效预约。"""
        return sorted(
            (res for res in reservations if res.is_active()),
            key=lambda res: (res.created_at, res.reservation_id or 0),
        )

    def peek(self, reservations: Sequence[Reservation]) -> Reservation | None:
        """返回队首的有效预约，队列为空返回 `None`。"""
        ordered = self.order(reservations)
        return ordered[0] if ordered else None

    def position_of(self, reservation: Reservation, reservations: Sequence[Reservation]) -> int:
        """指定预约的排队位置（从 1 开始），非有效预约返回 0。"""
        return reservation.queue_position(reservations)

    def size(self, reservations: Sequence[Reservation]) -> int:
        return len(self.order(reservations))

    # ---- 准入校验 --------------------------------------------------------

    def can_reserve(
        self,
        title: BookTitle | None,
        existing_reservations: Sequence[Reservation],
        reader_id: int | None = None,
        has_available_item: bool | None = None,
        max_size: int = MAX_QUEUE_SIZE,
    ) -> CheckResult:
        """判断是否可预约。校验三项：可借性（BR-020）、重复（BR-023）、容量（BR-022）。

        返回**首个失败**。注意：本方法不抛异常，由应用服务决定如何映射错误。

        `has_available_item` 若被显式传入（非 `None`），则以它为准，
        此时允许 `title` 为 `None`——便于对纯队列语义单独测试与复用。
        """
        available = has_available_item
        if available is None:
            if title is None:
                return CheckResult.failed(STEP_RESERVABLE, "TITLE_NOT_FOUND", "图书标题不存在")
            available = title.has_available_item()

        if available:
            return CheckResult.failed(
                STEP_RESERVABLE, ITEM_AVAILABLE_NO_RESERVATION, "当前有可借副本，无需预约"
            )

        effective = self.order(existing_reservations)
        if reader_id is not None and any(res.reader_id == reader_id for res in effective):
            return CheckResult.failed(
                STEP_RESERVABLE, DUPLICATE_RESERVATION, "已存在对该标题的有效预约"
            )

        if len(effective) >= max_size:
            return CheckResult.failed(
                STEP_RESERVABLE, RESERVATION_QUEUE_FULL, f"预约队列已满（上限 {max_size} 人）",
                size=len(effective), max_size=max_size,
            )

        return CheckResult.passed(STEP_RESERVABLE, "可预约")

    def can_reserve_or_raise(self, *args, **kwargs) -> None:
        """同 `can_reserve`，但失败时抛异常（应用服务用）。

        状态码依 `02` FR-021 验收标准 2~4：可借性 400、容量与重复 409。
        """
        result = self.can_reserve(*args, **kwargs)
        if result.ok:
            return
        if result.code == ITEM_AVAILABLE_NO_RESERVATION:
            raise BusinessRuleError(result.message, code=result.code, http_status=400)
        raise BusinessRuleError(result.message, code=result.code, http_status=409, detail=result.detail)

    # ---- 失效清理与顺延 --------------------------------------------------

    def dequeue_expired(
        self,
        reservations: Sequence[Reservation],
        now=None,
        validity_days: int = DEFAULT_VALIDITY_DAYS,
    ) -> list[Reservation]:
        """清理失效预约并返回**本次被置为 EXPIRED 的预约列表**。

        惰性判定：由调用方在查询或还书时触发（Q-01 / BR-025）。
        """
        expired: list[Reservation] = []
        for res in self.order(reservations):
            if res.is_expired(now, validity_days):
                res.expire(now)
                expired.append(res)
        return expired

    def handover(
        self,
        reservations: Sequence[Reservation],
        item: LibraryItem | None = None,
        now=None,
        validity_days: int = DEFAULT_VALIDITY_DAYS,
    ) -> Reservation | None:
        """**副本交接与队列顺延，在同一次调用内完成**（BR-024a、BR-025b）。

        步骤：① 清理失效 → ② 取队首 → ③ 队首置 `READY`、副本置 `RESERVED`。

        返回新的队首预约；队列已无有效预约时返回 `None`——此时调用方应将副本释放为 `AVAILABLE`。
        """
        self.dequeue_expired(reservations, now, validity_days)
        head = self.peek(reservations)
        if head is None:
            return None
        if head.status.value != "READY":
            head.mark_ready(now)
        if item is not None:
            item.mark_reserved()
        return head
